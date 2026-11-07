"""
Naukri Profile & Resume Operations Client.
Handles profile ID discovery, headline/summary updates, and PDF resume re-uploads.
"""
from __future__ import annotations

from io import BytesIO
import random
from typing import Any, Dict, List, Optional, Union

from backend.core.constants import (
    DASHBOARD_URL,
    FILE_VALIDATION_URL,
    HISTORY_URL,
    PROFILE_UPDATE_URL,
    RESUME_UPDATE_URL_TEMPLATE,
    UPLOAD_HEADERS,
)
from backend.core.exceptions import (
    NaukriAuthError,
    NaukriParseError,
    NaukriUploadError,
)
from backend.core.logging import get_logger
from backend.integrations.naukri.auth import NaukriAuthClient
from backend.integrations.naukri.retry import with_exponential_retry
from backend.models.models import (
    ApplicationHistory,
    ApplicationStatus,
    ProfileUpdateResult,
    ResumeUpdateResult,
)

logger = get_logger(__name__)


class NaukriProfileClient:
    """Manages profile modifications, resume updates, and application history."""

    def __init__(self, auth_client: NaukriAuthClient) -> None:
        self.auth = auth_client
        self.session = auth_client.session
        self.profile_id: Optional[str] = None

    # ── Profile ID Discovery ────────────────────────────────────────────────

    @with_exponential_retry(label="fetch_dashboard")
    def _fetch_dashboard(self) -> Any:
        return self.session.get(DASHBOARD_URL, headers=self.auth.build_headers(auth=True))

    def fetch_profile_id(self) -> str:
        """Retrieves the user's unique profileId from the dashboard aggregator API."""
        if self.profile_id:
            return self.profile_id

        res = self._fetch_dashboard()
        if not res.ok:
            raise NaukriParseError(f"Dashboard fetch failed: {res.status_code}")

        data = res.json()
        pid = data.get("profileId") or data.get("dashBoard", {}).get("profileId")
        if not pid:
            raise NaukriParseError("profileId not found in dashboard response", str(data))

        self.profile_id = str(pid)
        logger.debug("Discovered Naukri profileId: %s", self.profile_id)
        return self.profile_id

    # ── Headline & Summary Updates ──────────────────────────────────────────

    @with_exponential_retry(label="update_profile")
    def _update_profile_request(self, headers: Dict[str, str], payload: Dict[str, Any]) -> Any:
        return self.session.post(PROFILE_UPDATE_URL, headers=headers, json=payload)

    def update_profile(
        self,
        headline: Optional[str] = None,
        name: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> ProfileUpdateResult:
        """
        Updates the candidate's resume headline, name, or summary.
        Bumping the headline updates the 'Last Modified' timestamp on Naukri.
        """
        pid = self.fetch_profile_id()
        fields: Dict[str, Any] = {}
        if headline is not None:
            fields["resumeHeadline"] = headline
        if name is not None:
            fields["name"] = name
        if summary is not None:
            fields["summary"] = summary

        if not fields:
            raise ValueError("At least one profile field (headline, name, or summary) must be supplied")

        headers = self.auth.build_headers(
            auth=True,
            extra={
                "accept-encoding": "gzip, deflate, br, zstd",
                "accept-language": "en-US,en;q=0.9",
                "origin": "https://www.naukri.com",
                "referer": "https://www.naukri.com/mnjuser/profile?id=&altresid",
                "systemid": "105",
                "x-http-method-override": "PUT",
                "x-requested-with": "XMLHttpRequest",
            },
        )

        payload = {"profile": fields, "profileId": pid}
        res = self._update_profile_request(headers, payload)
        result = ProfileUpdateResult(profile_id=pid, response=res.json(), status_code=res.status_code)
        if result.is_success:
            logger.info("Successfully updated Naukri profile fields: %s", list(fields.keys()))
        else:
            logger.warning("Profile update returned status %d", res.status_code)
        return result

    # ── Resume File Validation & Upload ─────────────────────────────────────

    @staticmethod
    def _generate_file_key(length: int = 13) -> str:
        chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return "U" + "".join(random.choice(chars) for _ in range(length))

    @with_exponential_retry(label="validate_file")
    def _validate_file_request(self, filename: str, file_bytes: bytes, form_key: str, file_key: str) -> Any:
        # Use multipart upload via session or requests
        import requests
        return requests.post(
            FILE_VALIDATION_URL,
            headers=UPLOAD_HEADERS,
            files={"file": (filename, BytesIO(file_bytes), "application/pdf")},
            data={
                "formKey": form_key,
                "fileName": filename,
                "uploadCallback": "true",
                "fileKey": file_key,
            },
            timeout=30,
        )

    def validate_file(self, file_path_or_buffer: Union[str, Any]) -> tuple[str, str]:
        """Validates PDF file with Naukri's file validation endpoint."""
        form_key = self.auth.get_form_key2()
        file_key = self._generate_file_key()

        if isinstance(file_path_or_buffer, str):
            filename = file_path_or_buffer.replace("\\", "/").split("/")[-1]
            with open(file_path_or_buffer, "rb") as f:
                file_bytes = f.read()
        else:
            file_bytes = file_path_or_buffer.read()
            filename = getattr(file_path_or_buffer, "name", "resume.pdf")

        res = self._validate_file_request(filename, file_bytes, form_key, file_key)
        if not res.ok:
            raise NaukriUploadError(f"File validation failed with HTTP {res.status_code}", filename=filename)

        try:
            resp_json = res.json()
            if file_key not in resp_json and resp_json:
                file_key = next(iter(resp_json))
        except Exception:
            pass

        return file_key, form_key

    @with_exponential_retry(label="update_resume")
    def _update_resume_request(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Any:
        return self.session.post(url, headers=headers, json=payload)

    def update_resume(self, resume_file_path: Union[str, Any]) -> ResumeUpdateResult:
        """Uploads a fresh PDF resume to the user's Naukri profile."""
        pid = self.fetch_profile_id()
        url = RESUME_UPDATE_URL_TEMPLATE.format(profile_id=pid)
        file_key, form_key = self.validate_file(resume_file_path)

        headers = self.auth.build_headers(
            auth=True,
            extra={
                "accept-encoding": "gzip, deflate, br, zstd",
                "accept-language": "en-US,en;q=0.9",
                "content-type": "application/json",
                "origin": "https://www.naukri.com",
                "referer": "https://www.naukri.com/mnjuser/profile",
                "systemid": "105",
                "x-http-method-override": "PUT",
            },
        )

        payload = {"textCV": {"formKey": form_key, "fileKey": file_key}}
        res = self._update_resume_request(url, headers, payload)
        result = ResumeUpdateResult(profile_id=pid, raw_response=res.json(), status_code=res.status_code)
        if result.is_success:
            logger.info("Successfully uploaded new resume for profile %s", pid)
        else:
            logger.warning("Resume update returned status %d", res.status_code)
        return result

    # ── Application History ─────────────────────────────────────────────────

    @with_exponential_retry(label="fetch_history")
    def _fetch_history_request(self, page_size: int, days: int, page_number: int, mobile: bool = False) -> Any:
        headers = {
            "accept": "application/json",
            "appid": "135" if mobile else "107",
            "systemid": "135" if mobile else "107",
            "content-type": "application/json",
            "x-requested-with": "XMLHttpRequest",
            "referer": "https://www.naukri.com/apply/historypage" if mobile else "https://www.naukri.com/myapply/historypage",
            "authorization": f"Bearer {self.auth.naukri_session.bearer_token}",
        }
        if mobile:
            headers["clientid"] = "m0b5"

        params = {"pageSize": page_size, "days": days, "pageNumber": page_number}
        if not mobile:
            params["filterInfo"] = 2

        return self.session.get(HISTORY_URL, headers=headers, params=params)

    def get_application_history(
        self, page_size: int = 10, days: int = 90, page_number: int = 1, mobile: bool = False
    ) -> Dict[str, Any]:
        """Fetches the candidate's Naukri application history from the portal."""
        if not self.auth.naukri_session:
            raise NaukriAuthError("Login required to fetch application history")
        res = self._fetch_history_request(page_size, days, page_number, mobile)
        if not res.ok:
            raise NaukriParseError(f"Failed to fetch application history: {res.status_code}")
        return res.json()

    def parse_history(self, raw: Dict[str, Any]) -> List[ApplicationHistory]:
        """Parses raw JSON history payload into strongly-typed ApplicationHistory models."""
        results: List[ApplicationHistory] = []
        for item in raw.get("applyDetails", []):
            statuses = [
                ApplicationStatus(
                    status_id=s["statusId"],
                    status_value=s["statusValue"],
                    date_time=s["dateTime"],
                )
                for s in item.get("status", [])
            ]
            rating = item.get("companyRating", {})
            results.append(
                ApplicationHistory(
                    job_id=item["jobId"],
                    job_title=item["jobTitle"],
                    company=item["company"],
                    location=item["location"],
                    apply_type=item["applyType"],
                    is_open=str(item.get("isOpen", "")).lower() == "true",
                    ars_score=item.get("arsScore", 0),
                    star_rating=str(item.get("starRating", "0")),
                    job_type=item.get("jobType", ""),
                    statuses=statuses,
                    company_rating=float(rating["AggregateRating"]) if rating and "AggregateRating" in rating else None,
                    logo_path=item.get("logoPath"),
                )
            )
        return results
