"""
Unified Naukri Service Facade.
Provides a unified entry point for authentication, profile updates, and job workflows.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from backend.core.config import ConfigManager
from backend.core.exceptions import NaukriAuthError
from backend.core.logging import get_logger
from backend.integrations.naukri.auth import NaukriAuthClient
from backend.integrations.naukri.jobs import NaukriJobApiClient
from backend.integrations.naukri.profile import NaukriProfileClient
from backend.models.models import Job, NaukriSession, ProfileUpdateResult, ResumeUpdateResult

logger = get_logger(__name__)


class NaukriService:
    """High-level service coordinating authentication, profile management, and job client operations."""

    def __init__(self, config_manager: Optional[ConfigManager] = None) -> None:
        self.cfg = config_manager or ConfigManager()
        self.auth_client = NaukriAuthClient()
        self.profile_client = NaukriProfileClient(self.auth_client)
        self.job_client = NaukriJobApiClient(self.auth_client, config=self.cfg.config)

    def authenticate(self) -> NaukriSession:
        """
        Establishes an authenticated session.
        Prioritizes stored session cookies (nauk_at), falling back to username/password login.
        """
        nauk_at, nauk_rt = self.cfg.get_session_cookies()
        if nauk_at:
            logger.info("Found stored session cookies — attempting session resume")
            self.auth_client = NaukriAuthClient.from_browser_cookies(nauk_at, nauk_rt)
            self.profile_client = NaukriProfileClient(self.auth_client)
            self.job_client = NaukriJobApiClient(self.auth_client, config=self.cfg.config)
            return self.auth_client.naukri_session

        username, password = self.cfg.get_naukri_credentials()
        if not username or not password:
            raise NaukriAuthError("No credentials found. Set NAUKRI_USERNAME and PASSWORD in .env or run setup wizard.")

        self.auth_client.username = username
        self.auth_client.password = password
        session = self.auth_client.login()

        # Cache session tokens for future runs
        nauk_at = self.auth_client.session.cookies.get("nauk_at", "")
        nauk_rt = self.auth_client.session.cookies.get("nauk_rt", "")
        if nauk_at:
            self.cfg.store_session_cookies(nauk_at, nauk_rt)

        self.profile_client = NaukriProfileClient(self.auth_client)
        self.job_client = NaukriJobApiClient(self.auth_client, config=self.cfg.config)
        return session

    def search_jobs(
        self,
        keyword: str,
        location: str = "",
        page: int = 1,
        job_age: int = 3,
        experience: int = 2,
    ) -> List[Job]:
        return self.job_client.search_jobs(
            keyword=keyword,
            location=location,
            page=page,
            job_age=job_age,
            experience=experience,
        )

    def get_recommended_jobs(self) -> List[Job]:
        return self.job_client.get_recommended_jobs()

    def is_external_apply(self, job_id: str) -> bool:
        return self.job_client.is_external_apply(job_id)

    def apply_job(
        self,
        job: Job,
        mandatory_skills: Optional[List[str]] = None,
        optional_skills: Optional[List[str]] = None,
        source: str = "search",
    ) -> Dict[str, Any]:
        return self.job_client.apply_job(
            job=job,
            mandatory_skills=mandatory_skills,
            optional_skills=optional_skills,
            source=source,
        )

    def apply_with_questionnaire(
        self,
        job: Job,
        questionnaire: List[Dict[str, Any]],
        answers: Dict[str, Any],
        mandatory_skills: Optional[List[str]] = None,
        optional_skills: Optional[List[str]] = None,
        source: str = "search",
        sid: str = "",
    ) -> Dict[str, Any]:
        return self.job_client.handle_static_questionnaire_and_apply(
            job=job,
            questionnaire=questionnaire,
            sid=sid,
            mandatory_skills=mandatory_skills,
            optional_skills=optional_skills,
            source=source,
            precomputed_answers=answers,
        )

    def update_profile(
        self,
        headline: Optional[str] = None,
        name: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> ProfileUpdateResult:
        return self.profile_client.update_profile(headline=headline, name=name, summary=summary)

    def update_resume(self, resume_file: Union[str, Any]) -> ResumeUpdateResult:
        return self.profile_client.update_resume(resume_file)
