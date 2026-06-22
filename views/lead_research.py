"""Phase 3 — Company research: scraped emails and key people from websites."""

from __future__ import annotations

import time
from datetime import timedelta

import streamlit as st
from sqlalchemy.orm import joinedload

from config.settings import get_settings
from database.connection import get_session
from models.company_contact import CompanyContact
from models.crawl_job import CrawlJob, CrawlJobType
from services.company_service import CompanyService
from services.research_service import ResearchService
from utils.logging import setup_logging
from utils.proxy_manager import ProxyManager
from lead_bootstrap import ensure_lead_engine_db, render_lead_header, get_ai_provider

ensure_lead_engine_db()
setup_logging()

settings = get_settings()
ai_provider = get_ai_provider()
COOLDOWN_KEY = "research_cooldown_until"
BATCH_SIZE = settings.research_batch_size
COOLDOWN_SECONDS = settings.research_cooldown_seconds


def _cooldown_remaining() -> float:
    until = st.session_state.get(COOLDOWN_KEY)
    if not until:
        return 0.0
    return max(0.0, until - time.time())


def _start_cooldown() -> None:
    st.session_state[COOLDOWN_KEY] = time.time() + COOLDOWN_SECONDS


def _format_duration(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m {secs:02d}s"


render_lead_header(
    "Company Research (Phase 3)",
    "Website email scraping + DeepSeek key people identification",
)

proxy_status = ProxyManager().status()
if proxy_status["enabled"]:
    st.sidebar.markdown("**Proxy Pool**")
    st.sidebar.caption(
        f"Active: {proxy_status['active']}/{proxy_status['total']} · "
        f"Current: `{proxy_status['current']}`"
    )

if not settings.deepseek_api_key and ai_provider == "deepseek":
    st.error(
        "Set `DEEPSEEK_API_KEY` in your `.env` or Streamlit secrets to run AI research."
    )

with get_session() as session:
    research_service = ResearchService(session, ai_provider=ai_provider)
    stats = research_service.get_research_stats()
    countries = ["All"] + CompanyService(session).get_countries()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Ready to Research", stats["pending"])
m2.metric("Researched", stats["completed"])
m3.metric("Awaiting Enrichment", stats.get("awaiting_enrichment", 0))
m4.metric("Contacts Found", stats["total_contacts"])
m5.metric("Key People", stats["with_people"])

st.info(
    f"Processes up to **{BATCH_SIZE} enriched companies** per run (must have a website). "
    f"For each company: fast crawl of **contact pages** (max {settings.research_max_pages} pages, "
    f"stops early when emails found) → **DeepSeek** extracts up to **5 key people** (name + title). "
    f"No LinkedIn search here — that comes in a later discovery step. "
    f"Target: **~1–2 min/company**. "
    f"**{COOLDOWN_SECONDS // 60} min** cooldown after each batch."
)

st.divider()

filter_country = st.selectbox("Filter by Country", countries)

with get_session() as session:
    country_filter = None if filter_country == "All" else filter_country
    batch_preview = ResearchService(
        session, ai_provider=ai_provider
    ).preview_batch(country=country_filter)

if batch_preview:
    st.markdown(f"**Next research batch ({len(batch_preview)} companies):**")
    st.dataframe(batch_preview, use_container_width=True, hide_index=True)
else:
    st.success("No companies pending research — enrich companies with websites first.")

remaining = _cooldown_remaining()
if remaining > 0:

    @st.fragment(run_every=timedelta(seconds=5))
    def cooldown_banner() -> None:
        left = _cooldown_remaining()
        if left > 0:
            st.warning(f"Cooldown — locked for **{_format_duration(left)}**")
        else:
            st.session_state.pop(COOLDOWN_KEY, None)
            st.rerun()

    cooldown_banner()

button_disabled = (
    remaining > 0
    or not batch_preview
    or (ai_provider == "deepseek" and not settings.deepseek_api_key)
)
button_label = (
    f"Cooling down ({_format_duration(remaining)})"
    if remaining > 0
    else f"🔬 Research Next {min(len(batch_preview), BATCH_SIZE)} Companies"
    if batch_preview
    else "Nothing to Research"
)

research_btn = st.button(
    button_label,
    type="primary",
    use_container_width=True,
    disabled=button_disabled,
)

if research_btn and batch_preview and remaining <= 0:
    progress = st.progress(0, text="Starting research batch...")
    status = st.empty()
    all_rows = []

    def on_progress(current: int, total: int, name: str) -> None:
        progress.progress(current / total, text=f"Researching {current}/{total}: {name}")
        status.info(f"**{name}** — scraping emails and identifying key people...")

    with get_session() as session:
        batch = ResearchService(session, ai_provider=ai_provider).research_batch(
            country=country_filter,
            batch_size=BATCH_SIZE,
            on_progress=on_progress,
        )

    progress.progress(1.0, text="Batch complete")
    status.empty()

    if batch.processed > 0:
        _start_cooldown()
        st.success(batch.message)
        for item in batch.results:
            for contact in item.contacts:
                all_rows.append(
                    {
                        "Company": item.company_name,
                        "Name": contact.get("name") or "—",
                        "Title": contact.get("title") or "—",
                        "Email": contact.get("email") or "—",
                        "Status": "OK" if item.success else "Failed",
                    }
                )
            if not item.contacts and item.success:
                all_rows.append(
                    {
                        "Company": item.company_name,
                        "Name": "—",
                        "Title": "—",
                        "Email": "—",
                        "Status": "No contacts found",
                    }
                )
        if all_rows:
            st.dataframe(all_rows, use_container_width=True, hide_index=True)
        st.rerun()
    else:
        st.warning(batch.message)

st.divider()
st.subheader("Export Research Data")

export_col1, export_col2 = st.columns([3, 1])
with export_col1:
    export_country = st.selectbox(
        "Export contacts for",
        countries,
        index=countries.index(filter_country) if filter_country in countries else 0,
        key="research_export_country",
        help="Download all research contacts with company details as Excel",
    )
with export_col2:
    st.write("")
    st.write("")
    export_country_value = None if export_country == "All" else export_country
    with get_session() as session:
        export_service = ResearchService(session, ai_provider=ai_provider)
        export_count = export_service.get_contact_count(export_country_value)
        excel_data = export_service.export_contacts_to_excel(export_country_value)
        excel_filename = export_service.get_export_filename(export_country)

    st.download_button(
        label="Download Excel",
        data=excel_data,
        file_name=excel_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        disabled=export_count == 0,
    )
    if export_count == 0:
        st.caption("No contacts to export for this selection.")
    else:
        st.caption(f"{export_count:,} contact(s) will be included.")

st.divider()
st.subheader("Recent Contacts")

with get_session() as session:
    contacts = (
        session.query(CompanyContact)
        .options(joinedload(CompanyContact.company))
        .order_by(CompanyContact.created_at.desc())
        .limit(25)
        .all()
    )
    contact_rows = [
        {
            "Company": c.company.company_name if c.company else "—",
            "Name": c.full_name or "—",
            "Title": c.job_title or "—",
            "Email": c.email or "—",
            "LinkedIn": c.linkedin_url or "—",
            "Source": c.source.value,
        }
        for c in contacts
    ]

if contact_rows:
    st.dataframe(
        contact_rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "LinkedIn": st.column_config.LinkColumn("LinkedIn"),
            "Email": st.column_config.TextColumn("Email"),
        },
    )
else:
    st.caption("No contacts discovered yet.")

st.divider()
st.subheader("Recent Research Jobs")

with get_session() as session:
    jobs = (
        session.query(CrawlJob)
        .options(joinedload(CrawlJob.company))
        .filter(CrawlJob.job_type == CrawlJobType.RESEARCH)
        .order_by(CrawlJob.created_at.desc())
        .limit(10)
        .all()
    )
    job_rows = [
        {
            "Company": j.company.company_name if j.company else "—",
            "Contacts": j.companies_found,
            "Status": j.status.value,
            "Error": (j.error_message or "")[:80],
        }
        for j in jobs
    ]

if job_rows:
    st.dataframe(job_rows, use_container_width=True, hide_index=True)
