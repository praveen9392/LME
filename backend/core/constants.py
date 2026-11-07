"""
Central constants for Naukri API endpoints, RSA public keys, and extraction regexes.
"""
from __future__ import annotations

import re

# ── Authentication Endpoints ───────────────────────────────────────────────
LOGIN_URL = "https://www.naukri.com/central-login-services/v1/login"
OTP_VERIFY_URL = "https://www.naukri.com/central-login-services/v0/otp-login"
OTP_SEND_URL = "https://www.naukri.com/central-login-services/v1/otp"

# ── Profile & Resume Endpoints ─────────────────────────────────────────────
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"
PROFILE_UPDATE_URL = (
    "https://www.naukri.com/cloudgateway-mynaukri/resman-aggregator-services"
    "/v1/users/self/fullprofiles"
)
DASHBOARD_URL = (
    "https://www.naukri.com/cloudgateway-mynaukri/resman-aggregator-services"
    "/v0/users/self/dashboard"
)
FILE_VALIDATION_URL = "https://filevalidation.naukri.com/file"
RESUME_UPDATE_URL_TEMPLATE = (
    "https://www.naukri.com/cloudgateway-mynaukri/resman-aggregator-services"
    "/v0/users/self/profiles/{profile_id}/advResume"
)

# ── Job Search & Workflow Endpoints ─────────────────────────────────────────
JOB_SEARCH_URL = "https://www.naukri.com/jobapi/v3/search"
RECOMMENDED_JOBS_URL = "https://www.naukri.com/jobapi/v2/search/recom-jobs"
APPLY_JOB_URL = (
    "https://www.naukri.com/cloudgateway-workflow/workflow-services"
    "/apply-workflow/v1/apply"
)
HISTORY_URL = (
    "https://www.naukri.com/cloudgateway-apply/whtma-services/v0/applyapi/v5/history"
)

# ── Third-Party AI Endpoints ────────────────────────────────────────────────
OPENROUTER_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENAI_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"

# ── Static JS Assets ────────────────────────────────────────────────────────
STATIC_JS_BASE = "https://static.naukimg.com/s/5/105/j/"

# ── Cryptography: RSA Public Keys ───────────────────────────────────────────
# RSA key for nkparam signing
PUBLIC_KEY = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALrlQ+djR0RjJwBF1xuisHmdFv334MIm\n"
    "K6LgzJhmLhN7B5yuEyaKoasgXQk3+OQglsOaBxEJ0j5PcTL3nbOvt80CAwEAAQ==\n"
    "-----END PUBLIC KEY-----"
)

# BotGuard SDK Public Key
BOTGUARD_APP_ID = "105"
BOTGUARD_PUBLIC_KEY = (
    "MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALbx2oNW1OsL+zv+GK4Ed70m4gr6sBjp"
    "zj1PCmLAYs3dQph0IS/DFWXMDN//CyC46DgSJZJZdaxT0xskFBIKNSMCAwEAAQ=="
)

# ── Regex Patterns ─────────────────────────────────────────────────────────
FORM_KEY_PATTERNS = [
    re.compile(r'formKey\s*[:=]\s*["\']([A-Za-z0-9]{8,})["\']'),
    re.compile(r'"formKey"\s*:\s*"([A-Za-z0-9]{8,})"'),
]

APP_JS_PATTERN = re.compile(r'<script[^>]+src="([^"]*app_v\d+\.min\.js[^"]*)"')
APP_JS_RE = re.compile(
    r'src="((?:https?:)?//static\.naukimg\.com/s/5/105/j/app_v\d+\.min\.js)"'
)
MNJ_VERSION_RE = re.compile(r'\bmnj\s*:\s*"(_v\d+)"')
MNJ_FALLBACK_VERSIONS = ("_v323", "_v299")

# ── Apply Tracking & Sources ───────────────────────────────────────────────
APPLY_SRC_MAP = {
    "recommended": ("drecomm_apply", "--drecomm_apply-1-F-0-1--{sid}-"),
    "search": ("srp", "--srp-1-F-0-1--{sid}-"),
}

# ── Headers ────────────────────────────────────────────────────────────────
DEFAULT_HEADERS = {
    "accept": "application/json",
    "appid": "103",
    "clientid": "d3skt0p",
    "content-type": "application/json",
    "referer": "https://www.naukri.com/",
    "systemid": "jobseeker",
    "x-requested-with": "XMLHttpRequest",
}

UPLOAD_HEADERS = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "appid": "105",
    "origin": "https://www.naukri.com",
    "referer": "https://www.naukri.com/",
    "systemid": "fileupload",
}

OTP_HEADERS = {
    "accept": "application/json",
    "appid": "100",
    "content-type": "application/json",
    "referer": "https://www.naukri.com/nlogin/login?URL=//www.naukri.com/mnjuser/recommendedjobs",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "systemid": "jobseeker",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
    "x-requested-with": "XMLHttpRequest",
}
