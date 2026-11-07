"""
Unit tests for centralized logging and SecretMaskingFilter.
"""
import logging
from backend.core.logging import SecretMaskingFilter, configure_logging, get_logger


def test_secret_masking_filter_bearer_token():
    filt = SecretMaskingFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Authenticated with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz123",
        args=(), exc_info=None
    )
    filt.filter(record)
    assert "[REDACTED_TOKEN]" in record.msg
    assert "eyJhbGciOi" not in record.msg


def test_secret_masking_filter_api_key():
    filt = SecretMaskingFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Using OpenRouter key sk-or-v1-abcdef0123456789abcdef0123456789 to query LLM",
        args=(), exc_info=None
    )
    filt.filter(record)
    assert "sk-or-v1-[REDACTED]" in record.msg
    assert "abcdef0123456789" not in record.msg


def test_secret_masking_filter_telegram_token():
    filt = SecretMaskingFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Calling https://api.telegram.org/bot123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ/sendMessage",
        args=(), exc_info=None
    )
    filt.filter(record)
    assert "[REDACTED_TG_TOKEN]" in record.msg
    assert "ABCdefGhIJKlmNoPQRsTUVwxyZ" not in record.msg


def test_secret_masking_filter_password():
    filt = SecretMaskingFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg='Payload contains {"username": "admin", "password": "supersecretpassword123"}',
        args=(), exc_info=None
    )
    filt.filter(record)
    assert "[REDACTED_PASSWORD]" in record.msg
    assert "supersecretpassword123" not in record.msg
