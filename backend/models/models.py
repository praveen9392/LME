"""
Data models and dataclasses for Naukri Automation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time
from typing import Any, Dict, List, Optional


@dataclass
class NaukriSession:
    """Represents an active, authenticated Naukri user session."""
    bearer_token: str
    cookies: dict
    login_time: float = field(default_factory=time.time)

    def is_expired(self, max_age_seconds: float = 86400) -> bool:
        """Heuristic check on session age."""
        return (time.time() - self.login_time) > max_age_seconds


@dataclass
class FileValidationResult:
    """Result of file validation prior to resume upload."""
    file_key: str
    raw_response: dict
    was_key_remapped: bool = False


@dataclass
class ResumeUpdateResult:
    """Result of uploading/updating an advanced resume."""
    profile_id: str
    raw_response: dict
    status_code: int

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300


@dataclass
class ProfileUpdateResult:
    """Result of updating headline, name, or summary."""
    profile_id: str
    response: Dict[str, Any]
    status_code: int

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300


@dataclass
class Job:
    """Standardized representation of a Naukri job vacancy."""
    job_id: str
    title: str
    company: str
    location: str
    experience: str
    salary: str
    posted_date: str
    apply_link: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    ai_score: Optional[int] = None
    ai_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ApplicationStatus:
    """Status milestone for an application record in history."""
    status_id: int
    status_value: str
    date_time: str


@dataclass
class ApplicationHistory:
    """Historical application item from Naukri apply history."""
    job_id: str
    job_title: str
    company: str
    location: str
    apply_type: str
    is_open: bool
    ars_score: int
    star_rating: str
    job_type: str
    statuses: List[ApplicationStatus]
    company_rating: Optional[float] = None
    logo_path: Optional[str] = None


@dataclass
class RunStats:
    """Aggregated statistics for an agent search & apply execution run."""
    total: int = 0
    allowed: int = 0
    applied: int = 0
    skipped_ext: int = 0
    skipped_dup: int = 0
    failed: int = 0

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)
