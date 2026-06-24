"""Email campaigns — draft from Neon contacts, send via ZeptoMail, follow-ups."""

from __future__ import annotations

import streamlit as st

from ai_client import get_api_key
from config.settings import get_settings
from database.connection import get_session
from lead_bootstrap import ensure_lead_engine_db, render_lead_header
from outreach_ai import contact_to_research, generate_followup_email, generate_initial_email
from outreach_db import (
    campaign_stats,
    count_sent_today,
    get_message,
    has_follow_up_draft,
    list_drafts,
    list_eligible_contacts,
    list_follow_up_due,
    list_sent_pending_sync,
    mark_failed,
    mark_sent,
    save_draft,
)
from services.zeptomail_service import send_outreach_email, send_test_email, zeptomail_configured
from services.zeptomail_sync import sync_delivery_for_messages
from services.zoho_mail_sync import sync_replies_for_messages, zoho_configured
from utils.logging import setup_logging

ensure_lead_engine_db()
setup_logging()

st.title("📬 Email Campaigns")
st.caption(
    "Pull researched contacts from Neon → AI-draft 4-line emails → send via ZeptoMail → "
    "sync replies & bounces → follow up."
)

if not get_api_key():
    st.warning("Set `DEEPSEEK_API_KEY` in secrets for AI drafting.")
    st.stop()

settings = get_settings()
BATCH_MAX = 10

with get_session() as session:
    stats = campaign_stats(session)
    sent_today = count_sent_today(session)
    all_eligible = list_eligible_contacts(session, limit=500)

countries = ["All"] + sorted({r["country"] for r in all_eligible if r.get("country")})

tab_draft, tab_queue, tab_test, tab_sync, tab_follow = st.tabs(
    ["✨ Draft from DB", "📤 Drafts & Send", "🧪 Test send", "🔄 Sync status", "🔁 Follow-ups"]
)

