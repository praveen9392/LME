"""
Integration tests for background scheduler builder and trigger configuration.
"""
from backend.automation.scheduler import build_scheduler, parse_schedule


def test_parse_schedule():
    h, m = parse_schedule("08:30")
    assert h == 8
    assert m == 30

    h_def, m_def = parse_schedule("invalid")
    assert h_def == 8
    assert m_def == 0


def test_build_scheduler_triggers():
    custom_config = {
        "cron": {
            "profile_update": {
                "enabled": True,
                "interval_hours": 4,
            },
            "apply": {
                "enabled": True,
                "schedule": "09:15",
                "days": "mon,wed,fri",
                "timezone": "Asia/Kolkata",
            },
        }
    }

    sched, job_labels = build_scheduler(custom_config)
    jobs = sched.get_jobs()

    assert len(jobs) == 2
    job_ids = [j.id for j in jobs]
    assert "profile_update" in job_ids
    assert "apply_agent" in job_ids

    assert any("every 4h" in lbl for lbl in job_labels)
    assert any("09:15" in lbl for lbl in job_labels)
