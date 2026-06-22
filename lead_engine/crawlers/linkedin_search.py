"""LinkedIn profile discovery via privacy-respecting web search."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote_plus, unquote

from crawlers.base import ENFHTTPClient
from utils.logging import get_logger

logger = get_logger(__name__)

LINKEDIN_PROFILE_PATTERN = re.compile(
    r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[a-zA-Z0-9\-_%]+/?",
    re.IGNORECASE,
)


class LinkedInSearchCrawler(ENFHTTPClient):
    """Find public LinkedIn profile URLs using DuckDuckGo HTML search."""

    def find_profile(self, person_name: str, company_name: str) -> Optional[str]:
        if not person_name or not person_name.strip():
            return None
        query = f'site:linkedin.com/in "{person_name.strip()}" "{company_name.strip()}"'
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        try:
            html = self.fetch_html(search_url, rate_channel="research")
            for match in LINKEDIN_PROFILE_PATTERN.findall(html):
                clean = unquote(match.rstrip("/"))
                if "/in/" in clean.lower():
                    logger.info("LinkedIn found for %s: %s", person_name, clean)
                    return clean
            for anchor_match in re.findall(
                r'uddg=([^&"]+)', html, re.IGNORECASE
            ):
                decoded = unquote(anchor_match)
                if "linkedin.com/in/" in decoded.lower():
                    profile = LINKEDIN_PROFILE_PATTERN.search(decoded)
                    if profile:
                        return profile.group(0).rstrip("/")
        except Exception as exc:
            logger.warning("LinkedIn search failed for %s: %s", person_name, exc)
        return None
