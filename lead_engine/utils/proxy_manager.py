"""Webshare and custom proxy pool rotation."""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import quote

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

FAILURE_DECAY_SECONDS = 1800


@dataclass
class ProxyEntry:
    host: str
    port: int
    username: str
    password: str
    failures: int = 0
    successes: int = 0
    last_failure_at: float = field(default=0.0)

    @property
    def url(self) -> str:
        user = quote(self.username, safe="")
        pwd = quote(self.password, safe="")
        return f"http://{user}:{pwd}@{self.host}:{self.port}"

    @property
    def label(self) -> str:
        return f"{self.host}:{self.port}"


class ProxyManager:
    _instance: Optional["ProxyManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ProxyManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._proxies: List[ProxyEntry] = []
        self._index = 0
        self._request_count = 0
        self._mutex = threading.Lock()
        self._reload()
        self._initialized = True

    def _reload(self) -> None:
        settings = get_settings()
        self._proxies = _parse_proxy_list(settings.proxy_list)
        self._index = 0
        self._request_count = 0
        if settings.proxy_enabled and self._proxies:
            logger.info("Loaded %d proxies", len(self._proxies))

    def _decay_failures_unlocked(self) -> None:
        now = time.monotonic()
        for proxy in self._proxies:
            if (
                proxy.failures > 0
                and proxy.last_failure_at > 0
                and now - proxy.last_failure_at >= FAILURE_DECAY_SECONDS
            ):
                proxy.failures = max(0, proxy.failures - 1)
                proxy.last_failure_at = now

    def _active_pool_unlocked(self) -> List[ProxyEntry]:
        settings = get_settings()
        if not settings.proxy_enabled or not self._proxies:
            return []
        self._decay_failures_unlocked()
        max_failures = settings.proxy_max_failures
        pool = [p for p in self._proxies if p.failures < max_failures]
        if not pool:
            logger.warning("All proxies exhausted — resetting failure counts")
            for proxy in self._proxies:
                proxy.failures = 0
                proxy.last_failure_at = 0.0
            pool = list(self._proxies)
        return pool

    def _current_entry_unlocked(self) -> Optional[ProxyEntry]:
        pool = self._active_pool_unlocked()
        if not pool:
            return None
        return pool[self._index % len(pool)]

    def get_current(self) -> Optional[ProxyEntry]:
        with self._mutex:
            return self._current_entry_unlocked()

    def get_proxies_dict(self, *, channel: str = "discovery") -> Optional[Dict[str, str]]:
        settings = get_settings()
        if not settings.proxy_enabled:
            return None
        if channel in ("discovery", "enrichment") and not settings.proxy_use_for_enf:
            return None
        entry = self.get_current()
        if not entry:
            return None
        return {"http": entry.url, "https": entry.url}

    def after_request(self, *, success: bool, channel: str = "discovery") -> None:
        settings = get_settings()
        if not settings.proxy_enabled:
            return
        if channel in ("discovery", "enrichment") and not settings.proxy_use_for_enf:
            return

        with self._mutex:
            entry = self._current_entry_unlocked()
            if not entry:
                return
            self._request_count += 1
            if success:
                entry.successes += 1
            else:
                entry.failures += 1
                entry.last_failure_at = time.monotonic()
                logger.warning(
                    "Proxy failure: %s (failures=%d)", entry.label, entry.failures
                )
                self._rotate_index_unlocked()
            rotate_every = max(1, settings.proxy_rotate_every)
            if success and self._request_count % rotate_every == 0:
                self._rotate_index_unlocked()

    def rotate(self, force: bool = False) -> None:
        settings = get_settings()
        if not settings.proxy_enabled:
            return
        with self._mutex:
            if force or self._request_count % max(1, settings.proxy_rotate_every) == 0:
                self._rotate_index_unlocked()

    def _rotate_index_unlocked(self) -> None:
        pool = self._active_pool_unlocked()
        if not pool:
            return
        self._index = random.randrange(len(pool))

    def reset_failures(self) -> None:
        with self._mutex:
            for proxy in self._proxies:
                proxy.failures = 0
                proxy.last_failure_at = 0.0
            self._index = 0
            logger.info("Proxy failure counts reset")

    def status(self) -> dict:
        with self._mutex:
            pool = self._active_pool_unlocked()
            current = self._current_entry_unlocked()
            settings = get_settings()
            exhausted = sum(
                1
                for proxy in self._proxies
                if proxy.failures >= settings.proxy_max_failures
            )
            return {
                "enabled": settings.proxy_enabled,
                "enf_proxied": settings.proxy_use_for_enf,
                "total": len(self._proxies),
                "active": len(pool),
                "exhausted": exhausted,
                "current": current.label if current else "Direct",
                "request_count": self._request_count,
            }


def _parse_proxy_list(raw: str) -> List[ProxyEntry]:
    entries: List[ProxyEntry] = []
    if not raw:
        return entries
    for line in raw.replace(",", "\n").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(":")
        if len(parts) == 4:
            host, port, user, password = parts
            entries.append(
                ProxyEntry(
                    host=host,
                    port=int(port),
                    username=user,
                    password=password,
                )
            )
    return entries
