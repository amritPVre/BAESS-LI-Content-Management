"""Profile Enrichment page — batch enrich up to 30 companies per run."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import streamlit as st
from sqlalchemy.orm import joinedload

from config.settings import get_settings
from database.connection import get_session
from models.crawl_job import CrawlJob, CrawlJobType
from services.company_service import CompanyService
from services.enrichment_service import EnrichmentService
from utils.logging import setup_logging
from lead_bootstrap import ensure_lead_engine_db, render_lead_header

ensure_lead_engine_db()
setup_logging()
settings = get_settings()
COOLDOWN_KEY = "enrichment_cooldown_until"
BATCH_SIZE = settings.enrichment_batch_size
COOLDOWN_SECONDS = settings.enrichment_cooldown_seconds


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
    "Profile Enrichment",
    f"Batch-enrich up to {BATCH_SIZE} unscraped companies per run with safe delays",
)

with get_session() as session:
    enrichment_service = EnrichmentService(session)
    stats = enrichment_service.get_enrichment_stats()
    company_service = CompanyService(session)
    countries = ["All"] + company_service.get_countries()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Pending", stats["pending"])
m2.metric("Completed", stats["completed"])
m3.metric("In Progress", stats["in_progress"])
m4.metric("Failed", stats["failed"])

st.info(
    f"Each run processes up to **{BATCH_SIZE} companies** that have not been "
    f"enriched yet (no website on file). Every profile fetch waits "
    f"**{settings.enrichment_delay_min:.0f}–{settings.enrichment_delay_max:.0f}s** "
    f"randomly between requests. After a batch finishes, the button locks for "
    f"**{COOLDOWN_SECONDS // 60} minutes** before the next run."
)

st.divider()

filter_country = st.selectbox(
    "Filter by Country (optional)",
    options=countries,
    help="Limit enrichment to a specific country queue",
)

with get_session() as session:
    country_filter_value = None if filter_country == "All" else filter_country
    batch_preview = EnrichmentService(session).preview_batch(
        country=country_filter_value
    )

if batch_preview:
    st.markdown(
        f"**Next batch queue ({len(batch_preview)} companies without a website yet):**"
    )
    preview_rows = [
        {
            "Company": c["company_name"],
            "Country": c["country"],
            "ENF Profile": c["enf_profile_url"],
        }
        for c in batch_preview
    ]
    st.dataframe(preview_rows, use_container_width=True, hide_index=True)
else:
    if stats["completed"] > 0:
        st.success(
            f"All discovered companies have been enriched ({stats['completed']} completed). "
            f"Go to **Company Research** for the next phase."
        )
    else:
        st.info("No companies waiting for enrichment. Run **Discovery** first.")

remaining = _cooldown_remaining()

if remaining > 0:

    @st.fragment(run_every=timedelta(seconds=5))
    def cooldown_banner() -> None:
        left = _cooldown_remaining()
        if left > 0:
            available_at = datetime.fromtimestamp(
                st.session_state[COOLDOWN_KEY]
            ).strftime("%H:%M:%S")
            st.warning(
                f"Cooling down — enrichment locked for **{_format_duration(left)}** "
                f"(available again at **{available_at}**)"
            )
        else:
            st.session_state.pop(COOLDOWN_KEY, None)
            st.rerun()

    cooldown_banner()

st.divider()

button_disabled = remaining > 0 or not batch_preview
button_label = (
    f"Cooling down ({_format_duration(remaining)})"
    if remaining > 0
    else f"✨ Enrich Next {min(len(batch_preview), BATCH_SIZE)} Companies"
    if batch_preview
    else "No Companies to Enrich"
)

enrich_btn = st.button(
    button_label,
    type="primary",
    use_container_width=True,
    disabled=button_disabled,
    help=(
        f"Runs up to {BATCH_SIZE} profiles with "
        f"{settings.enrichment_delay_min:.0f}–{settings.enrichment_delay_max:.0f}s "
        f"delays, then {COOLDOWN_SECONDS // 60}-minute cooldown"
    ),
)

if enrich_btn and batch_preview and remaining <= 0:
    progress_bar = st.progress(0, text="Starting batch enrichment...")
    status_box = st.empty()
    result_rows = []

    def on_progress(current: int, total: int, company_name: str) -> None:
        progress_bar.progress(
            current / total,
            text=f"Enriching {current}/{total}: {company_name}",
        )
        status_box.info(
            f"Processing **{company_name}** ({current} of {total}). "
            f"Waiting {settings.enrichment_delay_min:.0f}–"
            f"{settings.enrichment_delay_max:.0f}s before each fetch..."
        )

    with get_session() as session:
        batch_result = EnrichmentService(session).enrich_batch(
            country=country_filter_value,
            batch_size=BATCH_SIZE,
            on_progress=on_progress,
        )

    progress_bar.progress(1.0, text="Batch complete")
    status_box.empty()

    if batch_result.processed > 0:
        _start_cooldown()
        st.success(batch_result.message)
        st.caption(
            f"Cooldown active for {COOLDOWN_SECONDS // 60} minutes before the next batch."
        )

        for item in batch_result.results:
            result_rows.append(
                {
                    "Company": item.company_name,
                    "Status": "OK" if item.success else "Failed",
                    "Website": item.website or "—",
                    "Error": (item.error or "")[:80],
                }
            )
        st.dataframe(result_rows, use_container_width=True, hide_index=True)
        st.rerun()
    else:
        st.warning(batch_result.message)

st.divider()
st.subheader("Recent Enrichment Jobs")

with get_session() as session:
    jobs = (
        session.query(CrawlJob)
        .options(joinedload(CrawlJob.company))
        .filter(CrawlJob.job_type == CrawlJobType.ENRICHMENT)
        .order_by(CrawlJob.created_at.desc())
        .limit(15)
        .all()
    )
    job_rows = [
        {
            "Company": j.company.company_name if j.company else "—",
            "Status": j.status.value,
            "Started": j.started_at.strftime("%Y-%m-%d %H:%M")
            if j.started_at
            else "—",
            "Error": (j.error_message or "")[:80],
        }
        for j in jobs
    ]

if job_rows:
    st.dataframe(job_rows, use_container_width=True, hide_index=True)
else:
    st.caption("No enrichment jobs yet.")
