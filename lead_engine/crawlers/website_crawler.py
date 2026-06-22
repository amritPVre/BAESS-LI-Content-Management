"""Company website crawler — emails and page text for AI research."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from config.settings import get_settings
from crawlers.base import ENFHTTPClient
from utils.logging import get_logger

logger = get_logger(__name__)

EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)
BLOCKED_EMAIL_FRAGMENTS = (
    "example.com",
    "sentry.io",
    "wixpress.com",
    "domain.com",
    "email.com",
    "yourname",
    "noreply",
    "no-reply",
    "donotreply",
)

# High-yield contact paths — tried only after homepage link discovery.
PRIORITY_CONTACT_PATHS = (
    "/contact",
    "/contact-us",
    "/contacts",
    "/contactus",
    "/get-in-touch",
    "/reach-us",
    "/office",
    "/location",
)

MAX_DISCOVERED_LINKS = 3

# Match nav/footer links pointing to contact pages.
CONTACT_LINK_KEYWORDS = (
    "contact",
    "contact-us",
    "contacts",
    "get-in-touch",
    "reach-us",
    "reach-out",
    "reach us",
    "contact us",
    "office",
    "offices",
    "office-address",
    "location",
    "locations",
    "find-us",
    "find us",
    "info",
    "information",
    "enquiry",
    "enquiries",
    "inquiry",
    "support",
    "customer-service",
    "call us",
    "email us",
)

# Match on-page sections (headings, ids, classes) that usually hold emails.
CONTACT_SECTION_KEYWORDS = (
    "contact us",
    "contact-us",
    "contact",
    "reach us",
    "reach-us",
    "get in touch",
    "office address",
    "our office",
    "office location",
    "locations",
    "find us",
    "enquiry",
    "enquiry form",
    "inquiry",
    "information",
    "call us",
    "email us",
)

CONTACT_ATTR_KEYWORDS = (
    "contact",
    "reach",
    "office",
    "location",
    "enquir",
    "inquir",
    "info",
    "footer",
)

CONTACT_PATH_HINTS = (
    "contact",
    "reach",
    "office",
    "location",
    "info",
    "enquir",
    "inquir",
)


@dataclass
class WebsiteCrawlResult:
    base_url: str = ""
    pages_fetched: List[str] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)
    text_content: str = ""
    error: str | None = None


class WebsiteCrawler(ENFHTTPClient):
    """Fetches a company website and extracts emails plus readable text."""

    def crawl(self, website_url: str) -> WebsiteCrawlResult:
        result = WebsiteCrawlResult(base_url=website_url)
        if not website_url:
            result.error = "No website URL"
            return result

        if not website_url.startswith("http"):
            website_url = f"https://{website_url}"
        result.base_url = website_url

        settings = get_settings()
        max_pages = settings.research_max_pages
        all_emails: Set[str] = set()
        text_chunks: List[str] = []
        fetched_urls: Set[str] = set()
        page_queue: List[str] = [website_url]
        queue_index = 0
        homepage_done = False

        while queue_index < len(page_queue) and len(fetched_urls) < max_pages:
            page_url = page_queue[queue_index]
            queue_index += 1
            normalized = self._normalize_url(page_url)
            if normalized in fetched_urls:
                continue
            if not self._same_domain(website_url, page_url):
                continue

            fetched_urls.add(normalized)
            try:
                html = self.fetch_html(
                    page_url, rate_channel="website", referer=website_url
                )
                result.pages_fetched.append(page_url)
                soup = self.parse_html(html)
                all_emails.update(self._extract_emails(soup, html))
                all_emails.update(self._extract_emails_from_contact_sections(soup))
                text_chunks.append(self._extract_text(soup))
                text_chunks.extend(self._extract_contact_section_text(soup))

                if not homepage_done and normalized == self._normalize_url(website_url):
                    homepage_done = True
                    self._enqueue_contact_targets(
                        page_queue,
                        fetched_urls,
                        website_url,
                        soup,
                        page_url,
                    )
            except Exception as exc:
                logger.warning("Could not fetch %s: %s", page_url, exc)
                if normalized == self._normalize_url(website_url):
                    result.error = str(exc)
                    return result
                if not homepage_done and normalized == self._normalize_url(website_url):
                    homepage_done = True
                    self._enqueue_fallback_contact_paths(
                        page_queue, fetched_urls, website_url
                    )

            if self._should_stop_early(all_emails, result.pages_fetched):
                logger.info(
                    "Early stop for %s after %d pages (%d emails)",
                    website_url,
                    len(result.pages_fetched),
                    len(all_emails),
                )
                break

        result.emails = sorted(all_emails)
        result.text_content = "\n\n".join(text_chunks)[:8000]
        logger.info(
            "Website crawl %s: %d pages, %d emails",
            website_url,
            len(result.pages_fetched),
            len(result.emails),
        )
        return result

    def _enqueue_contact_targets(
        self,
        page_queue: List[str],
        fetched_urls: Set[str],
        website_url: str,
        soup: BeautifulSoup,
        page_url: str,
    ) -> None:
        candidates: List[str] = []
        for discovered in self._discover_contact_urls(soup, page_url):
            if self._normalize_url(discovered) not in fetched_urls:
                candidates.append(discovered)
        candidates = list(dict.fromkeys(candidates))[:MAX_DISCOVERED_LINKS]
        self._enqueue_fallback_contact_paths(
            page_queue, fetched_urls, website_url, candidates

        )

    def _enqueue_fallback_contact_paths(
        self,
        page_queue: List[str],
        fetched_urls: Set[str],
        website_url: str,
        existing: List[str] | None = None,
    ) -> None:
        candidates = list(existing or [])
        for path in PRIORITY_CONTACT_PATHS:
            page_url = urljoin(website_url, path)
            if (
                self._same_domain(website_url, page_url)
                and self._normalize_url(page_url) not in fetched_urls
                and page_url not in candidates
            ):
                candidates.append(page_url)
        for candidate in candidates:
            if candidate not in page_queue:
                page_queue.append(candidate)

    @staticmethod
    def _should_stop_early(emails: Set[str], pages_fetched: List[str]) -> bool:
        if not emails or len(pages_fetched) < 2:
            return False
        return any(
            WebsiteCrawler._looks_like_contact_page(url) for url in pages_fetched[1:]
        )

    @staticmethod
    def _looks_like_contact_page(url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(hint in path for hint in CONTACT_PATH_HINTS)

    @staticmethod
    def _normalize_url(url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        return f"{parsed.scheme}://{parsed.netloc.lower()}{path}"

    def _discover_contact_urls(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        discovered: List[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href or href.startswith(("mailto:", "tel:", "javascript:")):
                continue

            full_url = urljoin(base_url, href).split("#")[0]
            if not self._same_domain(base_url, full_url):
                continue

            path = urlparse(full_url).path.lower()
            link_text = anchor.get_text(" ", strip=True).lower()
            combined = f"{path} {link_text}"
            if self._matches_keywords(combined, CONTACT_LINK_KEYWORDS):
                discovered.append(full_url)

        return list(dict.fromkeys(discovered))

    def _find_contact_sections(self, soup: BeautifulSoup) -> List[Tag]:
        sections: List[Tag] = []
        seen: Set[int] = set()

        for tag in soup.find_all(["section", "div", "article", "footer", "aside", "main"]):
            tag_id = (tag.get("id") or "").lower()
            tag_classes = " ".join(tag.get("class", [])).lower()
            attrs = f"{tag_id} {tag_classes}"
            if self._matches_keywords(attrs, CONTACT_ATTR_KEYWORDS):
                tag_key = id(tag)
                if tag_key not in seen:
                    seen.add(tag_key)
                    sections.append(tag)

        for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            heading_text = heading.get_text(" ", strip=True).lower()
            if not self._matches_keywords(heading_text, CONTACT_SECTION_KEYWORDS):
                continue
            parent = heading.find_parent(["section", "div", "article", "footer", "aside", "main"])
            if parent is None:
                parent = heading.parent
            if parent is None:
                continue
            tag_key = id(parent)
            if tag_key not in seen:
                seen.add(tag_key)
                sections.append(parent)

        return sections

    def _extract_emails_from_contact_sections(self, soup: BeautifulSoup) -> Set[str]:
        emails: Set[str] = set()
        for section in self._find_contact_sections(soup):
            section_html = str(section)
            emails.update(self._extract_emails(section, section_html))
        return emails

    def _extract_contact_section_text(self, soup: BeautifulSoup) -> List[str]:
        chunks: List[str] = []
        for section in self._find_contact_sections(soup):
            text = self._extract_text(section)
            if text:
                chunks.append(text[:2000])
        return chunks

    @staticmethod
    def _matches_keywords(text: str, keywords: Iterable[str]) -> bool:
        lowered = text.lower()
        return any(keyword in lowered for keyword in keywords)

    @staticmethod
    def _same_domain(base: str, target: str) -> bool:
        return urlparse(base).netloc.lower() == urlparse(target).netloc.lower()

    def _extract_emails(self, soup: BeautifulSoup, html: str) -> Set[str]:
        emails: Set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if href.lower().startswith("mailto:"):
                emails.add(href.split(":", 1)[1].split("?")[0].strip())
        for match in EMAIL_PATTERN.findall(html):
            emails.add(match.lower())
        return {e for e in emails if self._is_valid_email(e)}

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        lowered = email.lower()
        if any(fragment in lowered for fragment in BLOCKED_EMAIL_FRAGMENTS):
            return False
        if lowered.endswith((".png", ".jpg", ".gif", ".svg", ".webp")):
            return False
        return True

    @staticmethod
    def _extract_text(soup: BeautifulSoup | Tag) -> str:
        clone = BeautifulSoup(str(soup), "html.parser")
        for tag in clone(["script", "style", "noscript", "svg"]):
            tag.decompose()
        return clone.get_text("\n", strip=True)[:4000]
