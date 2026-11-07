"""External service integrations (Naukri, AI, Telegram)."""
from backend.integrations.ai.client import AIClient
from backend.integrations.naukri.auth import NaukriAuthClient
from backend.integrations.naukri.jobs import NaukriJobApiClient
from backend.integrations.naukri.profile import NaukriProfileClient
from backend.integrations.telegram.client import TelegramClient

__all__ = [
    "AIClient",
    "NaukriAuthClient",
    "NaukriJobApiClient",
    "NaukriProfileClient",
    "TelegramClient",
]
