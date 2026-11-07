"""
profile_updater.py — Standalone profile headline & resume refresh runner.
Maintains Naukri recruiter search ranking by bumping the candidate's headline and re-uploading the resume.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Allow project root imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.config import ConfigManager
from backend.core.logging import configure_logging, get_logger
from backend.services.profile_service import ProfileService

configure_logging()
logger = get_logger(__name__)


def run_profile_update(cfg: Optional[ConfigManager] = None) -> bool:
    """
    Refreshes profile headline and optionally re-uploads the PDF resume.
    Preserves exact backward-compatible signature.
    """
    service = ProfileService(config_manager=cfg)
    return service.run_update()


if __name__ == "__main__":
    success = run_profile_update()
    sys.exit(0 if success else 1)
