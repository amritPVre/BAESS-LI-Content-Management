"""Base HTTP client for conservative ENF crawling."""

from __future__ import annotations

import re
from typing import Optional, Tuple, Type

import requests
from bs4 import BeautifulSoup
from curl_cffi.requests import Session as CurlSession

from config.settings import get_settings
from utils.logging import get_logger
from utils.proxy_manager import ProxyManager
from utils.rate_limit import RateLimiter
from utils.retry import retry_on_failure

logger = get_logger(__name__)


class PageNotFoundError(Exception):
    """Target page missing — proxy delivered the request; do not retry or penalize."""

_HTTP_EXCEPTIONS: Tuple[Type[BaseException], ...] = (requests.RequestException,)
try:
    from curl_cffi.requests import RequestsError

    _HTTP_EXCEPTIONS = (requests.RequestException, RequestsError)
except ImportError:
    pass


class ENFHTTPClient:
    """Shared HTTP client with rate limiting, retries, browser impersonation, and proxies."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._rate_limiter = RateLimiter()
        self._proxy_manager = ProxyManager()

    @retry_on_failure(exceptions=_HTTP_EXCEPTIONS)
    def fetch_html(
        self,
        url: str,
        *,
        rate_channel: str = "discovery",
        referer: str | None = None,
    ) -> str:
        applied_delay = self._rate_limiter.wait(channel=rate_channel)
        proxies = self._proxy_manager.get_proxies_dict(channel=rate_channel)
        proxy_entry = self._proxy_manager.get_current()
        proxy_label = proxy_entry.label if proxy_entry and proxies else "direct"
        timeout = self._settings.request_timeout
        if rate_channel in ("website", "research"):
            timeout = min(timeout, self._settings.research_request_timeout)
        logger.info(
            "Fetching URL: %s (channel=%s, delay=%.1fs, proxy=%s)",
            url,
            rate_channel,
            applied_delay,
            proxy_label,
        )

        headers = {"Accept-Language": "en-US,en;q=0.9"}
        if referer:
            headers["Referer"] = referer
        elif rate_channel in ("discovery", "enrichment"):
            headers["Referer"] = f"{self._settings.enf_base_url}/"

        # Fresh session per request avoids curl_cffi hang when rotating proxies.
        session = CurlSession(impersonate=self._settings.http_impersonate)
        try:
            response = session.get(
                url,
                timeout=timeout,
                proxies=proxies,
                headers=headers,
            )
            html = response.text
            if response.status_code >= 400:
                proxy_fault = self._is_proxy_fault(response.status_code, html)
                self._proxy_manager.after_request(
                    success=not proxy_fault, channel=rate_channel
                )
                if response.status_code in (404, 410):
                    raise PageNotFoundError(
                        f"{response.status_code} Not Found for url: {url}"
                    )
                raise requests.HTTPError(
                    f"{response.status_code} Client Error for url: {url}",
                    response=response,
                )
            if self._is_cloudflare_block(html, response.status_code):
                self._proxy_manager.after_request(
                    success=False, channel=rate_channel
                )
                raise requests.HTTPError(
                    "Blocked by Cloudflare. Proxy rotated — retry or increase delay.",
                    response=response,
                )
            self._proxy_manager.after_request(success=True, channel=rate_channel)
            return html
        except PageNotFoundError:
            raise
        except Exception as exc:
            self._proxy_manager.after_request(
                success=not self._is_connection_proxy_fault(exc),
                channel=rate_channel,
            )
            raise
        finally:
            session.close()

    @staticmethod
    def _is_proxy_fault(status_code: int, html: str) -> bool:
        """True only when the proxy/IP is at fault — not missing pages on the target site."""
        if status_code in (407, 502, 503, 504):
            return True
        if status_code == 403 and ENFHTTPClient._is_cloudflare_block(html, status_code):
            return True
        return False

    @staticmethod
    def _is_connection_proxy_fault(exc: Exception) -> bool:
        if isinstance(exc, PageNotFoundError):
            return False
        if isinstance(exc, requests.HTTPError):
            response = getattr(exc, "response", None)
            if response is not None:
                return ENFHTTPClient._is_proxy_fault(
                    response.status_code, getattr(response, "text", "") or ""
                )
            return False
        if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
            return True
        lowered = str(exc).lower()
        return "proxy" in lowered or "407" in lowered

    @staticmethod
    def _is_cloudflare_block(html: str, status_code: int) -> bool:
        if status_code != 403:
            return False
        lowered = html.lower()
        return "cloudflare" in lowered or "attention required" in lowered

    @staticmethod
    def parse_html(html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    @staticmethod
    def extract_label_value(soup: BeautifulSoup, labels: list[str]) -> Optional[str]:
        """Find a value adjacent to a label in ENF profile layouts."""
        label_pattern = re.compile(
            r"^(" + "|".join(re.escape(label) for label in labels) + r")\s*:?\s*$",
            re.IGNORECASE,
        )
        for tag in soup.find_all(["td", "th", "dt", "div", "span", "label"]):
            text = tag.get_text(" ", strip=True)
            if not text or not label_pattern.match(text):
                continue
            sibling = tag.find_next_sibling()
            if sibling:
                value = sibling.get_text(" ", strip=True)
                if value:
                    return value
            parent = tag.parent
            if parent:
                cells = parent.find_all(["td", "dd", "span", "div"], recursive=False)
                if len(cells) >= 2:
                    value = cells[-1].get_text(" ", strip=True)
                    if value and value != text:
                        return value
        return None