with tab_draft:
    render_lead_header(
        "Draft outreach emails",
        "Contacts with completed research and a valid email address",
    )
    country = st.selectbox("Country filter", countries, key="camp_country")
    custom = st.text_area("Custom instructions (optional)", height=72, key="camp_custom")

    with get_session() as session:
        eligible = list_eligible_contacts(
            session,
            None if country == "All" else country,
            limit=BATCH_MAX,
        )

    if eligible:
        st.dataframe(
            [
                {
                    "Company": r["company_name"],
                    "Contact": r["name"] or "—",
                    "Email": r["email"],
                    "Country": r["country"],
                }
                for r in eligible
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No eligible contacts — run Lead Engine → Company Research first.")

    if st.button(
        f"⚡ Generate up to {BATCH_MAX} drafts",
        type="primary",
        disabled=not eligible,
    ):
        prog = st.progress(0)
        ok = 0
        with get_session() as session:
            rows = list_eligible_contacts(
                session,
                None if country == "All" else country,
                limit=BATCH_MAX,
            )
            for i, row in enumerate(rows):
                prog.progress((i + 1) / max(len(rows), 1))
                research = contact_to_research(row)
                subject, body = generate_initial_email(research, custom)
                if subject and body:
                    save_draft(
                        session,
                        company_id=row["company_id"],
                        contact_id=row["contact_id"],
                        subject=subject,
                        body_text=body,
                    )
                    ok += 1
        st.success(f"Saved {ok} draft(s). Review in **Drafts & Send**.")
        st.rerun()

with tab_queue:
    render_lead_header("Drafts & send", "Review AI drafts then send via ZeptoMail")
    if not zeptomail_configured():
        st.warning(
            "Configure `ZEPTOMAIL_SEND_TOKEN` and `ZEPTOMAIL_FROM_ADDRESS` in secrets to send."
        )
    st.caption(f"Sent today: **{sent_today}** / **{settings.daily_send_limit}** daily cap")

    with get_session() as session:
        drafts = list_drafts(session, limit=30)

    if not drafts:
        st.info("No drafts yet. Use **Draft from DB** to generate.")
    else:
        for msg in drafts:
            contact = msg.contact
            label = f"{contact.email if contact else '?'} — {msg.subject or 'No subject'}"
            with st.expander(label):
                new_subject = st.text_input(
                    "Subject", value=msg.subject or "", key=f"sub_{msg.id}"
                )
                new_body = st.text_area(
                    "Body", value=msg.body_text, height=220, key=f"body_{msg.id}"
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Save edits", key=f"save_{msg.id}"):
                        with get_session() as session:
                            m = get_message(session, str(msg.id))
                            if m:
                                m.subject = new_subject
                                m.body_text = new_body
                        st.success("Saved")
                with c2:
                    if st.button("Send via ZeptoMail", key=f"send_{msg.id}", type="primary"):
                        with get_session() as session:
                            today_count = count_sent_today(session)
                        if today_count >= settings.daily_send_limit:
                            st.error("Daily send limit reached.")
                        elif not contact or not contact.email:
                            st.error("Missing contact email.")
                        else:
                            result = send_outreach_email(
                                to_email=contact.email,
                                to_name=contact.full_name or "",
                                subject=new_subject,
                                body_text=new_body,
                                message_id=str(msg.id),
                            )
                            with get_session() as session:
                                m = get_message(session, str(msg.id))
                                if result.success and m:
                                    mark_sent(
                                        session,
                                        m,
                                        zepto_reference=result.email_reference,
                                        follow_up_days=settings.follow_up_days,
                                    )
                                    m.subject = new_subject
                                    m.body_text = new_body
                                    st.success("Sent.")
                                    st.rerun()
                                elif m:
                                    mark_failed(session, m, result.error or "Send failed")
                                    st.error(result.error)

with tab_test:
    render_lead_header(
        "Send test email",
        "Verify ZeptoMail delivery, From/Reply-To headers, and inbox placement",
    )
    if not zeptomail_configured():
        st.warning(
            "Configure `ZEPTOMAIL_SEND_TOKEN` and `ZEPTOMAIL_FROM_ADDRESS` in secrets first."
        )
    else:
        st.info(
            f"**From:** `{settings.zeptomail_from_address}` ({settings.zeptomail_from_name})  \n"
            f"**Reply-To:** `{settings.zeptomail_reply_to or settings.zeptomail_from_address}`  \n"
            f"**Where replies land:** Zoho Mail inbox for the Reply-To address (synced in **Sync status** tab)."
        )
        test_email = st.text_input(
            "Send test to",
            value=st.session_state.get("sender_email", settings.zeptomail_reply_to or ""),
            placeholder="you@example.com",
            key="camp_test_email",
        )
        test_subject = st.text_input(
            "Subject (optional)",
            value="BAESS Outreach — test email",
            key="camp_test_subject",
        )
        test_body = st.text_area(
            "Body (optional)",
            height=180,
            placeholder="Leave blank to use the default test message showing From / Reply-To details.",
            key="camp_test_body",
        )
        if st.button("Send test email", type="primary", key="camp_test_send"):
            if not test_email or "@" not in test_email:
                st.error("Enter a valid email address.")
            else:
                with st.spinner("Sending via ZeptoMail..."):
                    result = send_test_email(
                        to_email=test_email,
                        subject=test_subject or None,
                        body_text=test_body.strip() or None,
                    )
                if result.success:
                    st.success(f"Test sent to **{test_email}**. Check inbox (and spam/promotions).")
                    st.caption(
                        f"Zepto reference: `{result.email_reference or result.request_id or '—'}` · "
                        "Not counted toward daily campaign cap."
                    )
                else:
                    st.error(result.error or "Send failed")

with tab_sync:
    render_lead_header("Sync delivery & replies", "Poll ZeptoMail logs and Zoho Mail inbox")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Sync delivery status (bounces)", use_container_width=True):
            with get_session() as session:
                pending = list_sent_pending_sync(session)
                sync_result = sync_delivery_for_messages(pending)
            st.success(
                f"Checked {sync_result.checked} sent message(s); "
                f"{sync_result.bounced} bounce(s) marked."
            )
            for e in sync_result.errors or []:
                st.warning(e)
    with c2:
        if st.button("Sync replies (Zoho Mail)", use_container_width=True):
            if not zoho_configured():
                st.error("Zoho OAuth secrets not configured.")
            else:
                with get_session() as session:
                    pending = list_sent_pending_sync(session)
                    reply_result = sync_replies_for_messages(pending)
                st.success(
                    f"Scanned {reply_result.checked} inbox message(s); "
                    f"{reply_result.matched} matched as replies."
                )
                for e in reply_result.errors:
                    st.warning(e)
    st.markdown("Configure Zoho Mail OAuth — see `docs/ZOHO_MAIL_SETUP.md`.")

with tab_follow:
    render_lead_header(
        "Follow-up queue",
        f"Sent emails with no reply/bounce after {settings.follow_up_days}+ days",
    )
    with get_session() as session:
        due = list_follow_up_due(
            session, max_sequence=settings.max_follow_up_sequence, limit=BATCH_MAX
        )

    if not due:
        st.info("No follow-ups due. Sync replies after prospects respond.")
    else:
        st.dataframe(
            [
                {
                    "Company": m.company.company_name if m.company else "",
                    "Email": m.contact.email if m.contact else "",
                    "Seq": m.sequence_num,
                    "Sent": m.sent_at.strftime("%Y-%m-%d") if m.sent_at else "",
                }
                for m in due
            ],
            use_container_width=True,
            hide_index=True,
        )

    if st.button("Generate follow-up drafts", type="primary", disabled=not due):
        created = 0
        with get_session() as session:
            due_rows = list_follow_up_due(
                session, max_sequence=settings.max_follow_up_sequence, limit=BATCH_MAX
            )
            for parent in due_rows:
                if has_follow_up_draft(session, str(parent.id)):
                    continue
                contact = parent.contact
                company = parent.company
                if not contact or not company:
                    continue
                row = {
                    "company_name": company.company_name,
                    "country": company.country,
                    "website": company.website,
                    "email": contact.email,
                    "name": contact.full_name,
                    "title": contact.job_title,
                }
                research = contact_to_research(row)
                subject, body = generate_followup_email(
                    research,
                    parent.sequence_num + 1,
                    parent.subject or "",
                    parent.body_text,
                )
                if subject and body:
                    save_draft(
                        session,
                        company_id=parent.company_id,
                        contact_id=parent.contact_id,
                        subject=subject,
                        body_text=body,
                        sequence_num=parent.sequence_num + 1,
                        parent_message_id=str(parent.id),
                    )
                    created += 1
        st.success(f"Created {created} follow-up draft(s). Send from **Drafts & Send**.")
        st.rerun()

    st.caption(f"Campaign stats: {stats}")
