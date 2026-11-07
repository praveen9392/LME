"""
Integration tests for Job Application workflow with mocked network responses.
"""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from backend.models.models import Job
from backend.services.application_service import ApplicationService
from backend.storage.applied_jobs_repo import AppliedJobsDB


def test_application_loop_deduplication_and_apply():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "applied.db")
        csv_path = str(Path(tmp_dir) / "applied.csv")
        db = AppliedJobsDB(db_path=db_path, csv_path=csv_path)

        # Mock Naukri service
        mock_naukri = MagicMock()
        mock_naukri.authenticate.return_value = MagicMock()

        job1 = Job(
            job_id="101", title="Backend Developer", company="Startup A",
            location="Bangalore", experience="2 Yrs", salary="12 LPA",
            posted_date="Today", apply_link="https://naukri.com/job1",
            tags=["Node.js", "Python"],
        )
        job2 = Job(
            job_id="102", title="Python Engineer", company="Startup B",
            location="Hyderabad", experience="1-3 Yrs", salary="10 LPA",
            posted_date="Yesterday", apply_link="https://naukri.com/job2",
            tags=["Python", "FastAPI"],
        )
        job_ext = Job(
            job_id="103", title="DevOps Engineer", company="Enterprise C",
            location="Pune", experience="2 Yrs", salary="14 LPA",
            posted_date="Today", apply_link="https://naukri.com/job3",
            tags=["Python", "AWS"],
        )

        # Pre-apply job1
        db.mark_applied(job1, ai_score=90)

        # Setup mock returns
        mock_naukri.search_jobs.return_value = [job1, job2, job_ext]
        mock_naukri.is_external_apply.side_effect = lambda jid: jid == "103"
        mock_naukri.apply_job.return_value = {"jobs": [{"status": "applied", "questionnaire": None}]}

        # Mock matching service: score all
        mock_matcher = MagicMock()
        mock_matcher.filter_and_rank.return_value = [
            {"job_id": "101", "title": job1.title, "company": job1.company, "ai_score": 90},
            {"job_id": "102", "title": job2.title, "company": job2.company, "ai_score": 85},
            {"job_id": "103", "title": job_ext.title, "company": job_ext.company, "ai_score": 75},
        ]

        app_service = ApplicationService(
            naukri_service=mock_naukri,
            matching_service=mock_matcher,
            storage_db=db,
        )

        stats = app_service.run_pipeline()

        # Assertions
        assert stats.total == 3
        assert stats.skipped_dup == 1  # job1 was already in db
        assert stats.skipped_ext == 1  # job_ext required external apply
        assert stats.applied == 1      # job2 was applied to
        assert db.has_applied("102", "Startup B") is True
