"""LinkedIn profile fetch + company web research + AI synthesis."""

import json
import re
import requests
from bs4 import BeautifulSoup

from baess_context import BAESS_PLATFORM_CONTEXT

LINKEDIN_IN_RE = re.compile(r"linkedin\.com/in/[\w\-]+", re.I)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def normalize_linkedin_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    return url.split("?")[0]


def validate_linkedin_url(url: str) -> bool:
    return bool(LINKEDIN_IN_RE.search(url))


def _slug_name(url: str) -> str:
    m = re.search(r"/in/([\w\-]+)", url, re.I)
    if not m:
        return ""
    slug = m.group(1)
    # drop trailing numeric id segments like rajesh-kumar-123456
    parts = slug.split("-")
    while parts and parts[-1].isdigit():
        parts.pop()
    return " ".join(p.capitalize() for p in parts) if parts else slug.replace("-", " ").title()


def fetch_linkedin_profile(url: str) -> dict:
    """Fetch publicly available data from a live LinkedIn profile URL."""
    url = normalize_linkedin_url(url)
    data = {"url": url, "raw_available": False, "inferred_name": _slug_name(url)}

    try:
        resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for key, attr, val in [
            ("og_title", "property", "og:title"),
            ("og_description", "property", "og:description"),
            ("og_image", "property", "og:image"),
            ("meta_description", "name", "description"),
        ]:
            tag = soup.find("meta", attrs={attr: val})
            if tag and tag.get("content"):
                data[key] = tag["content"].strip()

        if soup.title and soup.title.string:
            data["page_title"] = soup.title.string.strip()

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                ld = json.loads(script.string or "")
                data["json_ld"] = ld if isinstance(ld, dict) else ld[0]
            except (json.JSONDecodeError, TypeError, IndexError):
                pass

        # Visible text snippets (auth-wall pages still leak some text)
        for sel in ["h1", ".top-card-layout__title", ".text-body-medium"]:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                data.setdefault("visible_text", []).append(el.get_text(strip=True))

        data["raw_available"] = bool(
            data.get("og_title") or data.get("og_description") or data.get("page_title")
        )
    except Exception as e:
        data["fetch_error"] = str(e)

    return data


def search_company_web(company: str) -> str:
    """Live web snippets about the company (no API key needed)."""
    if not company or len(company) < 2:
        return ""
    try:
        from duckduckgo_search import DDGS

        query = f'"{company}" solar PV BESS EPC company'
        with DDGS() as ddgs:
            hits = list(ddgs.text(query, max_results=6))
        if not hits:
            return ""
        return "\n".join(
            f"• {h.get('title', '')}: {h.get('body', '')}" for h in hits if h.get("body")
        )
    except Exception as e:
        return f"(Web search unavailable: {e})"


RESEARCH_SYSTEM = f"""You are a B2B sales intelligence analyst for solar/BESS LinkedIn outreach to BAESS Labs prospects.

{BAESS_PLATFORM_CONTEXT}

Given scraped LinkedIn profile data and web search results about the prospect's company,
produce a structured research brief aligned to BAESS's products.

Rules:
- Person research: light — role, seniority, likely responsibilities, 1-2 personalisation hooks.
- Company research: deep — what they do, solar/BESS focus, pain points BAESS solves,
  which BAESS product(s) fit (PV AI Designer Pro, PV 3D Designer, BESS Designer, free tools, etc.).
- Use ONLY evidence from the provided data; mark uncertain items as "likely" or "unknown".
- Output ONLY valid JSON, no markdown fences. Schema:
{{
  "name": "string",
  "role": "string",
  "company": "string",
  "location": "string or empty",
  "person_summary": "2-3 sentences",
  "company_research": "4-8 sentences, detailed",
  "recommended_baess_products": ["product 1", "product 2"],
  "outreach_hooks": ["specific hook 1", "specific hook 2", "specific hook 3"],
  "data_confidence": "high|medium|low"
}}"""


def _build_research_prompt(profile_data: dict, web_results: str) -> str:
    parts = [f"LinkedIn URL: {profile_data.get('url', '')}"]
    if profile_data.get("inferred_name"):
        parts.append(f"URL slug name hint: {profile_data['inferred_name']}")
    for k in ("og_title", "og_description", "meta_description", "page_title", "json_ld", "visible_text"):
        if profile_data.get(k):
            parts.append(f"{k}: {profile_data[k]}")
    if profile_data.get("fetch_error"):
        parts.append(f"Fetch note: {profile_data['fetch_error']} (limited public data)")
    if web_results:
        parts.append(f"\nCompany web search results:\n{web_results}")
    else:
        parts.append("\nNo web search results yet — infer company from profile headline/title.")
    return "\n".join(parts)


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def research_prospect(call_ai, profile_data: dict, web_results: str = "") -> dict:
    """Run AI research; returns structured prospect brief."""
    raw = call_ai(RESEARCH_SYSTEM, _build_research_prompt(profile_data, web_results), max_tokens=1200)
    if not raw:
        return {}
    try:
        research = _parse_json(raw)
    except json.JSONDecodeError:
        research = {
            "name": profile_data.get("inferred_name", "Unknown"),
            "role": "",
            "company": "",
            "location": "",
            "person_summary": raw[:500],
            "company_research": "",
            "outreach_hooks": [],
            "data_confidence": "low",
        }
    research["linkedin_url"] = profile_data.get("url", "")
    research["profile_scrape"] = profile_data
    research["web_results"] = web_results
    return research


def run_full_research(url: str, call_ai) -> dict:
    """Fetch profile → web search company → AI synthesis. Single entry point."""
    profile = fetch_linkedin_profile(url)

    # First pass: quick AI parse to get company name for web search
    preview = research_prospect(call_ai, profile, web_results="")
    company = preview.get("company", "")

    web_results = search_company_web(company) if company else ""
    if not web_results and preview.get("role"):
        # try company from og:title pattern "Name - Role - Company | LinkedIn"
        og = profile.get("og_title", "")
        if "|" in og:
            web_results = search_company_web(og.split("|")[0].split("-")[-1].strip())

    if web_results:
        return research_prospect(call_ai, profile, web_results=web_results)
    return preview
