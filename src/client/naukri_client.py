"""
Backward-compatibility adapter for NaukriLoginClient.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Union

from backend.integrations.naukri.auth import NaukriAuthClient
from backend.integrations.naukri.profile import NaukriProfileClient
from backend.models.models import (
    ApplicationHistory,
    NaukriSession,
    ProfileUpdateResult,
    ResumeUpdateResult,
)


class NaukriLoginClient:
    """Legacy facade wrapping NaukriAuthClient and NaukriProfileClient."""

    def __init__(self, username: str = "", password: str = "", session: Any = None) -> None:
        self.auth = NaukriAuthClient(username=username, password=password, session=session)
        self.profile = NaukriProfileClient(self.auth)

    @property
    def username(self) -> str:
        return self.auth.username

    @username.setter
    def username(self, val: str) -> None:
        self.auth.username = val

    @property
    def password(self) -> str:
        return self.auth.password

    @password.setter
    def password(self, val: str) -> None:
        self.auth.password = val

    @property
    def session(self) -> Any:
        return self.auth.session

    @property
    def naukri_session(self) -> Optional[NaukriSession]:
        return self.auth.naukri_session

    @naukri_session.setter
    def naukri_session(self, val: Optional[NaukriSession]) -> None:
        self.auth.naukri_session = val

    @property
    def cache(self) -> Dict[str, Any]:
        return self.auth.cache

    @classmethod
    def from_browser_cookies(cls, nauk_at: str, nauk_rt: str = "") -> "NaukriLoginClient":
        client = cls()
        client.auth = NaukriAuthClient.from_browser_cookies(nauk_at, nauk_rt)
        client.profile = NaukriProfileClient(client.auth)
        return client

    def _build_headers(self, auth: bool = False, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        return self.auth.build_headers(auth=auth, extra=extra)

    def login(self) -> NaukriSession:
        return self.auth.login()

    def send_otp(self, username: Optional[str] = None, is_mobile: bool = True) -> Dict[str, Any]:
        return self.auth.send_otp(username=username, is_mobile=is_mobile)

    def verify_otp(self, otp: str, username: Optional[str] = None, is_mobile: bool = True) -> NaukriSession:
        return self.auth.verify_otp(otp=otp, username=username, is_mobile=is_mobile)

    def get_form_key2(self) -> str:
        return self.auth.get_form_key2()

    def get_form_key(self) -> str:
        return self.auth.get_form_key2()

    def fetch_profile_id(self) -> str:
        return self.profile.fetch_profile_id()

    def update_profile(
        self,
        headline: Optional[str] = None,
        name: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> ProfileUpdateResult:
        return self.profile.update_profile(headline=headline, name=name, summary=summary)

    def validate_file(self, file_obj: Any) -> tuple[str, str]:
        return self.profile.validate_file(file_obj)

    def update_resume(self, resume_file: Union[str, Any]) -> ResumeUpdateResult:
        return self.profile.update_resume(resume_file)

    def get_application_history(
        self, page_size: int = 10, days: int = 90, page_number: int = 1, mobile: bool = False
    ) -> Dict[str, Any]:
        return self.profile.get_application_history(page_size, days, page_number, mobile)

    def parse_history(self, raw: Dict[str, Any]) -> list[ApplicationHistory]:
        return self.profile.parse_history(raw)
