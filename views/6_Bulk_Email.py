"""Bulk email — CSV upload, {first_name} personalization, ZeptoMail + Zoho sync."""

from __future__ import annotations

import time

import streamlit as st

from lead_bootstrap import ensure_lead_engine_db, render_lead_header

ensure_lead_engine_db()

from config.settings import get_settings
from database.connection import get_session
from bulk_email_db import (
    bulk_stats,
    count_sent_today_all,
    create_bulk_job_rows,
    list_pending_for_job,
    list_sent_pending_bulk_sync,
    mark_bulk_failed,
    mark_bulk_sent,
    recent_jobs,
)
from bulk_email_sync import sync_bulk_bounces, sync_bulk_replies
from bulk_email_utils import parse_recipients_csv, preview_rows, render_template
from services.zeptomail_service import send_outreach_email, zeptomail_configured
from services.zoho_mail_sync import zoho_configured
from utils.logging import setup_logging

setup_logging()

st.title("📨 Bulk Email")
st.caption(
    "Upload a CSV (name + email) → personalize with `{first_name}` → send via ZeptoMail → "
    "sync bounces & replies from Zoho."
)

settings = get_settings()
batch_cap = settings.bulk_send_limit_per_batch
daily_cap = settings.daily_send_limit

with get_session() as session:
    sent_today = count_sent_today_all(session)
    stats = bulk_stats(session)

tab_upload, tab_send, tab_sync, tab_history = st.tabs(
    ["📁 Upload & compose", "📤 Send batch", "🔄 Sync status", "📋 History"]
)

DEFAULT_SUBJECT = "Quick note for {first_name}"
DEFAULT_BODY = """Hi {first_name},

I wanted to reach out personally — we built BAESS to help solar EPCs streamline design and proposals.

If useful, you can explore our free tools at https://www.baess.app/tools

Best,
Amrit | BAESS Labs"""

with tab_upload:
    render_lead_header(
        "Upload CSV & compose",
        f"Required: email column. Optional: name. Max **{batch_cap}** recipients per batch.",
    )
    st.markdown(
        "Placeholders: `{first_name}`, `{name}`, `{email}` (case variants supported for first name)."
    )

    job_name = st.text_input("Batch name (optional)", placeholder="June installer outreach")
    uploaded = st.file_uploader("CSV file", type=["csv"])
    subject_tpl = st.text_input("Subject template", value=DEFAULT_SUBJECT)
    body_tpl = st.text_area("Email body template", value=DEFAULT_BODY, height=220)

    if uploaded:
        recipients, warn = parse_recipients_csv(uploaded.getvalue(), max_rows=batch_cap)
        if warn:
            st.warning(warn)
        if recipients:
            st.success(f"Loaded **{len(recipients)}** recipient(s).")
            st.dataframe(
                [
                    {
                        "Name": r["name"] or "—",
                        "First name": r["first_name"],
                        "Email": r["email"],
                    }
                    for r in recipients[:20]
                ],
                use_container_width=True,
                hide_index=True,
            )
            if len(recipients) > 20:
                st.caption(f"Showing first 20 of {len(recipients)}.")

            previews = preview_rows(recipients, subject_tpl, body_tpl, limit=3)
            st.subheader("Preview (first 3)")
            for i, row in enumerate(previews, 1):
                with st.expander(f"{i}. {row['email']}"):
                    st.markdown(f"**Subject:** {row['subject']}")
                    st.text(row["body"])

            if st.button("Save batch for sending", type="primary"):
                rendered = [
                    {
                        "subject": render_template(
                            subject_tpl, name=r["name"], email=r["email"]
                        ),
                        "body": render_template(body_tpl, name=r["name"], email=r["email"]),
                    }
                    for r in recipients
                ]
                with get_session() as session:
                    job_id = create_bulk_job_rows(
                        session,
                        job_name=job_name,
                        subject_template=subject_tpl,
                        body_template=body_tpl,
                        recipients=recipients,
                        rendered=rendered,
                    )
                st.session_state["bulk_job_id"] = job_id
                st.session_state["bulk_recipient_count"] = len(recipients)
                st.success(f"Batch saved ({len(recipients)} emails). Go to **Send batch**.")
        elif not warn:
            st.error("No valid rows in CSV.")

