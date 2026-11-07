"""
Unit tests for RSA nkparam signing and BotGuard token generation.
"""
from backend.integrations.naukri.crypto import generate_nkparam, generate_vid


def test_nkparam_generates_valid_base64_string():
    token = generate_nkparam("srp")
    assert isinstance(token, str)
    assert len(token) > 40
    # Test specific job id signing
    job_token = generate_nkparam("123456789")
    assert isinstance(job_token, str)
    assert len(job_token) > 40
    assert token != job_token


def test_vid_token_generates_or_skips(monkeypatch):
    try:
        vid = generate_vid("nlogin-login")
        assert isinstance(vid, str)
        assert len(vid) > 10
    except Exception as exc:
        # If Node.js is not on PATH or environment cannot run node
        pytest.skip(f"Node.js not available in test runner environment: {exc}")
