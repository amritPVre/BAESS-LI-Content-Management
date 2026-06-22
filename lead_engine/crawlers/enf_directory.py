"""ENF installer directory page crawler — one page at a time."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urljoin

from crawlers.base import ENFHTTPClient
from config.settings import get_settings
from utils.logging import get_logger
from utils.url_helpers import build_paginated_directory_url, normalize_enf_url

logger = get_logger(__name__)


@dataclass
class DirectoryCompany:
    company_name: str
    enf_profile_url: str


@dataclass
class DirectoryCrawlResult:
    companies: List[DirectoryCompany] = field(default_factory=list)
    current_page: int = 1
    has_next_page: bool = False
    total_pages: Optional[int] = None
    source_url: str = ""


class ENFDirectoryCrawler(ENFHTTPClient):
    """Fetches and parses a single ENF installer directory page."""

    INSTALLER_LINK_PATTERN = re.compile(
        r"directory=installer", re.IGNORECASE
    )

    def crawl_page(
        self,
        country_slug: str,
        page: int,
        *,
        directory_base_url: str | None = None,
    ) -> DirectoryCrawlResult:
        settings = get_settings()
        if directory_base_url:
            url = build_paginated_directory_url(directory_base_url, page)
        elif page <= 1:
            url = f"{settings.enf_base_url}/directory/installer/{country_slug}"
        else:
            url = (
                f"{settings.enf_base_url}/directory/installer/"
                f"{country_slug}?page={page}"
            )
        html = self.fetch_html(url)
        soup = self.parse_html(html)
        companies = self._extract_companies(soup, country_slug)
        pagination = self._extract_pagination(soup, page)
        return DirectoryCrawlResult(
            companies=companies,
            current_page=page,
            has_next_page=pagination["has_next"],
            total_pages=pagination["total_pages"],
            source_url=url,
        )

    def _extract_companies(
        self, soup, country_slug: str
    ) -> List[DirectoryCompany]:
        settings = get_settings()
        seen_urls: set[str] = set()
        companies: List[DirectoryCompany] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not self.INSTALLER_LINK_PATTERN.search(href):
                continue
            if "/directory/" in href:
                continue
            full_url = normalize_enf_url(urljoin(settings.enf_base_url, href))
            if full_url in seen_urls:
                continue
            name = anchor.get_text(" ", strip=True)
            if not name or len(name) < 2:
                continue
            if name.lower() in {"yes", "no", "germany", country_slug.lower()}:
                continue
            seen_urls.add(full_url)
            companies.append(
                DirectoryCompany(company_name=name, enf_profile_url=full_url)
            )

        if not companies:
            companies = self._extract_from_table_rows(soup, country_slug, seen_urls)

        logger.info("Extracted %d companies from directory page", len(companies))
        return companies

    def _extract_from_table_rows(
        self, soup, country_slug: str, seen_urls: set[str]
    ) -> List[DirectoryCompany]:
        settings = get_settings()
        companies: List[DirectoryCompany] = []
        for row in soup.find_all("tr"):
            anchor = row.find("a", href=True)
            if not anchor:
                continue
            href = anchor["href"]
            if "directory=installer" not in href and "/directory/" in href:
                continue
            if href.startswith("/directory/"):
                continue
            full_url = normalize_enf_url(urljoin(settings.enf_base_url, href))
            if "directory=installer" not in full_url and "list=" not in full_url:
                query_suffix = f"?directory=installer&list={country_slug}"
                if "?" not in full_url:
                    full_url = f"{full_url}{query_suffix}"
            if full_url in seen_urls:
                continue
            name = anchor.get_text(" ", strip=True)
            if not name:
                continue
            seen_urls.add(full_url)
            companies.append(
                DirectoryCompany(company_name=name, enf_profile_url=full_url)
            )
        return companies

    def _extract_pagination(self, soup, current_page: int) -> dict:
        max_page = current_page
        has_next = False
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            match = re.search(r"[?&]page=(\d+)", href)
            if match:
                page_num = int(match.group(1))
                max_page = max(max_page, page_num)
                if page_num == current_page + 1:
                    has_next = True
            text = anchor.get_text(strip=True).lower()
            if text in {"next", "›", "»", ">"}:
                has_next = True
        if not has_next and max_page > current_page:
            has_next = True
        return {"has_next": has_next, "total_pages": max_page if max_page > 1 else None}
