"""
HTML and JavaScript bundle extractors for form keys and script assets.
"""
from __future__ import annotations

import re
from typing import Callable, List, Optional

from backend.core.constants import (
    APP_JS_RE,
    MNJ_FALLBACK_VERSIONS,
    MNJ_VERSION_RE,
    STATIC_JS_BASE,
)


def extract_form_key2(js_text: str) -> Optional[str]:
    """Extracts formKey2 from JavaScript bundle content."""
    match = re.search(r'key:"initUploader".*?d\s*=\s*"([A-Za-z0-9]+)"', js_text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r'd\s*=\s*"([A-Za-z0-9]{10,})"', js_text)
    return match.group(1) if match else None


def extract_all_js_urls(html: str) -> List[str]:
    """Finds all script src URLs inside an HTML page."""
    return re.findall(r'<script[^>]+src="([^"]*\.js[^"]*)"', html)


def app_js_url(profile_html: str) -> Optional[str]:
    """Extracts the app bundle URL from Naukri profile HTML."""
    m = APP_JS_RE.search(profile_html)
    if not m:
        return None
    url = m.group(1)
    return "https:" + url if url.startswith("//") else url


def mnj_version_from_app_js(app_js: str) -> Optional[str]:
    """Locates the mnj version (e.g. '_v323') from the app JS version dictionary."""
    m = MNJ_VERSION_RE.search(app_js)
    return m.group(1) if m else None


def mnj_url(version: str) -> str:
    """Builds the full URL to the mnj bundle for a given version tag."""
    return f"{STATIC_JS_BASE}mnj{version}.min.js"


def candidate_mnj_urls(profile_html: str, fetch_text_fn: Callable[[str], str]) -> List[str]:
    """
    Returns candidate URLs for the mnj JS bundle:
    Discovered dynamically from app bundle first, followed by known fallbacks.
    """
    urls: List[str] = []
    app_url = app_js_url(profile_html)
    if app_url:
        try:
            js_content = fetch_text_fn(app_url)
            ver = mnj_version_from_app_js(js_content)
            if ver:
                urls.append(mnj_url(ver))
        except Exception:
            pass

    for ver in MNJ_FALLBACK_VERSIONS:
        u = mnj_url(ver)
        if u not in urls:
            urls.append(u)

    return urls
