"""
Naukri Authentication Client.
Handles login, session cookie resumption, OTP challenges, and form key extraction.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from backend.core.constants import (
    APP_JS_PATTERN,
    DEFAULT_HEADERS,
    FORM_KEY_PATTERNS,
    LOGIN_URL,
    OTP_HEADERS,
    OTP_SEND_URL,
    OTP_VERIFY_URL,
    PROFILE_URL,
)
from backend.core.exceptions import (
    NaukriAuthError,
    NaukriNetworkError,
    NaukriParseError,
)
from backend.core.logging import get_logger
from backend.integrations.naukri.crypto import generate_vid
from backend.integrations.naukri.extractors import (
    candidate_mnj_urls,
    extract_all_js_urls,
    extract_form_key2,
)
from backend.integrations.naukri.retry import with_exponential_retry
from backend.integrations.naukri.session import build_session
from backend.models.models import NaukriSession

logger = get_logger(__name__)


class NaukriAuthClient:
    """Manages authentication, session lifecycle, and security tokens for Naukri."""

    def __init__(self, username: str = "", password: str = "", session: Any = None) -> None:
        self.username = username
        self.password = password
        self.session = session if session is not None else build_session()
        self.naukri_session: Optional[NaukriSession] = None
        self.cache: Dict[str, Any] = {}

    @classmethod
    def from_browser_cookies(cls, nauk_at: str, nauk_rt: str = "") -> "NaukriAuthClient":
        """
        Creates an authenticated client directly from browser cookies (`nauk_at`, `nauk_rt`).
        Bypasses login and CAPTCHA/BotGuard challenges.
        """
        client = cls()
        client.username = ""
        client.password = ""
        client.session = build_session()

        client.session.cookies["nauk_at"] = nauk_at
        if nauk_rt:
            client.session.cookies["nauk_rt"] = nauk_rt

        cookies_dict = {"nauk_at": nauk_at}
        if nauk_rt:
            cookies_dict["nauk_rt"] = nauk_rt

        client.naukri_session = NaukriSession(bearer_token=nauk_at, cookies=cookies_dict)
        logger.info("Resumed authenticated session using pre-existing browser cookies")

        try:
            client.cache["form_key"] = client.get_form_key2()
        except Exception:
            pass

        return client

    def build_headers(self, auth: bool = False, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Constructs headers with appid, systemid, and optional authorization bearer."""
        headers = DEFAULT_HEADERS.copy()
        if auth:
            if not self.naukri_session:
                raise NaukriAuthError("Authentication required — login or provide cookies first")
            headers["authorization"] = f"Bearer {self.naukri_session.bearer_token}"
            headers["systemid"] = "Naukri"
        if extra:
            headers.update(extra)
        return headers

    # ── Login ────────────────────────────────────────────────────────────────

    @with_exponential_retry(label="login_request")
    def _login_request(self) -> Any:
        headers = self.build_headers()
        headers["appid"] = "105"
        headers["systemid"] = "jobseeker"
        try:
            headers["vid"] = generate_vid("nlogin-login")
        except Exception as exc:
            logger.warning("BotGuard vid generation failed (%s) — proceeding without vid header", exc)

        return self.session.post(
            LOGIN_URL,
            headers=headers,
            json={"username": self.username, "password": self.password},
        )

    def login(self) -> NaukriSession:
        """
        Authenticates against Naukri using username and password.
        Returns active NaukriSession with Bearer token.
        """
        if not self.username or not self.password:
            raise NaukriAuthError("Username and password are required for login")

        logger.info("Initiating Naukri login for user: %s", self.username)
        res = self._login_request()

        if not res.ok:
            status = getattr(res, "status_code", 0)
            logger.error("Naukri login failed with HTTP %d", status)
            raise NaukriAuthError("Login failed — invalid credentials or challenge triggered", status_code=status)

        token = self.session.cookies.get("nauk_at")
        if not token:
            try:
                data = res.json()
                token = data.get("token") or data.get("authToken")
            except Exception:
                pass

        if not token:
            raise NaukriAuthError("Login succeeded but no 'nauk_at' session token was received")

        self.naukri_session = NaukriSession(bearer_token=str(token), cookies=dict(self.session.cookies))
        logger.info("Naukri login successful — session established")

        try:
            self.cache["form_key"] = self.get_form_key2()
        except Exception:
            pass

        return self.naukri_session

    # ── OTP Challenge Handling ───────────────────────────────────────────────

    @with_exponential_retry(label="send_otp")
    def _send_otp_request(self, username: str, is_mobile: bool) -> Any:
        payload = {
            "username": username,
            "flowId": "login",
            "isLoginByEmail": not is_mobile,
            "isLoginByMobile": is_mobile,
        }
        headers = self.build_headers()
        headers["appid"] = "100"
        return self.session.post(OTP_SEND_URL, headers=headers, json=payload)

    def send_otp(self, username: Optional[str] = None, is_mobile: bool = True) -> Dict[str, Any]:
        """Requests an OTP code sent via SMS or Email."""
        target = username or self.username
        res = self._send_otp_request(target, is_mobile)
        if not res.ok:
            raise NaukriAuthError(f"Failed to request OTP (HTTP {res.status_code})", status_code=res.status_code)
        try:
            return res.json()
        except Exception:
            return {}

    @with_exponential_retry(label="verify_otp")
    def _verify_otp_request(self, username: str, otp: str, is_mobile: bool) -> Any:
        payload = {
            "username": username,
            "token": otp,
            "flowId": "login",
            "isLoginByEmail": not is_mobile,
            "isLoginByMobile": is_mobile,
        }
        return self.session.post(OTP_VERIFY_URL, headers=OTP_HEADERS, json=payload)

    def verify_otp(self, otp: str, username: Optional[str] = None, is_mobile: bool = True) -> NaukriSession:
        """Verifies OTP code and establishes an authenticated session."""
        target = username or self.username
        res = self._verify_otp_request(target, otp, is_mobile)
        if not res.ok:
            raise NaukriAuthError(f"OTP verification failed (HTTP {res.status_code})", status_code=res.status_code)

        token = self.session.cookies.get("nauk_at")
        if not token:
            try:
                token = res.json().get("authToken") or res.json().get("token")
            except Exception:
                pass

        if not token:
            raise NaukriAuthError("OTP verified successfully but no authentication token was returned")

        self.naukri_session = NaukriSession(bearer_token=str(token), cookies=dict(self.session.cookies))
        logger.info("OTP verification successful — session established")
        return self.naukri_session

    # ── Form Key Extraction ──────────────────────────────────────────────────

    @with_exponential_retry(label="fetch_profile_html")
    def _fetch_profile_html(self) -> Any:
        return self.session.get(PROFILE_URL, headers=self.build_headers(auth=True))

    @with_exponential_retry(label="fetch_js")
    def _fetch_js(self, js_url: str) -> Any:
        return self.session.get(js_url)

    def get_form_key2(self) -> str:
        """Extracts dynamic formKey2 required for resume file uploads."""
        if not self.naukri_session:
            raise NaukriAuthError("Login required to extract formKey2")

        if "form_key" in self.cache:
            return self.cache["form_key"]

        res = self._fetch_profile_html()
        html = getattr(res, "text", "")
        js_urls = extract_all_js_urls(html)

        for js_url in js_urls:
            if "mnj" not in js_url:
                continue
            if js_url.startswith("//"):
                js_url = "https:" + js_url
            try:
                js_content = self._fetch_js(js_url).text
                key = extract_form_key2(js_content)
                if key:
                    self.cache["form_key"] = key
                    return key
            except Exception:
                continue

        # Discovery fallback using candidate_mnj_urls
        for mnj_js_url in candidate_mnj_urls(html, lambda u: self._fetch_js(u).text):
            try:
                js_content = self._fetch_js(mnj_js_url).text
                key = extract_form_key2(js_content)
                if key:
                    self.cache["form_key"] = key
                    return key
            except Exception:
                continue

        raise NaukriParseError("Dynamic formKey2 could not be located in JavaScript bundles")
