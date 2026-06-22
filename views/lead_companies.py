"""Companies page — search, filter, paginate, export."""

from __future__ import annotations

import streamlit as st

from config.settings import get_settings
from database.connection import get_session
from models.company import CrawlStatus, EnrichmentStatus
from services.company_service import CompanyService
from utils.logging import setup_logging
from lead_bootstrap import ensure_lead_engine_db, render_lead_header

ensure_lead_engine_db()
setup_logging()
render_lead_header(
    "Companies",
    "Search, filter, and export your solar industry lead database",
)

settings = get_settings()

with get_session() as session:
    service = CompanyService(session)
    available_countries = ["All"] + service.get_countries()
    dashboard = service.get_dashboard_stats()

s1, s2, s3, s4 = st.columns(4)
s1.metric("Total", dashboard["total_companies"])
s2.metric("Enriched", dashboard["enriched"])
s3.metric("With Phone", dashboard["with_phone"])
s4.metric("Failed", dashboard["failed"])

st.divider()

fc1, fc2, fc3, fc4 = st.columns(4)
with fc1:
    search = st.text_input("Search", placeholder="Name, website, phone, address...")
with fc2:
    country_filter = st.selectbox("Country", available_countries)
with fc3:
    crawl_filter = st.selectbox(
        "Crawl Status", ["All"] + [s.value for s in CrawlStatus]
    )
with fc4:
    enrich_filter = st.selectbox(
        "Enrichment Status", ["All"] + [s.value for s in EnrichmentStatus]
    )

if "companies_page" not in st.session_state:
    st.session_state.companies_page = 1

btn_prev, btn_info, btn_next, btn_export = st.columns([1, 2, 1, 1])

with get_session() as session:
    service = CompanyService(session)
    companies, total = service.search_companies(
        search=search,
        country=country_filter,
        crawl_status=crawl_filter,
        enrichment_status=enrich_filter,
        page=st.session_state.companies_page,
        per_page=settings.companies_per_page,
    )
    display_df = service.companies_to_dataframe(companies) if companies else None
    company_details = [
        {
            "company_name": c.company_name,
            "enf_profile_url": c.enf_profile_url,
            "address": c.address,
            "operating_area": c.profile.operating_area if c.profile else None,
            "battery_storage": c.profile.battery_storage if c.profile else None,
            "installation_size": c.profile.installation_size if c.profile else None,
        }
        for c in companies
    ]

total_pages = max(1, (total + settings.companies_per_page - 1) // settings.companies_per_page)

with btn_prev:
    if st.button("← Prev", disabled=st.session_state.companies_page <= 1):
        st.session_state.companies_page -= 1
        st.rerun()
with btn_info:
    st.caption(
        f"Page {st.session_state.companies_page} of {total_pages} · "
        f"{total:,} results"
    )
with btn_next:
    if st.button("Next →", disabled=st.session_state.companies_page >= total_pages):
        st.session_state.companies_page += 1
        st.rerun()
with btn_export:
    export_all = st.button("Export CSV")

if export_all:
    with get_session() as session:
        df = CompanyService(session).export_all_to_csv()
    st.download_button(
        label="Download CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="baess_companies_export.csv",
        mime="text/csv",
    )

if display_df is not None and not display_df.empty:
    st.dataframe(
        display_df[
            [
                "company_name",
                "country",
                "website",
                "phone",
                "crawl_status",
                "enrichment_status",
                "battery_storage",
                "installation_size",
            ]
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "company_name": "Company",
            "country": "Country",
            "website": st.column_config.LinkColumn("Website"),
            "phone": "Phone",
            "crawl_status": "Crawl",
            "enrichment_status": "Enrichment",
            "battery_storage": "Battery",
            "installation_size": "Install Size",
        },
    )

    with st.expander("View full details"):
        selected_idx = st.selectbox(
            "Select company",
            range(len(company_details)),
            format_func=lambda i: company_details[i]["company_name"],
        )
        c = company_details[selected_idx]
        st.markdown(f"**ENF Profile:** [{c['enf_profile_url']}]({c['enf_profile_url']})")
        st.markdown(f"**Address:** {c['address'] or '—'}")
        st.markdown(f"**Operating Area:** {c['operating_area'] or '—'}")
        st.markdown(f"**Battery Storage:** {c['battery_storage'] or '—'}")
        st.markdown(f"**Installation Size:** {c['installation_size'] or '—'}")
else:
    st.info("No companies match your filters.")
