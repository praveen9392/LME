"""
End-to-End Job Application Service.
Orchestrates search -> filter -> score -> questionnaire -> apply -> track pipeline.
"""
from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional, Set

try:
    from colorama import Fore, Style
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

from backend.core.config import ConfigManager
from backend.core.logging import get_logger
from backend.integrations.telegram.client import TelegramClient
from backend.models.models import Job, RunStats
from backend.services.job_matching_service import JobMatchingService
from backend.services.naukri_service import NaukriService
from backend.services.questionnaire_service import QuestionnaireService
from backend.storage.applied_jobs_repo import AppliedJobsDB

logger = get_logger(__name__)

_LINE = (Fore.WHITE + "─" * 68 + Style.RESET_ALL) if HAS_COLORAMA else ("─" * 68)
_THIN = (Fore.WHITE + "·" * 68 + Style.RESET_ALL) if HAS_COLORAMA else ("·" * 68)


class ApplicationService:
    """Coordinates search queries, candidate matching, and automated job submissions."""

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        naukri_service: Optional[NaukriService] = None,
        matching_service: Optional[JobMatchingService] = None,
        questionnaire_service: Optional[QuestionnaireService] = None,
        storage_db: Optional[AppliedJobsDB] = None,
        telegram_client: Optional[TelegramClient] = None,
    ) -> None:
        self.cfg = config_manager or ConfigManager()
        self.naukri = naukri_service or NaukriService(self.cfg)
        self.matcher = matching_service or JobMatchingService(self.cfg)
        self.qa = questionnaire_service or QuestionnaireService(self.cfg)
        self.db = storage_db or AppliedJobsDB()
        self.tg = telegram_client or TelegramClient()

    # ── Job Fetching ─────────────────────────────────────────────────────────

    def fetch_jobs(self) -> List[Job]:
        """Iterates over configured search queries and collects unique job vacancies."""
        config = self.cfg.config
        queries = config.get("queries", [])
        search_cfg = config.get("search", {})
        exp = config.get("profile", {}).get("experience_years", 2)
        job_age = search_cfg.get("job_age", 2)
        pages = search_cfg.get("pages_per_query", 1)

        seen_ids: Set[str] = set()
        all_jobs: List[Job] = []

        self._print_section(f"Fetching Jobs ({len(queries)} queries × {pages} pages)")

        for q in queries:
            kw = q.get("keyword", "")
            loc = q.get("location", "")
            for page in range(1, pages + 1):
                try:
                    jobs = self.naukri.search_jobs(
                        keyword=kw,
                        location=loc,
                        page=page,
                        job_age=job_age,
                        experience=exp,
                    )
                    new_jobs = [j for j in jobs if j.job_id not in seen_ids and not seen_ids.add(j.job_id)]
                    all_jobs.extend(new_jobs)
                    self._print_fetch_row(kw, loc, exp, page, len(jobs), len(new_jobs))
                    if not jobs:
                        break
                    time.sleep(1.2)
                except Exception as exc:
                    logger.warning("Job fetch failed for '%s' @ '%s': %s", kw, loc, exc)
                    time.sleep(2)

        logger.info("Total unique jobs fetched across all queries: %d", len(all_jobs))
        return all_jobs

    # ── Main Run Pipeline ────────────────────────────────────────────────────

    def run_pipeline(self, mode: str = "manual") -> RunStats:
        """
        Executes complete search, filter, score, and application run.
        Returns RunStats model with counts.
        """
        config = self.cfg.config
        tg_cfg = config.get("telegram", {})
        tg_on = tg_cfg.get("enabled", False)
        alerts = tg_cfg.get("alerts", {})

        stats = RunStats()

        # 1. Authenticate
        self._print_section("Authenticating with Naukri")
        try:
            self.naukri.authenticate()
        except Exception as exc:
            logger.critical("Naukri authentication failed: %s", exc)
            if tg_on and alerts.get("on_error", True):
                self.tg.alert_error(f"Naukri authentication failed: {exc}")
            raise

        if tg_on and alerts.get("on_scheduler_start", True):
            self.tg.alert_run_started(mode)

        # 2. Fetch Jobs
        jobs = self.fetch_jobs()
        stats.total = len(jobs)
        if not jobs:
            logger.info("No jobs found matching criteria.")
            return stats

        # 3. Filter & AI Score
        self._print_section("Running Job Filter & AI Scoring Pipeline")
        scored_jobs = self.matcher.filter_and_rank(jobs)
        stats.allowed = len(scored_jobs)

        score_map: Dict[str, Dict[str, Any]] = {
            str(j.get("job_id")): j for j in scored_jobs
        }

        # Build list of Job instances for apply loop
        candidate_jobs = [j for j in jobs if str(j.job_id) in score_map]

        self._print_pipeline_table(scored_jobs)

        # 4. Apply Loop
        self._print_section(f"Applying to {len(candidate_jobs)} Filtered Jobs")

        for idx, job in enumerate(candidate_jobs, 1):
            meta = score_map.get(str(job.job_id), {})
            score = meta.get("ai_score")
            reason = meta.get("ai_reason")

            self._print_job(idx, len(candidate_jobs), job, score, reason)

            # Check local database for prior application
            if self.db.has_applied(job.job_id, job.company):
                logger.info("Skipping job %s — already applied previously", job.job_id)
                self._print_status("Skipped — already applied previously", Fore.YELLOW if HAS_COLORAMA else "")
                stats.skipped_dup += 1
                continue

            # Check if external careers portal redirect is required
            if self.naukri.is_external_apply(job.job_id):
                logger.info("Skipping job %s — external redirect apply", job.job_id)
                self._print_status("Skipped — external apply link", Fore.YELLOW if HAS_COLORAMA else "")
                stats.skipped_ext += 1
                continue

            mandatory = job.tags[:2] if job.tags else []
            optional = job.tags[2:] if len(job.tags) > 2 else []

            try:
                result = self.naukri.apply_job(
                    job, mandatory_skills=mandatory, optional_skills=optional, source="search"
                )
                job_result = (result.get("jobs") or [{}])[0]

                # Check if employer attached a screening questionnaire
                if job_result.get("questionnaire"):
                    logger.info("Questionnaire detected for job %s @ %s", job.title, job.company)
                    self._print_status("Questionnaire detected — solving automatically", Fore.CYAN if HAS_COLORAMA else "")
                    if tg_on and alerts.get("on_questionnaire"):
                        self.tg.alert_questionnaire(job.title, job.company)

                    sid = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "0000000"
                    answers = self.qa.answer(job_result["questionnaire"], job)
                    result = self.naukri.apply_with_questionnaire(
                        job=job,
                        questionnaire=job_result["questionnaire"],
                        answers=answers,
                        mandatory_skills=mandatory,
                        optional_skills=optional,
                        source="search",
                        sid=sid,
                    )

                self._print_status("Applied successfully", Fore.GREEN if HAS_COLORAMA else "")
                self.db.mark_applied(job, ai_score=score)
                stats.applied += 1

                if tg_on and alerts.get("on_apply", True):
                    self.tg.alert_apply(job.title, job.company, score, job.job_id)

            except Exception as exc:
                logger.error("Failed to apply for job %s: %s", job.job_id, exc)
                self._print_status(f"Failed — {exc}", Fore.RED if HAS_COLORAMA else "")
                stats.failed += 1

                if tg_on and alerts.get("on_failure", True):
                    self.tg.alert_failed(job.title, job.company, str(exc))

            time.sleep(3)

        # 5. Run Summary
        self._print_summary(stats)

        if tg_on and alerts.get("on_run_summary", True):
            self.tg.alert_run_summary(
                total_found=stats.total,
                applied=stats.applied,
                skipped_ext=stats.skipped_ext,
                skipped_dup=stats.skipped_dup,
                failed=stats.failed,
            )

        return stats

    # ── Console Presentation Helpers ────────────────────────────────────────

    def _print_section(self, title: str) -> None:
        title_str = (Fore.CYAN + Style.BRIGHT + title.upper() + Style.RESET_ALL) if HAS_COLORAMA else title.upper()
        print(f"\n{_LINE}\n  {title_str}\n{_LINE}")

    def _print_status(self, text: str, color_code: str) -> None:
        reset = Style.RESET_ALL if HAS_COLORAMA else ""
        print(f"  Status  :  {color_code}{text}{reset}")

    def _print_fetch_row(self, keyword: str, location: str, exp: int, page: int, fetched: int, new: int) -> None:
        loc_str = (location or "All India")[:12]
        new_color = (Fore.GREEN if HAS_COLORAMA else "") if new > 0 else ""
        reset = Style.RESET_ALL if HAS_COLORAMA else ""
        print(
            f"  [{keyword[:30]:<30} | {loc_str:<12} | exp={exp} | p{page}]  "
            f"{fetched:>3} fetched  {new_color}{new:>3} new{reset}"
        )

    def _print_pipeline_table(self, jobs: List[Dict[str, Any]]) -> None:
        self._print_section(f"AI Filter — {len(jobs)} Jobs Selected")
        w = [4, 35, 28, 6]
        header = f"  {'#':<{w[0]}}  {'Title':<{w[1]}}  {'Company':<{w[2]}}  {'Score':>{w[3]}}"
        print(header)
        print(f"  {'─' * sum(w)}")
        for i, j in enumerate(jobs, 1):
            s = j.get("ai_score")
            sc = ""
            if HAS_COLORAMA:
                sc = Fore.GREEN if s and s >= 70 else (Fore.YELLOW if s and s >= 50 else Fore.RED)
            reset = Style.RESET_ALL if HAS_COLORAMA else ""
            sd = f"{sc}{s:>3}{reset}" if s is not None else "  ?"
            print(
                f"  {i:<{w[0]}}  "
                f"{(j.get('title') or '')[:w[1]]:<{w[1]}}  "
                f"{(j.get('company') or '')[:w[2]]:<{w[2]}}  "
                f"{sd}"
            )

    def _print_job(self, index: int, total: int, job: Job, score: Optional[int] = None, reason: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M UTC")
        print(f"\n{_LINE}")
        print(f"  JOB {index}/{total}  {now}")
        print(_THIN)
        print(f"  Title   :  {job.title}")
        print(f"  Company :  {job.company}")
        print(f"  Job ID  :  {job.job_id}")
        print(f"  URL     :  https://www.naukri.com/job-listings-{job.job_id}")
        if score is not None:
            detail = f"  ({reason})" if reason else ""
            print(f"  Score   :  {score}/100{detail}")
        if job.tags:
            print(f"  Tags    :  {'  '.join(f'[{t}]' for t in job.tags)}")

    def _print_summary(self, stats: RunStats) -> None:
        self._print_section("Run Summary")
        rows = [
            ("Jobs fetched (total unique)", str(stats.total)),
            ("Jobs passed AI filter", str(stats.allowed)),
            ("Applied successfully", str(stats.applied)),
            ("Skipped (external apply)", str(stats.skipped_ext)),
            ("Skipped (already applied)", str(stats.skipped_dup)),
            ("Failed", str(stats.failed)),
        ]
        for label, val in rows:
            print(f"  {label:<30}  {val}")
        print(_LINE + "\n")
