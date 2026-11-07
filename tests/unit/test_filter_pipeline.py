"""
Unit tests for the multi-stage heuristic job filter pipeline.
"""
from backend.services.job_matching_service import JobMatchingService


def test_normalize_jobs():
    pipeline = JobMatchingService()
    raw_jobs = [
        {
            "job_id": "1",
            "title": "Backend Developer",
            "company": "Tech Corp",
            "posted_date": "3 days ago",
            "experience": "2-4 Yrs",
            "tags": "Python, Node.js, AWS",
        },
        {
            "job_id": "2",
            "title": "Software Engineer",
            "company": "NextGen",
            "posted_date": "Just now",
            "experience": "0-1 Yrs",
            "skills": ["Python", "FastAPI"],
        },
    ]

    normalized = pipeline.normalize_jobs(raw_jobs)
    assert len(normalized) == 2
    assert normalized[0]["days_old"] == 3
    assert normalized[0]["experience_min"] == 2
    assert normalized[0]["experience_max"] == 4
    assert "python" in normalized[0]["tags"]

    assert normalized[1]["days_old"] == 0
    assert normalized[1]["experience_min"] == 0


def test_dedup():
    pipeline = JobMatchingService()
    jobs = [
        {"job_id": "100", "title": "Dev 1"},
        {"job_id": "100", "title": "Dev 1 Duplicate"},
        {"job_id": "200", "title": "Dev 2"},
    ]
    deduped = pipeline.dedup(jobs)
    assert len(deduped) == 2
    assert [j["job_id"] for j in deduped] == ["100", "200"]


def test_hard_veto():
    pipeline = JobMatchingService()
    jobs = [
        {"title": "Backend Software Engineer"},
        {"title": "Walk-in Interview for Java"},
        {"title": "Frontend Internship"},
    ]
    passed = pipeline.hard_veto(jobs)
    assert len(passed) == 1
    assert passed[0]["title"] == "Backend Software Engineer"


def test_experience_filter():
    pipeline = JobMatchingService()
    jobs = [
        {"title": "Junior Dev", "experience_min": 1, "experience_max": 3},
        {"title": "Principal Architect", "experience_min": 8, "experience_max": 12},
    ]
    passed = pipeline.experience_filter(jobs)
    assert len(passed) == 1
    assert passed[0]["title"] == "Junior Dev"


def test_company_veto():
    pipeline = JobMatchingService()
    jobs = [
        {"title": "Dev", "company": "Infosys Technologies"},
        {"title": "Dev", "company": "Cool Startup"},
    ]
    passed = pipeline.company_veto(jobs)
    assert len(passed) == 1
    assert passed[0]["company"] == "Cool Startup"
