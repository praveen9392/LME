"""
Profile Freshness Update Service.
Bumps headline and re-uploads PDF resume to maintain recruiter search ranking.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from backend.core.config import ConfigManager
from backend.core.logging import get_logger
from backend.integrations.telegram.client import TelegramClient
from backend.services.naukri_service import NaukriService

logger = get_logger(__name__)


class ProfileService:
    """Manages scheduled and manual profile headline refreshes and resume updates."""

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        naukri_service: Optional[NaukriService] = None,
        telegram_client: Optional[TelegramClient] = None,
    ) -> None:
        self.cfg = config_manager or ConfigManager()
        self.naukri = naukri_service or NaukriService(self.cfg)
        self.tg = telegram_client or TelegramClient()

    def build_headline(self, profile: dict) -> str:
        """Constructs an optimized recruiter headline string from profile configuration."""
        role = profile.get("role_focus", "AI/ML Engineer")
        if "Engineer" in role:
            role_clean = role
        else:
            role_clean = f"{role} Engineer"
        exp = profile.get("experience_years", 2)
        stack = profile.get("tech_stack", [])
        stack_short = " · ".join(stack[:3]) if stack else "Python · FastAPI · GenAI"
        hl = f"{role_clean} | {exp}+ YOE | {stack_short}"
        return hl[:250]

    def run_update(self) -> bool:
        """
        Executes full profile freshness update:
          1. Authenticate with Naukri
          2. Update profile headline
          3. Upload PDF resume if configured and file exists
          4. Dispatch Telegram notification
        """
        config = self.cfg.config
        profile = config.get("profile", {})
        resume_path = profile.get("resume_path", "").strip()

        logger.info("Executing profile freshness update...")
        try:
            self.naukri.authenticate()

            # 1. Update Headline
            headline = self.build_headline(profile)
            self.naukri.update_profile(headline=headline)
            logger.info("Profile headline updated: %s", headline)

            # 2. Upload Resume if configured
            if resume_path:
                if os.path.exists(resume_path):
                    self.naukri.update_resume(resume_path)
                    logger.info("Resume successfully re-uploaded: %s", resume_path)
                else:
                    logger.warning("Configured resume path does not exist on disk: %s", resume_path)

            # 3. Telegram Alert
            if config.get("telegram", {}).get("enabled"):
                self.tg.alert_profile_updated(headline)

            return True

        except Exception as exc:
            logger.error("Profile update failed: %s", exc)
            if config.get("telegram", {}).get("enabled") and config.get("telegram", {}).get("alerts", {}).get("on_error", True):
                self.tg.alert_error(f"Profile update failed: {exc}")
            return False
