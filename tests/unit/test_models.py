"""
Unit tests for data models and dataclass serialization.
"""
from backend.models.models import (
    ApplicationHistory,
    ApplicationStatus,
    Job,
    NaukriSession,
    ProfileUpdateResult,
    ResumeUpdateResult,
    RunStats,
)


def test_job_dataclass():
    job = Job(
        job_id="12345",
        title="Senior Python Engineer",
        company="Tech Corp",
        location="Bangalore",
        experience="2-4 Yrs",
        salary="15-20 LPA",
        posted_date="Just Now",
        apply_link="https://www.naukri.com/job-listings-12345",
        tags=["Python", "FastAPI", "Docker"],
    )
    assert job.job_id == "12345"
    assert len(job.tags) == 3
    d = job.to_dict()
    assert d["title"] == "Senior Python Engineer"
    assert d["company"] == "Tech Corp"


def test_naukri_session_model():
    session = NaukriSession(bearer_token="token_xyz", cookies={"nauk_at": "token_xyz"})
    assert session.bearer_token == "token_xyz"
    assert not session.is_expired()


def test_run_stats_model():
    stats = RunStats(total=10, allowed=8, applied=5, skipped_ext=2, skipped_dup=1, failed=0)
    d = stats.to_dict()
    assert d["total"] == 10
    assert d["applied"] == 5
    assert d["failed"] == 0


def test_profile_update_result():
    res = ProfileUpdateResult(profile_id="PID_001", response={"ok": True}, status_code=200)
    assert res.is_success is True

    res_fail = ProfileUpdateResult(profile_id="PID_001", response={"error": True}, status_code=400)
    assert res_fail.is_success is False
