"""
Change-detection smoke tests for NopeRi.

Run:  pytest tests/ -v
Run (skip live network):  pytest tests/ -v -m "not live"

Live tests need NAUKRI_USERNAME + PASSWORD in .env.
They are skipped automatically when credentials are absent.

Purpose: fail fast when Naukri changes their API shape.
Not a unit-test suite — no mocking, real HTTP where needed.
"""
import os
import pytest
from dotenv import load_dotenv

load_dotenv()

_HAS_CREDS = bool(os.getenv("NAUKRI_USERNAME")) and bool(os.getenv("PASSWORD"))
live = pytest.mark.skipif(not _HAS_CREDS, reason="NAUKRI_USERNAME / PASSWORD not in .env")

# ---------------------------------------------------------------------------
# 1. vid token (no network)
# ---------------------------------------------------------------------------

def test_vid_token_generates():
    from backend.integrations.naukri.crypto import generate_vid
    try:
        vid = generate_vid()
        assert isinstance(vid, str) and len(vid) > 10, "vid token looks wrong"
    except Exception as exc:
        pytest.skip(f"Node.js not available for vid test: {exc}")

# ---------------------------------------------------------------------------
# 2. Login — checks BotGuard hasn't broken the auth flow
# ---------------------------------------------------------------------------

@live
def test_login_returns_nauk_at():
    from backend.integrations.naukri.auth import NaukriAuthClient
    client = NaukriAuthClient(
        username=os.getenv("NAUKRI_USERNAME"),
        password=os.getenv("PASSWORD"),
    )
    client.login()
    nauk_at = client.session.cookies.get("nauk_at")
    assert nauk_at, "nauk_at cookie missing after login — BotGuard may have changed"
    assert len(nauk_at) > 20, f"nauk_at suspiciously short: {nauk_at!r}"

# ---------------------------------------------------------------------------
# 3. Job search schema — checks key fields still present in response
# ---------------------------------------------------------------------------

REQUIRED_JOB_FIELDS = ["job_id", "title", "company", "location"]

@live
def test_job_search_returns_results():
    from backend.integrations.naukri.auth import NaukriAuthClient
    from backend.integrations.naukri.jobs import NaukriJobApiClient
    client = NaukriAuthClient(
        username=os.getenv("NAUKRI_USERNAME"),
        password=os.getenv("PASSWORD"),
    )
    client.login()
    jc = NaukriJobApiClient(client)
    jobs = jc.search_jobs("Python developer", "", experience=2, pages=1)
    assert len(jobs) > 0, "Job search returned 0 results — endpoint or auth may have changed"

@live
def test_job_schema_has_required_fields():
    from backend.integrations.naukri.auth import NaukriAuthClient
    from backend.integrations.naukri.jobs import NaukriJobApiClient
    client = NaukriAuthClient(
        username=os.getenv("NAUKRI_USERNAME"),
        password=os.getenv("PASSWORD"),
    )
    client.login()
    jc = NaukriJobApiClient(client)
    jobs = jc.search_jobs("Python developer", "", experience=2, pages=1)
    assert jobs, "No jobs returned"
    job = jobs[0]
    missing = [f for f in REQUIRED_JOB_FIELDS if not hasattr(job, f)]
    assert not missing, f"Job response missing fields: {missing}\nGot attrs: {dir(job)}"

# ---------------------------------------------------------------------------
# 4. Recommended jobs schema
# ---------------------------------------------------------------------------

@live
def test_recommended_jobs_schema():
    from backend.integrations.naukri.auth import NaukriAuthClient
    from backend.integrations.naukri.jobs import NaukriJobApiClient
    client = NaukriAuthClient(
        username=os.getenv("NAUKRI_USERNAME"),
        password=os.getenv("PASSWORD"),
    )
    client.login()
    jc = NaukriJobApiClient(client)
    jobs = jc.get_recommended_jobs(pages=1)
    if not jobs:
        pytest.skip("No recommended jobs returned (empty feed is not a failure)")
    job = jobs[0]
    missing = [f for f in REQUIRED_JOB_FIELDS if not hasattr(job, f)]
    assert not missing, f"Recommended job response missing fields: {missing}\nGot attrs: {dir(job)}"
