"""Discovery — crawl one ENF directory page at a time."""

from __future__ import annotations

import streamlit as st

from database.connection import get_session
from models.country_source import CountrySource
from models.crawl_job import CrawlJob, CrawlJobType
from services.discovery_service import DiscoveryService
from utils.logging import setup_logging
from lead_bootstrap import ensure_lead_engine_db, render_lead_header

ensure_lead_engine_db()
setup_logging()

render_lead_header(
    "Company Discovery",
    "Discover solar installers from ENF — one directory page per click",
)

with get_session() as session:
    country_rows = (
        session.query(CountrySource)
        .filter(CountrySource.is_active.is_(True))
        .order_by(CountrySource.country_name)
        .all()
    )
    countries = [
        {
            "id": c.id,
            "country_name": c.country_name,
            "country_slug": c.country_slug,
        }
        for c in country_rows
    ]

if not countries:
    st.warning("No countries configured. Click **Sync Lead Database** in the sidebar.")
    st.stop()

country_options = {c["country_name"]: c["id"] for c in countries}
selected_country = st.selectbox(
    "Select Country",
    options=list(country_options.keys()),
    help="Pre-loaded countries from ENF installer directory",
)
country_id = country_options[selected_country]

with get_session() as session:
    country_stats = DiscoveryService(session).get_country_stats(country_id)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Next Page", country_stats.get("current_page", 1))
m2.metric("Companies Stored", country_stats.get("total_companies", 0))
m3.metric("Total Pages (est.)", country_stats.get("total_pages") or "—")
last_crawled = country_stats.get("last_crawled_at")
m4.metric(
    "Last Crawled",
    last_crawled.strftime("%Y-%m-%d %H:%M") if last_crawled else "Never",
)

st.divider()
st.subheader("Directory URL")
st.caption(
    "Some countries (e.g. UAE) use a different ENF URL. Paste the correct page 1 link below."
)

auto_url = country_stats.get("auto_directory_url", "")
stored_url = country_stats.get("directory_url", "")
next_fetch_url = country_stats.get("next_fetch_url", "")

if auto_url and auto_url != stored_url:
    st.warning(f"Auto-generated URL (often 404): `{auto_url}`")

url_col, save_col = st.columns([4, 1])
with url_col:
    custom_directory_url = st.text_input(
        "First page directory URL",
        value=stored_url,
        placeholder="https://www.enfsolar.com/directory/installer/UAE",
        label_visibility="collapsed",
    )
with save_col:
    save_url_btn = st.button("Save URL", use_container_width=True)

if save_url_btn:
    if not custom_directory_url.strip():
        st.error("Please enter a directory URL.")
    else:
        with get_session() as session:
            ok, message = DiscoveryService(session).set_directory_url(
                country_id, custom_directory_url.strip(), reset_page=True
            )
        if ok:
            st.success(f"{message} — reset to page 1.")
            st.rerun()
        else:
            st.error(message)

st.info(f"**Next fetch:** `{next_fetch_url}`")
st.divider()

discover_btn = st.button(
    "🔍 Discover Next Page",
    type="primary",
    use_container_width=True,
)

if discover_btn:
    with st.spinner("Crawling one directory page (rate-limited)..."):
        with get_session() as session:
            result = DiscoveryService(session).discover_next_page(country_id)
    if result.success:
        st.success(result.message)
        c1, c2, c3 = st.columns(3)
        c1.metric("Page Processed", result.page_processed)
        c2.metric("New Companies", result.companies_new)
        c3.metric("Duplicates Skipped", result.companies_duplicate)
        if not result.has_next_page:
            st.warning("No further pages detected.")
        st.rerun()
    else:
        st.error(result.message)
        if result.error:
            st.code(result.error)

st.divider()
st.subheader("Recent Discovery Jobs")

with get_session() as session:
    jobs = (
        session.query(CrawlJob)
        .filter(
            CrawlJob.job_type == CrawlJobType.DISCOVERY,
            CrawlJob.country_source_id == country_id,
        )
        .order_by(CrawlJob.created_at.desc())
        .limit(10)
        .all()
    )
    job_rows = [
        {
            "Page": j.page_number,
            "Found": j.companies_found,
            "Status": j.status.value,
            "Started": j.started_at.strftime("%Y-%m-%d %H:%M") if j.started_at else "—",
            "Error": (j.error_message or "")[:80],
        }
        for j in jobs
    ]

if job_rows:
    st.dataframe(job_rows, use_container_width=True, hide_index=True)
else:
    st.caption("No discovery jobs yet for this country.")
