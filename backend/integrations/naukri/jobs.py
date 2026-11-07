"""
Naukri Job Search, Recommendation, and Application API Client.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from backend.core.constants import (
    APPLY_JOB_URL,
    APPLY_SRC_MAP,
    JOB_SEARCH_URL,
    RECOMMENDED_JOBS_URL,
)
from backend.core.exceptions import (
    NaukriAuthError,
    NaukriParseError,
)
from backend.core.logging import get_logger
from backend.integrations.naukri.auth import NaukriAuthClient
from backend.integrations.naukri.crypto import generate_nkparam
from backend.integrations.naukri.retry import with_exponential_retry
from backend.models.models import Job

logger = get_logger(__name__)


class NaukriJobApiClient:
    """Communicates with Naukri's search, recommended feeds, and apply workflow endpoints."""

    def __init__(
        self,
        auth_client: NaukriAuthClient,
        use_pool: bool = False,
        config: Optional[dict] = None,
    ) -> None:
        self.auth = auth_client
        self.session = auth_client.session
        self.use_pool = use_pool
        self.pool_idx = 0
        self._profile_config = config.get("profile", {}) if config else {}
        self.pool = [
            "sa9chfJkrXEpn3Zt7rAPaAOb6gAWNSFzzmPQEc6tLSMzytUGPxrGDqiKJyjvBAHGIYPhbDRBDHMad071ZRZlZA=="
        ]

    # ── Internal Helpers ────────────────────────────────────────────────────

    def _parse_job(self, raw: Dict[str, Any]) -> Job:
        """Normalizes raw Naukri JSON job item into a Job dataclass."""
        location = next(
            (p["label"] for p in raw.get("placeholders", []) if p.get("type") == "location"),
            "N/A",
        )
        return Job(
            job_id=str(raw.get("jobId") or raw.get("id") or ""),
            title=raw.get("title") or raw.get("jobTitle") or "N/A",
            company=raw.get("companyName") or raw.get("company") or "N/A",
            location=location,
            experience=raw.get("experienceText") or raw.get("experience") or "N/A",
            salary=raw.get("salaryDetail") or raw.get("salary") or "Not disclosed",
            posted_date=raw.get("footerPlaceholderLabel") or raw.get("postedDate") or "N/A",
            apply_link=raw.get("jdURL") or f"https://www.naukri.com/job-listings-{raw.get('jobId', '')}",
            description=raw.get("jobDescription") or "",
            tags=(
                [t.strip() for t in raw.get("tagsAndSkills", "").split(",") if t.strip()]
                if raw.get("tagsAndSkills")
                else []
            ),
        )

    def _cluster_dates(self) -> Dict[str, str]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        return {
            "apply": now,
            "preference": now,
            "profile": now,
            "similar_jobs": now,
        }

    def _build_seo_key(self, keyword: str, location: str, page: int) -> str:
        kw_slug = (
            keyword.strip()
            .lower()
            .replace(".", "-dot-")
            .replace(" ", "-")
            .replace("+", "-")
            .strip("-")
        )
        if location.strip():
            loc_slug = location.strip().lower().replace(" ", "-")
            return f"{kw_slug}-jobs-in-{loc_slug}-{page}"
        return f"{kw_slug}-jobs-{page}"

    def _get_nkparam(self, page_type: str = "srp") -> str:
        if self.use_pool and self.pool:
            token = self.pool[self.pool_idx % len(self.pool)]
            self.pool_idx += 1
            return token
        return generate_nkparam(page_type)

    def _search_headers(self) -> Dict[str, str]:
        headers = self.auth.build_headers(auth=False)
        headers.update({
            "authority": "www.naukri.com",
            "accept": "application/json",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9",
            "appid": "109",
            "gid": "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE",
            "nkparam": self._get_nkparam("srp"),
        })
        return headers

    # ── Job Details ─────────────────────────────────────────────────────────

    @with_exponential_retry(label="get_job_details")
    def _fetch_job_details_request(self, url: str, headers: Dict[str, str], params: Dict[str, Any]) -> Any:
        return self.session.get(url, headers=headers, params=params)

    def get_job_details(self, job_id: str, sid: str = "") -> Dict[str, Any]:
        """Fetches detailed job view including apply redirect URLs."""
        if not job_id:
            raise ValueError("job_id is required")

        if not sid:
            sid = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "0000000"

        url = f"https://www.naukri.com/jobapi/v4/job/{job_id}"
        params = {
            "microsite": "y",
            "brandedConsultantJd": "true",
            "amboxConsultantData": "true",
            "src": "jobsearchDesk",
            "sid": sid,
        }

        headers = self.auth.build_headers(auth=True)
        headers.update({
            "appid": "121",
            "systemid": "Naukri",
            "clientid": "d3skt0p",
            "accept": "application/json",
            "gid": "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE",
            "nkparam": generate_nkparam(job_id),
            "referer": "https://www.naukri.com/",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
        })

        res = self._fetch_job_details_request(url, headers, params)
        if res.status_code in (401, 403):
            raise NaukriAuthError(f"Job details authentication failed ({res.status_code})", status_code=res.status_code)
        if not res.ok:
            raise NaukriParseError(f"Job details fetch failed: {res.status_code}")

        try:
            data = res.json()
            if not isinstance(data, dict) or not isinstance(data.get("jobDetails"), dict):
                raise NaukriParseError("Job details response payload missing 'jobDetails'")
            return data
        except Exception as exc:
            raise NaukriParseError(f"Invalid JSON returned for job details: {exc}")

    def is_external_apply(self, job_id: str, sid: str = "") -> bool:
        """Returns True if the job requires external application on a company careers portal."""
        try:
            details = self.get_job_details(job_id, sid).get("jobDetails", {})
            return bool(details.get("applyRedirectUrl") or details.get("companyApplyUrl"))
        except Exception:
            return False

    # ── Job Application Submissions ─────────────────────────────────────────

    @with_exponential_retry(label="apply_job")
    def _apply_request(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Any:
        return self.session.post(url, headers=headers, json=payload)

    def apply_job(
        self,
        job: Job,
        mandatory_skills: Optional[List[str]] = None,
        optional_skills: Optional[List[str]] = None,
        sid: str = "",
        source: str = "recommended",
    ) -> Dict[str, Any]:
        """Submits 1-click application for a job."""
        if not job.job_id:
            raise ValueError("Invalid job_id")

        if not sid:
            sid = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "0000000"

        apply_src, logstr_template = APPLY_SRC_MAP.get(source, APPLY_SRC_MAP["recommended"])
        logstr = logstr_template.format(sid=sid)

        payload = {
            "strJobsarr": [job.job_id],
            "logstr": logstr,
            "flowtype": "show",
            "crossdomain": True,
            "jquery": 1,
            "rdxMsgId": "",
            "chatBotSDK": True,
            "mandatory_skills": mandatory_skills or [],
            "optional_skills": optional_skills or [],
            "applyTypeId": "107",
            "closebtn": "y",
            "applySrc": apply_src,
            "sid": sid,
            "mid": "",
        }

        headers = self.auth.build_headers(auth=True)
        headers.update({
            "appid": "121",
            "systemid": "jobseeker",
            "clientid": "d3skt0p",
            "accept": "application/json",
        })

        res = self._apply_request(APPLY_JOB_URL, headers, payload)
        if res.status_code in (401, 403):
            raise NaukriAuthError(f"Apply failed due to auth error ({res.status_code})", status_code=res.status_code)
        if not res.ok:
            raise NaukriParseError(f"Apply request failed with HTTP {res.status_code}")

        try:
            return res.json()
        except Exception as exc:
            raise NaukriParseError(f"Invalid JSON returned on apply: {exc}")

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
        """Submits job application along with answers to screening questionnaire questions."""
        pc = self._profile_config
        exp_str = str(pc.get("experience_years", 2))
        profile_data = {
            "current_ctc": pc.get("current_ctc", "5"),
            "expected_ctc": pc.get("expected_ctc", "7"),
            "exp_total": exp_str,
            "exp_node": exp_str,
            "exp_python": exp_str,
            "notice_days": pc.get("notice_days", 30),
            "skills": [t.lower() for t in pc.get("tech_stack", ["node", "python", "aws", "docker"])],
        }

        def build_smart_answers(q_list: List[Dict[str, Any]], prof: Dict[str, Any]) -> Dict[str, Any]:
            answers = {}
            for q in q_list:
                qid = q["questionId"]
                qtext = (q.get("questionName") or "").lower()
                qtype = (q.get("questionType") or "").lower()
                options = q.get("answerOption") or {}

                if qtype == "text box":
                    if "current ctc" in qtext:
                        ans = prof["current_ctc"]
                    elif "expected ctc" in qtext:
                        ans = prof["expected_ctc"]
                    elif "experience" in qtext:
                        if "node" in qtext:
                            ans = prof["exp_node"]
                        elif "python" in qtext:
                            ans = prof["exp_python"]
                        else:
                            ans = prof["exp_total"]
                    elif "notice" in qtext:
                        ans = str(prof["notice_days"])
                    else:
                        ans = "1"
                else:
                    if options:
                        chosen = list(options.keys())[0]
                        for k, v in options.items():
                            if "yes" in v.lower():
                                chosen = k
                                break
                        ans = [chosen]
                    else:
                        ans = "1"
                answers[qid] = ans
            return answers

        answers = precomputed_answers if precomputed_answers else build_smart_answers(questionnaire, profile_data)
        apply_src, logstr_template = APPLY_SRC_MAP.get(source, APPLY_SRC_MAP["recommended"])
        logstr = logstr_template.format(sid=sid)

        payload = {
            "strJobsarr": [job.job_id],
            "logstr": logstr,
            "flowtype": "show",
            "crossdomain": True,
            "jquery": 1,
            "rdxMsgId": "",
            "chatBotSDK": True,
            "mandatory_skills": mandatory_skills or [],
            "optional_skills": optional_skills or [],
            "applyTypeId": "107",
            "closebtn": "y",
            "applySrc": apply_src,
            "sid": sid,
            "mid": "",
            "applyData": {
                job.job_id: {
                    "answers": answers,
                }
            },
        }

        headers = self.auth.build_headers(auth=True)
        res = self._apply_request(APPLY_JOB_URL, headers, payload)
        if not res.ok:
            return {"success": False, "error": getattr(res, "text", "Apply request failed")}
        try:
            return res.json()
        except Exception:
            return {"success": False, "error": "Invalid JSON response"}

    # ── Job Feeds ───────────────────────────────────────────────────────────

    def get_recommended_jobs(self) -> List[Job]:
        """Fetches personalized job feed based on candidate's Naukri profile."""
        headers = self.auth.build_headers(auth=True)
        res = self.session.post(
            RECOMMENDED_JOBS_URL,
            headers=headers,
            json={
                "clusterId": None,
                "src": "recommClusterApi",
                "clusterSplitDate": self._cluster_dates(),
            },
        )
        if not res.ok:
            raise NaukriParseError(f"Recommended jobs fetch failed: {res.status_code}")

        data = res.json()
        raw_jobs = data.get("jobDetails") or []
        return [self._parse_job(j) for j in raw_jobs]

    def search_jobs(
        self,
        keyword: str,
        location: str = "",
        page: int = 1,
        job_age: int = 3,
        experience: int = 2,
        results_per_page: int = 20,
        lat_long: str = "",
    ) -> List[Job]:
        """Searches jobs matching keyword, location, and experience criteria."""
        seo_key = self._build_seo_key(keyword, location, page)
        params = {
            "noOfResults": results_per_page,
            "urlType": "search_by_keyword",
            "searchType": "adv",
            "keyword": keyword,
            "k": keyword,
            "pageNo": page,
            "experience": experience,
            "jobAge": job_age,
            "nignbevent_src": "jobsearchDeskGNB",
            "seoKey": seo_key,
            "src": "jobsearchDesk",
            "latLong": lat_long,
        }

        res = self.session.get(JOB_SEARCH_URL, headers=self._search_headers(), params=params)
        if res.status_code == 403:
            raise NaukriAuthError("403 Forbidden — nkparam token expired or blocked", status_code=403)
        if res.status_code == 406:
            logger.debug("406 Validation error for keyword '%s'", keyword)
            return []
        if not res.ok:
            raise NaukriParseError(f"Job search failed: {res.status_code}")

        data = res.json()
        raw_jobs = data.get("jobDetails") or data.get("jobs") or []
        return [self._parse_job(j) for j in raw_jobs]
