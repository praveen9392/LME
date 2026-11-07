"""
telegram_alert.py — Telegram Notification dispatch module for NopeRi.
Provides backward-compatible functional interface backed by backend.integrations.telegram.TelegramClient.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.integrations.telegram.client import TelegramClient

_client = TelegramClient()


def send(text: str) -> bool:
    return _client.send(text)


def alert_run_started(mode: str = "manual") -> bool:
    return _client.alert_run_started(mode)


def alert_apply(job_title: str, company: str, score: Optional[int], job_id: str) -> bool:
    return _client.alert_apply(job_title, company, score, job_id)


def alert_failed(job_title: str, company: str, error: str) -> bool:
    return _client.alert_failed(job_title, company, error)


def alert_questionnaire(job_title: str, company: str) -> bool:
    return _client.alert_questionnaire(job_title, company)


def alert_run_summary(
    total_found: int,
    applied: int,
    skipped_ext: int,
    skipped_dup: int,
    failed: int,
) -> bool:
    return _client.alert_run_summary(total_found, applied, skipped_ext, skipped_dup, failed)


def alert_profile_updated(headline: str = "") -> bool:
    return _client.alert_profile_updated(headline)


def alert_error(message: str) -> bool:
    return _client.alert_error(message)


def alert_scheduler_started(job_names: List[str]) -> bool:
    return _client.alert_scheduler_started(job_names)


def alert_scheduler_stopped() -> bool:
    return _client.alert_scheduler_stopped()
