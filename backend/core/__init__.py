"""Core cross-cutting concerns: configuration, logging, exceptions, and constants."""
from backend.core.config import ConfigManager, DEFAULT_CONFIG, DEFAULT_VETO
from backend.core.constants import *
from backend.core.exceptions import *
from backend.core.logging import configure_logging, get_logger

__all__ = [
    "ConfigManager",
    "DEFAULT_CONFIG",
    "DEFAULT_VETO",
    "configure_logging",
    "get_logger",
]
