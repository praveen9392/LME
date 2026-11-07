"""Naukri client adapters and integrations."""
from backend.integrations.naukri.auth import NaukriAuthClient
from backend.integrations.naukri.crypto import generate_nkparam, generate_vid
from backend.integrations.naukri.jobs import NaukriJobApiClient
from backend.integrations.naukri.profile import NaukriProfileClient
from backend.integrations.naukri.session import build_session

__all__ = [
    "NaukriAuthClient",
    "NaukriJobApiClient",
    "NaukriProfileClient",
    "build_session",
    "generate_nkparam",
    "generate_vid",
]
