"""Simple rate limiter for conservative crawling."""

from __future__ import annotations

import random
import time
from threading import Lock

from config.settings import get_settings


class RateLimiter:
    """Ensures a minimum delay between consecutive HTTP requests per channel."""

    _instance: "RateLimiter | None" = None
    _lock = Lock()

    def __new__(cls) -> "RateLimiter":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._last_request_at: dict[str, float] = {}
        self._mutex = Lock()
        self._initialized = True

    def wait(self, channel: str = "discovery", delay_seconds: float | None = None) -> float:
        """Wait for rate limit. Returns the delay applied in seconds."""
        settings = get_settings()
        if delay_seconds is None:
            if channel == "enrichment":
                delay_seconds = random.uniform(
                    settings.enrichment_delay_min,
                    settings.enrichment_delay_max,
                )
            elif channel == "website":
                delay_seconds = random.uniform(
                    settings.website_delay_min,
                    settings.website_delay_max,
                )
            elif channel == "research":
                delay_seconds = random.uniform(
                    settings.research_delay_min,
                    settings.research_delay_max,
                )
            else:
                delay_seconds = settings.request_delay_seconds

        with self._mutex:
            last_at = self._last_request_at.get(channel, 0.0)
            elapsed = time.monotonic() - last_at
            sleep_for = delay_seconds - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last_request_at[channel] = time.monotonic()
        return delay_seconds
