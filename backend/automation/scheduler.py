"""
NopeRi Background Scheduler Daemon using APScheduler 3.x.
Runs periodic profile freshness refreshes and scheduled job application batches.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import List, Optional, Tuple

try:
    from colorama import Fore, Style
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.core.config import ConfigManager
from backend.core.exceptions import SchedulerError
from backend.core.logging import get_logger
from backend.integrations.telegram.client import TelegramClient
from backend.services.application_service import ApplicationService
from backend.services.profile_service import ProfileService

logger = get_logger(__name__)

PID_FILE = Path(".scheduler.pid")


def parse_schedule(schedule_str: str) -> Tuple[int, int]:
    """Parses 'HH:MM' string into (hour, minute) integers."""
    try:
        parts = schedule_str.strip().split(":")
        return int(parts[0]), int(parts[1])
    except Exception:
        logger.warning("Invalid schedule format '%s', defaulting to 08:00", schedule_str)
        return 8, 0


# ── Job Wrapper Functions ────────────────────────────────────────────────────

def execute_profile_update() -> None:
    """Scheduled task: Bumps headline and optionally re-uploads resume."""
    logger.info("── Scheduled Profile Update Starting ──")
    try:
        service = ProfileService()
        success = service.run_update()
        logger.info("── Scheduled Profile Update Finished (success=%s) ──", success)
    except Exception as exc:
        logger.error("Scheduled Profile Update encountered error: %s", exc)


def execute_apply_agent() -> None:
    """Scheduled task: Full search -> score -> apply run."""
    logger.info("── Scheduled Apply Run Starting ──")
    try:
        service = ApplicationService()
        stats = service.run_pipeline(mode="scheduled")
        logger.info(
            "── Scheduled Apply Run Finished (applied=%d, failed=%d, skipped=%d) ──",
            stats.applied,
            stats.failed,
            stats.skipped_ext + stats.skipped_dup,
        )
    except Exception as exc:
        logger.error("Scheduled Apply Run encountered error: %s", exc)


# ── Scheduler Builder ────────────────────────────────────────────────────────

def build_scheduler(config: Optional[dict] = None) -> Tuple[BlockingScheduler, List[str]]:
    """Builds and configures the APScheduler instance based on config.json settings."""
    cfg = ConfigManager() if config is None else None
    conf = config if config is not None else cfg.config

    cron_cfg = conf.get("cron", {})
    tz = cron_cfg.get("apply", {}).get("timezone", "Asia/Kolkata")

    sched = BlockingScheduler(timezone=tz)
    job_labels: List[str] = []

    # 1. Profile updater job
    pu_cfg = cron_cfg.get("profile_update", {})
    if pu_cfg.get("enabled", True):
        interval_h = pu_cfg.get("interval_hours", 6)
        sched.add_job(
            execute_profile_update,
            trigger=IntervalTrigger(hours=interval_h, timezone=tz),
            id="profile_update",
            replace_existing=True,
            misfire_grace_time=300,
        )
        label = f"Profile update (every {interval_h}h)"
        job_labels.append(label)
        logger.info("Scheduled task: %s", label)

    # 2. Job apply agent job
    ap_cfg = cron_cfg.get("apply", {})
    if ap_cfg.get("enabled", True):
        schedule_str = ap_cfg.get("schedule", "08:00")
        days = ap_cfg.get("days", "mon-fri")
        hour, minute = parse_schedule(schedule_str)
        day_of_week = ",".join(days) if isinstance(days, list) else days

        sched.add_job(
            execute_apply_agent,
            trigger=CronTrigger(
                hour=hour,
                minute=minute,
                day_of_week=day_of_week,
                timezone=tz,
            ),
            id="apply_agent",
            replace_existing=True,
            misfire_grace_time=600,
        )
        label = f"Apply agent ({schedule_str} {tz}, {day_of_week})"
        job_labels.append(label)
        logger.info("Scheduled task: %s", label)

    return sched, job_labels


def _acquire_instance_lock() -> bool:
    """Ensures only a single scheduler daemon runs at any given time."""
    current_pid = os.getpid()
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            # Check if process is still active
            if old_pid != current_pid:
                if os.name == "nt":
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, old_pid)
                    if h_proc:
                        kernel32.CloseHandle(h_proc)
                        logger.warning("Another scheduler instance is already running with PID %d", old_pid)
                        return False
                else:
                    try:
                        os.kill(old_pid, 0)
                        logger.warning("Another scheduler instance is already running with PID %d", old_pid)
                        return False
                    except OSError:
                        pass
        except Exception:
            pass

    PID_FILE.write_text(str(current_pid), encoding="utf-8")
    return True


def _release_instance_lock() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _print_banner(sched: BlockingScheduler, job_labels: List[str]) -> None:
    border = Fore.CYAN + "─" * 60 + Style.RESET_ALL if HAS_COLORAMA else "─" * 60
    title = Fore.CYAN + Style.BRIGHT + "NopeRi Background Scheduler" + Style.RESET_ALL if HAS_COLORAMA else "NopeRi Background Scheduler"
    print(f"\n{border}\n  {title}\n{border}")
    for job in sched.get_jobs():
        bullet = (Fore.WHITE + "●" + Style.RESET_ALL) if HAS_COLORAMA else "●"
        next_run = (Fore.CYAN + f"next: {job.next_run_time}" + Style.RESET_ALL) if HAS_COLORAMA else f"next: {job.next_run_time}"
        print(f"  {bullet}  {job.name or job.id:<20} {next_run}")
    print(f"\n  Press Ctrl+C to stop.\n")


def run_scheduler() -> None:
    """Entry point for the background scheduler process."""
    if not _acquire_instance_lock():
        print("Scheduler is already active in another process. Exiting.")
        sys.exit(1)

    cfg = ConfigManager()
    tg = TelegramClient()
    sched, job_labels = build_scheduler(cfg.config)

    if not sched.get_jobs():
        print("No background jobs are enabled in config.json under 'cron'. Exiting.")
        _release_instance_lock()
        return

    _print_banner(sched, job_labels)

    if cfg.config.get("telegram", {}).get("enabled"):
        tg.alert_scheduler_started(job_labels)

    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutdown initiated by user.")
        if cfg.config.get("telegram", {}).get("enabled"):
            tg.alert_scheduler_stopped()
    finally:
        _release_instance_lock()
