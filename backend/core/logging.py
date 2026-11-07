"""
Centralized logging configuration with rotating file handler, colored console output,
and automated secret masking for credentials, tokens, and cookies.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
from typing import Optional

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

DEFAULT_LOG_DIR = Path("backend") / "logs" if Path("backend").exists() else Path("logs")
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "noperi.log"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | [%(name)s:%(funcName)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ── Secret Redaction Filter ──────────────────────────────────────────────────

class SecretMaskingFilter(logging.Filter):
    """
    Sanitizes log messages to ensure sensitive tokens, passwords, and API keys
    never leak into console or log files.
    """

    REDACTION_PATTERNS = [
        # Bearer tokens
        (re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{15,}", re.IGNORECASE), r"\1[REDACTED_TOKEN]"),
        # Cookie values for nauk_at and nauk_rt
        (re.compile(r"(nauk_[ar]t[\"']?\s*[:=]\s*[\"'])[A-Za-z0-9_\-\.]{15,}([\"'])", re.IGNORECASE), r"\1[REDACTED_COOKIE]\2"),
        # OpenRouter API keys
        (re.compile(r"sk-or-v1-[a-f0-9]{32,}", re.IGNORECASE), "sk-or-v1-[REDACTED]"),
        # OpenAI API keys
        (re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}", re.IGNORECASE), "sk-[REDACTED]"),
        # Telegram Bot tokens (in URL or freestanding token)
        (re.compile(r"(bot)?(\d{7,12}:[A-Za-z0-9_\-]{20,})"), r"\1[REDACTED_TG_TOKEN]"),
        # Passwords in dictionaries or JSON strings
        (re.compile(r"(password[\"']?\s*[:=]\s*[\"'])[^\"'\s]{3,}([\"'])", re.IGNORECASE), r"\1[REDACTED_PASSWORD]\2"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact(a) if isinstance(a, str) else a for a in record.args)
        return True

    @classmethod
    def _redact(cls, text: str) -> str:
        for pattern, replacement in cls.REDACTION_PATTERNS:
            text = pattern.sub(replacement, text)
        return text


# ── Color Console Formatter ──────────────────────────────────────────────────

class ColoredConsoleFormatter(logging.Formatter):
    """Adds ANSI terminal colors to log levels when colorama is available."""

    LEVEL_COLORS = {
        logging.DEBUG: Fore.CYAN if HAS_COLORAMA else "",
        logging.INFO: Fore.GREEN if HAS_COLORAMA else "",
        logging.WARNING: Fore.YELLOW if HAS_COLORAMA else "",
        logging.ERROR: Fore.RED if HAS_COLORAMA else "",
        logging.CRITICAL: (Fore.RED + Style.BRIGHT) if HAS_COLORAMA else "",
    }

    def format(self, record: logging.LogRecord) -> str:
        level_color = self.LEVEL_COLORS.get(record.levelno, "")
        reset = Style.RESET_ALL if HAS_COLORAMA else ""
        formatted = super().format(record)
        if level_color and reset:
            levelname = record.levelname
            return formatted.replace(levelname, f"{level_color}{levelname}{reset}", 1)
        return formatted


# ── Central Configuration ────────────────────────────────────────────────────

_is_configured = False


def configure_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = DEFAULT_LOG_FILE,
    enable_console: bool = True,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Configures centralized application logging. Idempotent.
    """
    global _is_configured
    root_logger = logging.getLogger()

    if _is_configured:
        root_logger.setLevel(level)
        return root_logger

    root_logger.setLevel(level)
    # Clear any pre-existing default handlers
    root_logger.handlers.clear()

    masking_filter = SecretMaskingFilter()

    # 1. Console Handler
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(ColoredConsoleFormatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        console_handler.addFilter(masking_filter)
        root_logger.addHandler(console_handler)

    # 2. Rotating File Handler
    if log_file:
        try:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                filename=str(log_path),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)  # Capture DEBUG in file
            file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
            file_handler.addFilter(masking_filter)
            root_logger.addHandler(file_handler)
        except Exception as exc:
            logging.warning("Failed to initialize rotating file logger: %s", exc)

    _is_configured = True
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Convenience getter for child loggers."""
    if not _is_configured:
        configure_logging()
    return logging.getLogger(name)
