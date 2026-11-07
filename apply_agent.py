"""
apply_agent.py — NopeRi automated Naukri job application agent.

Usage:
  python apply_agent.py                     normal run
  python apply_agent.py --setup             re-run setup wizard
  python apply_agent.py --dashboard         open HTML dashboard
  python apply_agent.py --list-applied      print applied job history
  python apply_agent.py --remove-job HASH   allow re-apply for one job
  python apply_agent.py --veto list
  python apply_agent.py --veto add-company "Infosys"
  python apply_agent.py --veto remove-company "Infosys"
  python apply_agent.py --veto add-title "walk-in"
  python apply_agent.py --veto remove-title "walk-in"
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import os
import sys

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

from backend.core.config import CONFIG_PATH, ConfigManager
from backend.core.logging import configure_logging, get_logger
from backend.models.models import RunStats
from backend.services.application_service import ApplicationService
from backend.storage.applied_jobs_repo import AppliedJobsDB
from backend.web.server import launch_dashboard, launch_wizard

# Configure central logging
configure_logging()
logger = get_logger(__name__)


# ── CLI Argument Parser ──────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="apply_agent",
        description="NopeRi — Naukri automated job application agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Veto examples:\n"
            "  --veto list\n"
            "  --veto add-company Infosys\n"
            "  --veto remove-company Infosys\n"
            "  --veto add-title walk-in\n"
            "  --veto remove-title walk-in"
        ),
    )
    parser.add_argument("--setup", action="store_true", help="Re-run the browser setup wizard")
    parser.add_argument("--dashboard", action="store_true", help="Open local analytics dashboard and exit")
    parser.add_argument("--list-applied", action="store_true", help="Print applied job history and exit")
    parser.add_argument("--remove-job", metavar="HASH", help="Remove a job from history (enables re-apply)")
    parser.add_argument("--veto", nargs="+", metavar="ARG", help="Manage company and title veto lists")
    return parser.parse_args()


# ── Subcommand Handlers ──────────────────────────────────────────────────────

def _handle_veto(args_list: list, cfg: ConfigManager) -> None:
    veto = cfg.load_veto()
    action = args_list[0].lower() if args_list else "list"

    cyan = Fore.CYAN if HAS_COLORAMA else ""
    yellow = Fore.YELLOW if HAS_COLORAMA else ""
    green = Fore.GREEN if HAS_COLORAMA else ""
    red = Fore.RED if HAS_COLORAMA else ""
    reset = Style.RESET_ALL if HAS_COLORAMA else ""

    if action == "list":
        print(f"\n{cyan}-- Company vetoes ----------------------------------------{reset}")
        for c in sorted(veto.get("companies", [])):
            print(f"  {yellow}{c}{reset}")
        print(f"\n{cyan}-- Title vetoes ------------------------------------------{reset}")
        for t in sorted(veto.get("titles", [])):
            print(f"  {t}")
        return

    if len(args_list) < 2:
        print(f"{red}  Usage: --veto {action} <value>{reset}")
        return

    value = " ".join(args_list[1:]).lower().strip()

    if action == "add-company":
        lst = veto.setdefault("companies", [])
        if value not in [x.lower() for x in lst]:
            lst.append(value)
            cfg.save_veto(veto)
            print(f"{green}  [+] Added company veto: {value}{reset}")
        else:
            print(f"{yellow}  Already in list: {value}{reset}")

    elif action == "remove-company":
        before = len(veto.get("companies", []))
        veto["companies"] = [x for x in veto.get("companies", []) if x.lower() != value]
        if len(veto["companies"]) < before:
            cfg.save_veto(veto)
            print(f"{green}  [-] Removed company veto: {value}{reset}")
        else:
            print(f"{yellow}  Not found: {value}{reset}")

    elif action == "add-title":
        lst = veto.setdefault("titles", [])
        if value not in [x.lower() for x in lst]:
            lst.append(value)
            cfg.save_veto(veto)
            print(f"{green}  [+] Added title veto: {value}{reset}")
        else:
            print(f"{yellow}  Already in list: {value}{reset}")

    elif action == "remove-title":
        before = len(veto.get("titles", []))
        veto["titles"] = [x for x in veto.get("titles", []) if x.lower() != value]
        if len(veto["titles"]) < before:
            cfg.save_veto(veto)
            print(f"{green}  [-] Removed title veto: {value}{reset}")
        else:
            print(f"{yellow}  Not found: {value}{reset}")

    else:
        print(f"{red}  Unknown action: {action}{reset}")
        print("  Valid actions: list | add-company | remove-company | add-title | remove-title")


def _handle_list_applied(db: AppliedJobsDB) -> None:
    rows = db.list_applied(limit=50)
    yellow = Fore.YELLOW if HAS_COLORAMA else ""
    cyan = Fore.CYAN if HAS_COLORAMA else ""
    reset = Style.RESET_ALL if HAS_COLORAMA else ""

    if not rows:
        print(f"\n{yellow}  No applied jobs on record yet.{reset}")
        return

    print(f"\n  APPLIED JOBS (LAST {len(rows)})")
    print(f"  {'HASH':<18}  {'Score':>5}  {'Title':<34}  {'Company':<24}  Applied At")
    print(f"  {'-'*18}  {'-'*5}  {'-'*34}  {'-'*24}  {'-'*19}")
    for row in rows:
        sc = row.get("ai_score")
        sc_str = f"{sc:>5}" if sc is not None else "    ?"
        print(
            f"  {cyan}{row['hash']:<18}{reset}  "
            f"{sc_str}  "
            f"{(row.get('title') or '')[:34]:<34}  "
            f"{yellow}{(row.get('company') or '')[:24]:<24}{reset}  "
            f"{(row.get('applied_at') or '')[:19]}"
        )
    print(f"\n  Total on record: {db.total()}")
    print("  Use --remove-job <HASH> to allow re-applying to a job.\n")


# ── Core Pipeline Entry ──────────────────────────────────────────────────────

def run_agent(cfg: ConfigManager, db: AppliedJobsDB) -> dict:
    """
    Executes full search -> score -> apply pipeline.
    Preserves exact contract expected by cron/scheduler.py.
    Returns stats dict: {total, applied, skipped_ext, skipped_dup, failed}.
    """
    app_service = ApplicationService(config_manager=cfg, storage_db=db)
    stats: RunStats = app_service.run_pipeline(mode="manual")
    return stats.to_dict()


# ── Main Entry Point ─────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()
    cfg = ConfigManager()
    db = AppliedJobsDB()

    if args.dashboard:
        launch_dashboard()
        sys.exit(0)

    if args.veto:
        _handle_veto(args.veto, cfg)
        sys.exit(0)

    if args.list_applied:
        _handle_list_applied(db)
        sys.exit(0)

    if args.remove_job:
        green = Fore.GREEN if HAS_COLORAMA else ""
        yellow = Fore.YELLOW if HAS_COLORAMA else ""
        reset = Style.RESET_ALL if HAS_COLORAMA else ""
        if db.remove(args.remove_job):
            print(f"{green}  ✓ Removed {args.remove_job} — job can now be re-applied.{reset}")
        else:
            print(f"{yellow}  Hash not found: {args.remove_job}{reset}")
        sys.exit(0)

    if args.setup or not CONFIG_PATH.exists():
        launch_wizard()
        cfg.reload()
        if args.setup:
            sys.exit(0)

    # One-time CSV -> SQLite migration (silent if no CSV)
    if os.path.exists("applied_jobs.csv"):
        count = 0
        try:
            with open("applied_jobs.csv", newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    job_id = (row.get("job_id") or "").strip()
                    if job_id:
                        h = AppliedJobsDB._hash(job_id, "")
                        db._insert_raw(
                            h,
                            job_id,
                            row.get("title", ""),
                            row.get("company", ""),
                            "",
                            None,
                            row.get("applied_at", datetime.now(timezone.utc).isoformat()),
                        )
                        count += 1
        except Exception:
            pass
        if count:
            logger.info("Migrated %d records from CSV to SQLite", count)

    run_agent(cfg, db)


if __name__ == "__main__":
    main()
