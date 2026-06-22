"""Retry decorator with exponential backoff."""

from __future__ import annotations

import time
from functools import wraps
from typing import Callable, Tuple, Type

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)


def retry_on_failure(
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    max_retries: int | None = None,
    backoff_factor: float | None = None,
) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            settings = get_settings()
            retries = max_retries if max_retries is not None else settings.max_retries
            backoff = (
                backoff_factor
                if backoff_factor is not None
                else settings.retry_backoff_factor
            )
            last_error: BaseException | None = None
            for attempt in range(1, retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_error = exc
                    if attempt >= retries:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            func.__name__,
                            retries,
                            exc,
                        )
                        raise
                    wait = backoff ** (attempt - 1)
                    logger.warning(
                        "%s attempt %d/%d failed (%s). Retrying in %.1fs...",
                        func.__name__,
                        attempt,
                        retries,
                        exc,
                        wait,
                    )
                    time.sleep(wait)
            if last_error:
                raise last_error

        return wrapper

    return decorator
