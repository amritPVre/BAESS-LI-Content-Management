"""Company web research + paste-row parsing for cold email outreach."""

import csv
import io
import json
import re
import sys
import requests
from bs4 import BeautifulSoup
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from linkedin_research import search_company_web, _parse_json
from baess_context import BAESS_PLATFORM_CONTEXT

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

FIELD_ALIASES = {
    "company": {"company", "company_name", "company name", "organisation", "organization", "firm"},
    "country": {"country", "nation", "region"},
    "website": {"website", "url", "site", "web", "domain"},
    "email": {"email", "email_id", "email id", "e-mail", "mail"},
    "name": {"name", "contact", "contact_name", "contact name", "person"},
    "title": {"title", "role", "contact_title", "job title", "designation"},
}

REQUIRED = {"company", "country"}


def _normalize_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    return url.split("?")[0]


def fetch_website(url: str) -> dict:
    """Fetch publicly available data from a company website."""
    url = _normalize_url(url)
    data = {"url": url, "raw_available": False}
    if not url:
        return data

    try:
        resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for key, attr, val in [
            ("og_title", "property", "og:title"),
            ("og_description", "property", "og:description"),
            ("meta_description", "name", "description"),
        ]:
            tag = soup.find("meta", attrs={attr: val})
            if tag and tag.get("content"):
                data[key] = tag["content"].strip()

        if soup.title and soup.title.string:
            data["page_title"] = soup.title.string.strip()

        h1 = soup.find("h1")
        if h1:
            data["h1"] = h1.get_text(strip=True)

        data["raw_available"] = bool(
            data.get("og_title") or data.get("og_description") or data.get("page_title")
        )
    except Exception as e:
        data["fetch_error"] = str(e)

    return data


def search_company(company: str, country: str = "") -> str:
    """Web search tailored to company + country."""
    base = search_company_web(company)
    if country:
        try:
            from duckduckgo_search import DDGS

            query = f'"{company}" {country} solar installer EPC'
            with DDGS() as ddgs:
                hits = list(ddgs.text(query, max_results=4))
            extra = "\n".join(
                f"• {h.get('title', '')}: {h.get('body', '')}" for h in hits if h.get("body")
            )
            if extra:
                return f"{base}\n{extra}" if base else extra
        except Exception:
            pass
    return base


COMPANY_RESEARCH_SYSTEM = f"""You are a B2B sales intelligence analyst for solar/BESS cold email outreach to BAESS Labs prospects.

{BAESS_PLATFORM_CONTEXT}

Given company details, website scrape, and web search results, produce a research brief aligned to BAESS's products.

Rules:
- Company research: DEEP — services, project types, scale, solar/BESS focus, market position,
  pain points BAESS solves (BOQ speed, fragmented tools, feasibility screening, BESS sizing, free calculators),
  which BAESS product(s) fit best.
- Contact research: LIGHT — only if name/title provided; otherwise suggest a role-based greeting.
- Use evidence from provided data; mark gaps as unknown.
- Output ONLY valid JSON, no markdown fences. Schema:
{{
  "company": "string",
  "country": "string",
  "company_type": "C&I EPC contractor|Residential installer|Large-scale developer|BESS integrator|Solar consultant/designer|Other",
  "company_research": "5-10 sentences, detailed",
  "recommended_baess_products": ["product 1", "product 2"],
  "contact_greeting": "Hi [Name] or Hi there / Dear [Role] team",
  "person_note": "1-2 sentences if name/title known, else empty",
  "outreach_hooks": ["hook 1", "hook 2", "hook 3"],
  "data_confidence": "high|medium|low"
}}"""


def _build_company_prompt(row: dict, site_data: dict, web_results: str) -> str:
    parts = [
        f"Company: {row.get('company', '')}",
        f"Country: {row.get('country', '')}",
        f"Website: {row.get('website') or 'not provided'}",
        f"Contact email: {row.get('email') or 'not provided'}",
        f"Contact name: {row.get('name') or 'unknown'}",
        f"Contact title: {row.get('title') or 'unknown'}",
    ]
    for k in ("og_title", "og_description", "meta_description", "page_title", "h1"):
        if site_data.get(k):
            parts.append(f"Website {k}: {site_data[k]}")
    if site_data.get("fetch_error"):
        parts.append(f"Website fetch note: {site_data['fetch_error']}")
    if web_results:
        parts.append(f"\nWeb search results:\n{web_results}")
    return "\n".join(parts)


def research_company_row(row: dict, call_ai) -> dict:
    """Fetch website + web search → AI company brief."""
    company = row.get("company", "").strip()
    country = row.get("country", "").strip()
    website = row.get("website", "").strip()

    site_data = fetch_website(website) if website else {}
    web_results = search_company(company, country)

    raw = call_ai(
        COMPANY_RESEARCH_SYSTEM,
        _build_company_prompt(row, site_data, web_results),
        max_tokens=1200,
    )
    if not raw:
        return {}

    try:
        research = _parse_json(raw)
    except json.JSONDecodeError:
        research = {
            "company": company,
            "country": country,
            "company_type": "Other",
            "company_research": raw[:600],
            "contact_greeting": f"Hi{' ' + row['name'] if row.get('name') else ''}".strip(),
            "person_note": "",
            "outreach_hooks": [],
            "data_confidence": "low",
        }

    research.update({
        "email": row.get("email", ""),
        "name": row.get("name", ""),
        "title": row.get("title", ""),
        "website": website,
        "site_scrape": site_data,
        "web_results": web_results,
    })
    return research


def _map_header(header: list[str]) -> dict[int, str]:
    mapping = {}
    for i, h in enumerate(header):
        key = h.strip().lower()
        for field, aliases in FIELD_ALIASES.items():
            if key in aliases:
                mapping[i] = field
                break
    return mapping


def parse_pasted_rows(text: str, max_rows: int = 10) -> tuple[list[dict], str | None]:
    """Parse CSV/TSV pasted text into prospect rows (max 10 data rows)."""
    text = text.strip()
    if not text:
        return [], "Nothing pasted yet."

    delimiter = "\t" if text.count("\t") >= text.count(",") else ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    rows = [r for r in rows if any(cell.strip() for cell in r)]
    if not rows:
        return [], "No valid rows found."

    col_map = _map_header(rows[0])
    has_header = len(col_map) >= 2 and "company" in col_map.values()
    data_rows = rows[1:] if has_header else rows

    warning = None
    if len(data_rows) > max_rows:
        warning = f"Only the first {max_rows} rows will be processed."
        data_rows = data_rows[:max_rows]

    fields = ["company", "country", "website", "email", "name", "title"]
    parsed = []

    for row in data_rows:
        if has_header:
            record = {field: "" for field in fields}
            for i, val in enumerate(row):
                if i in col_map:
                    record[col_map[i]] = val.strip()
        else:
            record = {
                fields[i]: row[i].strip() if i < len(row) else ""
                for i in range(len(fields))
            }

        if not record.get("company") and not record.get("country"):
            continue
        if not record.get("company") or not record.get("country"):
            return parsed, f"Row missing company or country: {record}"
        parsed.append(record)

    if not parsed:
        return [], "No rows with company + country found."
    return parsed, warning
