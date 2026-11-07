"""
scheduler.py — NopeRi Background Scheduler Daemon (APScheduler 3.x).
Runs profile freshness updates on an interval and job application batches on a cron schedule.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow project root imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.automation.scheduler import (
    build_scheduler,
    execute_apply_agent as job_apply_agent,
    execute_profile_update as job_profile_update,
    run_scheduler as main,
)
from backend.core.logging import configure_logging

configure_logging()

if __name__ == "__main__":
    main()
