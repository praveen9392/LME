"""
Backward-compatibility adapter for NaukriJobClient and JobClient.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.integrations.naukri.auth import NaukriAuthClient
from backend.integrations.naukri.jobs import NaukriJobApiClient
from backend.models.models import Job


class NaukriJobClient:
    """Legacy wrapper delegating to backend.integrations.naukri.NaukriJobApiClient."""

    def __init__(self, login_client: Any, use_pool: bool = False, config: Optional[dict] = None) -> None:
        auth_client = getattr(login_client, "auth", login_client)
        if not isinstance(auth_client, NaukriAuthClient):
            # If a session was passed directly
            auth_wrapper = NaukriAuthClient(session=getattr(login_client, "session", login_client))
            if hasattr(login_client, "naukri_session"):
                auth_wrapper.naukri_session = login_client.naukri_session
            auth_client = auth_wrapper

        self._api = NaukriJobApiClient(auth_client, use_pool=use_pool, config=config)

    def search_jobs(
        self,
        keyword: str,
        location: str = "",
        page: int = 1,
        job_age: int = 3,
        experience: int = 2,
        results_per_page: int = 20,
        lat_long: str = "",
        pages: Optional[int] = None,
    ) -> List[Job]:
        # Handle legacy 'pages' arg if passed
        p = pages if pages is not None else page
        return self._api.search_jobs(
            keyword=keyword,
            location=location,
            page=p,
            job_age=job_age,
            experience=experience,
            results_per_page=results_per_page,
            lat_long=lat_long,
        )

    def get_recommended_jobs(self, pages: int = 1) -> List[Job]:
        return self._api.get_recommended_jobs()

    def get_job_details(self, job_id: str, sid: str = "") -> Dict[str, Any]:
        return self._api.get_job_details(job_id=job_id, sid=sid)

    def is_external_apply(self, job_id: str, sid: str = "") -> bool:
        return self._api.is_external_apply(job_id=job_id, sid=sid)

    def apply_job(
        self,
        job: Job,
        mandatory_skills: Optional[List[str]] = None,
        optional_skills: Optional[List[str]] = None,
        sid: str = "",
        source: str = "recommended",
    ) -> Dict[str, Any]:
        return self._api.apply_job(
            job=job,
            mandatory_skills=mandatory_skills,
            optional_skills=optional_skills,
            sid=sid,
            source=source,
        )

    def handle_static_questionnaire_and_apply(
        self,
        job: Job,
        questionnaire: List[Dict[str, Any]],
        sid: str,
        mandatory_skills: Optional[List[str]] = None,
        optional_skills: Optional[List[str]] = None,
        source: str = "recommended",
        precomputed_answers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._api.handle_static_questionnaire_and_apply(
            job=job,
            questionnaire=questionnaire,
            sid=sid,
            mandatory_skills=mandatory_skills,
            optional_skills=optional_skills,
            source=source,
            precomputed_answers=precomputed_answers,
        )


# Backward-compatibility alias
JobClient = NaukriJobClient
