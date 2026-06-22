"""ENF company profile page crawler — one profile at a time."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import urljoin

from crawlers.base import ENFHTTPClient
from config.settings import get_settings
from utils.logging import get_logger
from utils.url_helpers import extract_country_from_profile_url

logger = get_logger(__name__)


@dataclass
class ProfileCrawlResult:
    company_name: str = ""
    website: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    battery_storage: Optional[str] = None
    installation_size: Optional[str] = None
    operating_area: Optional[str] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)
    source_url: str = ""


class ENFProfileCrawler(ENFHTTPClient):
    """Fetches and parses a single ENF company profile page."""

    def crawl_profile(self, profile_url: str) -> ProfileCrawlResult:
        html = self.fetch_html(profile_url, rate_channel="enrichment")
        soup = self.parse_html(html)
        result = ProfileCrawlResult(source_url=profile_url)
        result.company_name = self._extract_company_name(soup)
        result.website = self._extract_website(soup)
        result.phone = self.extract_label_value(
            soup, ["Telephone", "Phone", "Tel", "Mobile"]
        )
        result.address = self.extract_label_value(
            soup, ["Address", "Office Address", "Location"]
        )
        result.country = (
            self.extract_label_value(soup, ["Country", "Nation"])
            or extract_country_from_profile_url(profile_url)
        )
        result.battery_storage = self.extract_label_value(
            soup, ["Battery Storage", "Battery", "Storage"]
        )
        result.installation_size = self.extract_label_value(
            soup,
            [
                "Installation Size",
                "Installation size",
                "Project Size",
                "System Size",
            ],
        )
        result.operating_area = self._extract_operating_area(soup)
        result.extra_data = self._extract_extra_fields(soup)
        logger.info("Parsed profile for: %s", result.company_name or profile_url)
        return result

    def _extract_company_name(self, soup) -> str:
        h1 = soup.find("h1")
        if h1:
            name = h1.get_text(" ", strip=True)
            if name:
                return name
        title = soup.find("title")
        if title:
            text = title.get_text(strip=True)
            return re.sub(r"\s*\|.*$", "", text).strip()
        return ""

    def _extract_website(self, soup) -> Optional[str]:
        website = self.extract_label_value(soup, ["Website", "Web", "Homepage"])
        if website:
            return self._normalize_website_url(website)

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            text = anchor.get_text(strip=True)
            if not href.startswith("http"):
                continue
            if self._is_external_website(href):
                text_lower = text.lower()
                if text_lower in {
                    "website",
                    "visit website",
                    "company website",
                    "web",
                    "homepage",
                } or text.startswith("http"):
                    return href

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if self._is_external_website(href):
                return href
        return None

    @staticmethod
    def _normalize_website_url(website: str) -> str:
        website = website.strip()
        if website.startswith("http"):
            return website
        return urljoin("https://", website)

    @staticmethod
    def _is_external_website(url: str) -> bool:
        lowered = url.lower()
        if not lowered.startswith("http"):
            return False
        blocked_hosts = (
            "enfsolar.com",
            "enf.com.cn",
            "enfrecycling.com",
            "facebook.com",
            "linkedin.com",
            "twitter.com",
            "x.com",
            "instagram.com",
            "youtube.com",
        )
        return not any(host in lowered for host in blocked_hosts)

    def _extract_operating_area(self, soup) -> Optional[str]:
        area = self.extract_label_value(
            soup,
            [
                "Countries Operating In",
                "Operating Area",
                "Operating Countries",
                "Service Area",
                "Area",
            ],
        )
        if area:
            return area
        for heading in soup.find_all(["h2", "h3", "h4", "strong"]):
            text = heading.get_text(strip=True).lower()
            if "operating" in text or "countries" in text:
                sibling = heading.find_next(["p", "div", "td", "ul"])
                if sibling:
                    return sibling.get_text(" ", strip=True)
        return None

    def _extract_extra_fields(self, soup) -> Dict[str, Any]:
        extra: Dict[str, Any] = {}
        for label in [
            "Starting Date",
            "Employees",
            "Stock Code",
            "Service Coverage",
            "Email",
        ]:
            value = self.extract_label_value(soup, [label])
            if value:
                extra[label.lower().replace(" ", "_")] = value
        return extra