with tab_send:
    render_lead_header("Send batch", "Uses ZeptoMail — shares daily cap with Email Campaigns")
    if not zeptomail_configured():
        st.warning("Configure ZeptoMail secrets before sending.")
    st.caption(f"Sent today (all modules): **{sent_today}** / **{daily_cap}**")

    job_id = st.session_state.get("bulk_job_id")
    if not job_id:
        st.info("Upload a CSV and click **Save batch for sending** first.")
    else:
        with get_session() as session:
            pending = list_pending_for_job(session, job_id)
        st.write(f"Batch `{job_id[:8]}…` — **{len(pending)}** email(s) pending.")

        remaining_today = max(0, daily_cap - sent_today)
        can_send = min(len(pending), remaining_today, batch_cap)

        if remaining_today <= 0:
            st.error("Daily send limit reached. Try again tomorrow or raise `DAILY_SEND_LIMIT`.")
        elif not pending:
            st.success("This batch is fully processed.")
        elif st.button(f"Send {can_send} email(s) now", type="primary", disabled=not zeptomail_configured()):
            prog = st.progress(0)
            status = st.empty()
            ok = fail = 0
            with get_session() as session:
                rows = list_pending_for_job(session, job_id)[:can_send]
                for i, row in enumerate(rows):
                    prog.progress((i + 1) / max(len(rows), 1))
                    status.caption(f"Sending {i + 1}/{len(rows)} → {row.recipient_email}")
                    if count_sent_today_all(session) >= daily_cap:
                        st.warning("Daily limit hit mid-batch — stopping.")
                        break
                    result = send_outreach_email(
                        to_email=row.recipient_email,
                        to_name=row.recipient_name or row.first_name or "",
                        subject=row.subject,
                        body_text=row.body_text,
                        message_id=str(row.id),
                    )
                    if result.success:
                        mark_bulk_sent(session, row, zepto_reference=result.email_reference)
                        ok += 1
                    else:
                        mark_bulk_failed(session, row, result.error or "Send failed")
                        fail += 1
                    time.sleep(0.25)
            st.success(f"Done — **{ok}** sent, **{fail}** failed.")
            st.rerun()

with tab_sync:
    render_lead_header("Sync bounces & replies", "ZeptoMail logs + Zoho Mail inbox")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Sync delivery (bounces)", use_container_width=True):
            with get_session() as session:
                pending = list_sent_pending_bulk_sync(session)
                sync_result = sync_bulk_bounces(pending)
            st.success(
                f"Checked {sync_result.checked}; {sync_result.bounced} bounce(s) marked."
            )
            for e in sync_result.errors or []:
                st.warning(e)
    with c2:
        if st.button("Sync replies (Zoho)", use_container_width=True):
            if not zoho_configured():
                st.error("Zoho OAuth not configured.")
            else:
                with get_session() as session:
                    pending = list_sent_pending_bulk_sync(session)
                    reply_result = sync_bulk_replies(pending)
                st.success(
                    f"Scanned {reply_result.checked} inbox message(s); "
                    f"{reply_result.matched} matched as replies."
                )
                for e in reply_result.errors:
                    st.warning(e)

with tab_history:
    render_lead_header("Bulk send stats", "Recent batches stored in Neon")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Sent", stats.get("sent", 0))
    m2.metric("Failed", stats.get("failed", 0))
    m3.metric("Replied", stats.get("replied", 0))
    m4.metric("Bounced", stats.get("bounced", 0))

    with get_session() as session:
        jobs = recent_jobs(session)
    if jobs:
        st.dataframe(
            [
                {
                    "Batch": j["job_name"],
                    "Recipients": j["total"],
                    "Created": j["created_at"].strftime("%Y-%m-%d %H:%M")
                    if j["created_at"]
                    else "",
                    "Job ID": j["job_id"][:8] + "…",
                }
                for j in jobs
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No bulk sends yet.")
