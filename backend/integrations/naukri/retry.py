"""
Exponential backoff retry decorator with randomized jitter for network requests.
"""
from __future__ import annotations

import functools
import random
import time
from typing import Any, Callable, Optional, Type

from backend.core.logging import get_logger

logger = get_logger(__name__)

RETRY_MAX_ATTEMPTS = 5
RETRY_BASE_DELAY = 1.0
RETRY_MAX_DELAY = 60.0
RETRY_MULTIPLIER = 2.0
RETRY_JITTER = 0.3


def _should_retry(result_or_exc: Any) -> bool:
    """Returns True if the result represents a transient error (e.g. 429, 5xx) or exception."""
    if isinstance(result_or_exc, Exception):
        return True
    if hasattr(result_or_exc, "status_code"):
        return result_or_exc.status_code in {429, 500, 502, 503, 504}
    return False


def with_exponential_retry(
    max_attempts: int = RETRY_MAX_ATTEMPTS,
    base_delay: float = RETRY_BASE_DELAY,
    max_delay: float = RETRY_MAX_DELAY,
    multiplier: float = RETRY_MULTIPLIER,
    jitter: float = RETRY_JITTER,
    reraise_as: Optional[Type[Exception]] = None,
    label: str = "request",
) -> Callable:
    """
    Decorator that retries network operations upon transient HTTP errors (429, 5xx)
    or socket/connection exceptions.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = base_delay
            last_exc: Optional[Exception] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)

                    if hasattr(result, "status_code") and _should_retry(result):
                        logger.warning(
                            "[%s] Attempt %d/%d returned HTTP %d, retrying in %.1fs...",
                            label, attempt, max_attempts, result.status_code, delay,
                        )
                        if attempt == max_attempts:
                            return result
                    else:
                        return result

                except Exception as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        logger.error(
                            "[%s] All %d attempts failed. Last error: %s",
                            label, max_attempts, exc,
                        )
                        if reraise_as:
                            raise reraise_as(str(exc)) from exc
                        raise

                    logger.warning(
                        "[%s] Attempt %d/%d failed with %s (%s), retrying in %.1fs...",
                        label, attempt, max_attempts, type(exc).__name__, exc, delay,
                    )

                sleep_time = min(delay * (1 + jitter * random.random()), max_delay)
                time.sleep(sleep_time)
                delay = min(delay * multiplier, max_delay)

            if last_exc:
                raise last_exc

        return wrapper
    return decorator
