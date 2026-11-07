"""
Unit tests for SQLite and CSV storage repositories.
"""
import tempfile
from pathlib import Path

from backend.models.models import Job
from backend.storage.applied_jobs_repo import AppliedJobsDB
from backend.storage.token_pool_repo import NkparamDB


def test_applied_jobs_db_crud():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "applied.db")
        csv_path = str(Path(tmp_dir) / "applied.csv")
        repo = AppliedJobsDB(db_path=db_path, csv_path=csv_path)

        assert repo.total() == 0

        job = Job(
            job_id="999111",
            title="Backend Python Developer",
            company="Startup Labs",
            location="Bangalore",
            experience="2 Yrs",
            salary="10 LPA",
            posted_date="Today",
            apply_link="https://www.naukri.com/job-999111",
        )

        # Before applying
        assert repo.has_applied(job.job_id, job.company) is False

        # Mark applied
        h = repo.mark_applied(job, ai_score=85)
        assert isinstance(h, str) and len(h) == 16
        assert repo.total() == 1
        assert repo.has_applied(job.job_id, job.company) is True

        # Check list applied
        rows = repo.list_applied(limit=10)
        assert len(rows) == 1
        assert rows[0]["job_id"] == "999111"
        assert rows[0]["ai_score"] == 85

        # Remove job
        removed = repo.remove(h)
        assert removed is True
        assert repo.total() == 0
        assert repo.has_applied(job.job_id, job.company) is False


def test_token_pool_repo():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "tokens.db")
        pool = NkparamDB(db_path=db_path)

        assert pool.get_nkparam() is None

        pool.add_nkparam("token_alpha")
        pool.add_nkparam("token_beta")

        t1 = pool.get_nkparam()
        assert t1 == "token_alpha"

        t2 = pool.get_nkparam()
        assert t2 == "token_beta"

        # All consumed
        assert pool.get_nkparam() is None
