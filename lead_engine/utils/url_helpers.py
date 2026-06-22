"""URL normalization helpers for ENF Solar."""

from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from config.settings import get_settings


def build_enf_directory_url(country_slug: str, page: int = 1) -> str:
    settings = get_settings()
    base = f"{settings.enf_base_url}/directory/installer/{country_slug}"
    return build_paginated_directory_url(base, page)


def build_paginated_directory_url(base_url: str, page: int = 1) -> str:
    """Build page N from a stored first-page directory URL."""
    if not base_url:
        return ""
    parsed = urlparse(base_url.strip())
    query = parse_qs(parsed.query, keep_blank_values=True)
    if page <= 1:
        query.pop("page", None)
    else:
        query["page"] = [str(page)]
    flat_query = urlencode(
        [(key, value) for key, values in query.items() for value in values]
    )
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, flat_query, "")
    )


def normalize_enf_url(url: str) -> str:
    """Normalize ENF URLs for deduplication (strip fragments, lowercase host/path)."""
    if not url:
        return ""
    settings = get_settings()
    if url.startswith("/"):
        url = urljoin(settings.enf_base_url, url)
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or parsed.path
    normalized = urlunparse((scheme, netloc, path, "", parsed.query, ""))
    return normalized


def extract_country_from_profile_url(url: str) -> str | None:
    """Extract country from profile query string (?list=Germany)."""
    if "list=" not in url:
        return None
    query = urlparse(url).query
    for part in query.split("&"):
        if part.startswith("list="):
            return part.replace("list=", "").replace("+", " ")
    return None
