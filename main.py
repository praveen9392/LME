"""
main.py — NopeRi API Sandbox and Demonstration Runner.
Demonstrates authentication, job search, recommendations, and application workflows.
"""
from __future__ import annotations

import os
import time

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

from backend.core.config import ConfigManager
from backend.core.logging import configure_logging, get_logger
from backend.services.naukri_service import NaukriService

configure_logging()
logger = get_logger(__name__)


def main() -> None:
    cfg = ConfigManager()
    naukri = NaukriService(cfg)

    print("\n[SANDBOX] Authenticating with Naukri...")
    try:
        session = naukri.authenticate()
        print(f"Authenticated successfully! Bearer Token: {session.bearer_token[:15]}...")
    except Exception as exc:
        print(f"Authentication failed: {exc}")
        return

    print("\n[SANDBOX] Searching for Python Developer jobs in Bangalore...")
    jobs = naukri.search_jobs(keyword="Python developer", location="Bangalore", experience=2)

    if not jobs:
        print("No jobs found matching criteria.")
        return

    print(f"Found {len(jobs)} jobs:\n")
    for idx, job in enumerate(jobs[:5], 1):
        print(f"{idx}. {job.title} @ {job.company} (Exp: {job.experience}, Location: {job.location})")
        print(f"   Tags: {', '.join(job.tags) if job.tags else 'None'}")
        print(f"   URL:  {job.apply_link}\n")


if __name__ == "__main__":
    main()
