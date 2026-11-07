"""
Operating system crontab generator and installer for Linux and macOS environments.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Tuple

from backend.core.logging import get_logger

logger = get_logger(__name__)


def install_crontab(cron_line: str) -> Tuple[bool, str]:
    """
    Installs or updates a NopeRi cron entry in the user's crontab on Linux/macOS.
    Returns (success: bool, message: str).
    """
    if sys.platform not in ("linux", "darwin") and not sys.platform.startswith("linux"):
        return False, "Automatic crontab installation is only supported on Linux / macOS systems."

    cron_line = cron_line.strip()
    if not cron_line:
        return False, "No cron expression or command provided."

    try:
        # Read existing crontab
        existing = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
        ).stdout or ""

        # Remove any previous NopeRi apply_agent entries to prevent duplication
        clean_lines = [
            line for line in existing.splitlines()
            if "apply_agent.py" not in line and line.strip()
        ]
        clean_lines.append(cron_line)
        new_crontab = "\n".join(clean_lines) + "\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".crontab", delete=False, encoding="utf-8") as f:
            f.write(new_crontab)
            tmp_path = f.name

        res = subprocess.run(["crontab", tmp_path], capture_output=True, text=True)
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass

        if res.returncode == 0:
            logger.info("Successfully installed crontab line: %s", cron_line)
            return True, "Crontab entry successfully installed."
        else:
            err = res.stderr or "crontab command returned non-zero exit code"
            logger.error("Crontab installation failed: %s", err)
            return False, err

    except Exception as exc:
        logger.error("Failed to install crontab: %s", exc)
        return False, str(exc)
