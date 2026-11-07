"""
Custom exception hierarchy for Naukri Automation.
"""
from __future__ import annotations

from typing import Optional


class NaukriAutomationError(Exception):
    """Base exception for all errors in the Naukri automation application."""
    pass


# ── Naukri Client & API Exceptions ──────────────────────────────────────────

class NaukriClientError(NaukriAutomationError):
    """Base exception for all direct Naukri client errors."""
    pass


class NaukriAuthError(NaukriClientError):
    """Authentication or session-related errors (e.g. invalid credentials, expired cookies, OTP)."""

    def __init__(self, message: str = "Authentication failed", status_code: Optional[int] = None):
        self.status_code = status_code
        msg = f"[AUTH ERROR] {message}"
        if status_code:
            msg += f" | HTTP {status_code}"
        super().__init__(msg)


class NaukriNetworkError(NaukriClientError):
    """Network connection failures, DNS errors, or socket timeouts."""

    def __init__(self, message: str = "Network request failed", url: Optional[str] = None):
        self.url = url
        msg = f"[NETWORK ERROR] {message}"
        if url:
            msg += f" | URL: {url}"
        super().__init__(msg)


class NaukriParseError(NaukriClientError):
    """Unexpected payload shape, JSON parse error, or missing expected fields."""

    def __init__(self, message: str = "Failed to parse response", response_snippet: Optional[str] = None):
        self.response_snippet = response_snippet
        msg = f"[PARSE ERROR] {message}"
        if response_snippet:
            msg += f" | Response: {response_snippet[:200]}"
        super().__init__(msg)


class NaukriUploadError(NaukriClientError):
    """Resume validation or upload failures."""

    def __init__(self, message: str = "Upload failed", filename: Optional[str] = None):
        self.filename = filename
        msg = f"[UPLOAD ERROR] {message}"
        if filename:
            msg += f" | File: {filename}"
        super().__init__(msg)


# ── System & Integration Exceptions ─────────────────────────────────────────

class ConfigurationError(NaukriAutomationError):
    """Configuration validation or file loading error."""
    pass


class CryptoError(NaukriAutomationError):
    """Cryptographic signing, token generation, or BotGuard execution failure."""
    pass


class AIProviderError(NaukriAutomationError):
    """AI API request, scoring, or response parsing error (OpenRouter / OpenAI)."""
    pass


class TelegramError(NaukriAutomationError):
    """Telegram notification dispatch error."""
    pass


class SchedulerError(NaukriAutomationError):
    """Background scheduler initialization or execution error."""
    pass
