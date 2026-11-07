"""
HTTP session factory providing Chrome TLS/JA3/HTTP2 fingerprint impersonation.
Tries httpcloak first; automatically falls back to curl_cffi on permission or import error.
"""
from __future__ import annotations

import os
from typing import Any

from backend.core.logging import get_logger

logger = get_logger(__name__)


def build_session(use_curl_cffi: bool = False, timeout: int = 30) -> Any:
    """
    Creates an impersonated HTTP session.
    Automatically handles Windows permission quirks by falling back to curl_cffi.
    """
    force_curl = use_curl_cffi or os.getenv("USE_CURL_CFFI", "").lower() in ("true", "1", "yes")

    if not force_curl:
        try:
            import httpcloak
            logger.debug("Initialized session via httpcloak (chrome-latest)")
            return httpcloak.Session(preset="chrome-latest", timeout=timeout)
        except Exception as exc:
            logger.debug("httpcloak session init failed (%s) — falling back to curl_cffi", exc)

    try:
        from curl_cffi import requests as curl_requests
        logger.debug("Initialized session via curl_cffi (chrome124)")
        return curl_requests.Session(impersonate="chrome124", timeout=timeout)
    except Exception as exc:
        logger.warning("curl_cffi failed (%s) — falling back to standard requests", exc)
        import requests
        return requests.Session()
