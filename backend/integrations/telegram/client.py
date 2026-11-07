"""
Telegram notification client using Telegram Bot API.
Sends structured Markdown notifications for runs, applications, errors, and summaries.
"""
from __future__ import annotations

from datetime import datetime
import os
from typing import List, Optional

import requests

from backend.core.logging import get_logger

logger = get_logger(__name__)


class TelegramClient:
    """Dispatches notifications to a configured Telegram chat."""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None) -> None:
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()

    def is_ready(self) -> bool:
        """Returns True if bot token and chat ID are both present."""
        return bool(self.bot_token and self.chat_id)

    def send(self, text: str) -> bool:
        """
        Sends a Markdown message to Telegram chat.
        Never raises exceptions; returns True on success, False on error.
        """
        if not self.is_ready():
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        try:
            res = requests.post(url, json=payload, timeout=10)
            if not res.ok:
                logger.debug("Telegram API error (%d): %s", res.status_code, res.text[:100])
            return res.ok
        except Exception as exc:
            logger.debug("Telegram notification failed: %s", exc)
            return False

    # ── Notification Helper Methods ──────────────────────────────────────────

    def alert_run_started(self, mode: str = "manual") -> bool:
        ts = datetime.now().strftime("%d %b %Y %H:%M")
        return self.send(f"🚀 *NopeRi started* `[{mode}]`\n_{ts}_")

    def alert_apply(self, job_title: str, company: str, score: Optional[int], job_id: str) -> bool:
        score_str = f"{score}/100" if score is not None else "?"
        return self.send(
            f"✅ *Applied*\n"
            f"*{job_title}*\n"
            f"_{company}_\n"
            f"Score: `{score_str}` | ID: `{job_id}`"
        )

    def alert_failed(self, job_title: str, company: str, error: str) -> bool:
        return self.send(
            f"❌ *Apply failed*\n"
            f"*{job_title}* _{company}_\n"
            f"`{str(error)[:200]}`"
        )

    def alert_questionnaire(self, job_title: str, company: str) -> bool:
        return self.send(
            f"📝 *Questionnaire handled*\n"
            f"*{job_title}* _{company}_"
        )

    def alert_run_summary(
        self,
        total_found: int,
        applied: int,
        skipped_ext: int,
        skipped_dup: int,
        failed: int,
    ) -> bool:
        ts = datetime.now().strftime("%d %b %H:%M")
        return self.send(
            f"📊 *Run Summary* _{ts}_\n"
            f"Found `{total_found}` jobs\n"
            f"✅ Applied: `{applied}`\n"
            f"⏭ Skipped ext: `{skipped_ext}` | dup: `{skipped_dup}`\n"
            f"❌ Failed: `{failed}`"
        )

    def alert_profile_updated(self, headline: str = "") -> bool:
        ts = datetime.now().strftime("%d %b %H:%M")
        body = f"\n_{headline}_" if headline else ""
        return self.send(f"👤 *Profile updated* _{ts}_{body}")

    def alert_error(self, message: str) -> bool:
        return self.send(f"🚨 *NopeRi error*\n`{str(message)[:300]}`")

    def alert_scheduler_started(self, job_names: List[str]) -> bool:
        jobs_str = "\n".join(f"  • {n}" for n in job_names)
        return self.send(f"🕐 *Scheduler running*\n{jobs_str}")

    def alert_scheduler_stopped(self) -> bool:
        return self.send("⏹ *Scheduler stopped*")
