"""
BAESS Outreach Suite — Cold Email Generator (Page 2)
Paste up to 10 prospect rows (CSV/TSV) → web research → personalised cold emails.
"""

import streamlit as st
import json
import csv
import io
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ai_client import get_api_key, call_ai
from company_research import parse_pasted_rows, research_company_row
from baess_context import (
    BAESS_PLATFORM_CONTEXT,
    EMAIL_TEMPLATES,
    segment_hint,
    optional_instructions_block,
    topics_focus_block,
)
from content_history import avoid_repetition_block

st.title("📧 Cold Email Generator")
st.caption(
    "Paste up to 10 prospects at a time — the app researches each company on the web "
    "and writes personalised cold emails."
)

MAX_BATCH = 10

# ── Guard ─────────────────────────────────────────────────────────────────────
if not get_api_key():
    st.warning("⚠️ Add your DeepSeek API key to `.streamlit/secrets.toml`.")
    st.stop()

# ── Pull shared config ────────────────────────────────────────────────────────
offer        = st.session_state.get("offer_type",   "Founding Member – ₹1,499/month locked forever")
cta_type     = st.session_state.get("cta_type",     "Try the free tools at baess.app")
sender_name  = st.session_state.get("sender_name",  "Amrit")
sender_title = st.session_state.get("sender_title", "Founder, BAESS Labs")
sender_email = st.session_state.get("sender_email", "amrit@baess.app")

if "email_research_cache" not in st.session_state:
    st.session_state.email_research_cache = {}

# ── System prompts ────────────────────────────────────────────────────────────
EMAIL_SYSTEM = f"""You are a B2B cold email specialist for BAESS Labs (https://baess.app).
You write cold emails that get replies. Use accurate product names and honest positioning.

{BAESS_PLATFORM_CONTEXT}

Rules:
- Subject line: under 8 words, no spam triggers, no ALL CAPS.
- Opening: do NOT start with 'I hope this email finds you well' or 'My name is'.
  Open with something specific from the company research — their projects, market, or pain point.
- Body: 3 short paragraphs max. Plain text — no bullet points.
  Para 1: why them, why now (use research hooks). Para 2: most relevant BAESS product + concrete benefit.
  Para 3: single CTA aligned to sidebar offer/CTA.
- Reference real products where relevant: PV AI Designer Pro, PV 3D Designer, BESS Designer,
  AI BOQ Generator, Solar Simulator, or free tools at baess.app/tools.
- Do NOT overclaim vs PVsyst/Helioscope — position as faster web workflow and AI-assisted BOQ/reports.
- If an anti-repetition block is provided, MUST use fresh subject lines, hooks, and angles — never reuse prior content.
- If contact name is unknown, use a role-appropriate greeting (e.g. "Hi team" or "Hi there").
- Signature: name, title, email.
- Tone: direct, peer-to-peer, zero corporate fluff.
- Output format exactly:
  SUBJECT: [subject line]
  ---
  [email body including signature]"""

REPLY_SYSTEM = f"""You are writing follow-up emails for BAESS Labs cold outreach.
Keep each follow-up shorter than the previous one. Use company research and BAESS product fit.

{BAESS_PLATFORM_CONTEXT}

Output format exactly:
SUBJECT: [subject line]
---
[email body]
No commentary. No labels. Just the email."""

# ── Prompt builders ───────────────────────────────────────────────────────────
def _research_block(r: dict) -> str:
    hooks = r.get("outreach_hooks") or []
    hooks_txt = "\n".join(f"  - {h}" for h in hooks) if hooks else "  (none)"
    products = r.get("recommended_baess_products") or []
    seg = segment_hint(r.get("company_type", "Other"))
    return f"""Company research brief:
- Company: {r.get('company', '')}
- Country: {r.get('country', '')}
- Website: {r.get('website') or 'not provided'}
- Company type: {r.get('company_type', 'Other')}
- Company (deep): {r.get('company_research', '')}
- Recommended BAESS products: {', '.join(products) if products else 'infer from segment'}
- Segment outreach angle:
{seg}
- Contact: {r.get('name') or 'unknown'} | {r.get('title') or 'unknown role'}
- To email: {r.get('email') or 'not provided'}
- Greeting hint: {r.get('contact_greeting', '')}
- Person note: {r.get('person_note') or 'none'}
- Hooks:
{hooks_txt}
- Confidence: {r.get('data_confidence', 'unknown')}"""


def build_email_prompt(
    research: dict,
    custom_instructions: str = "",
    same_batch_bodies: list[str] | None = None,
) -> str:
    history_avoid = avoid_repetition_block(
        email_log=st.session_state.get("email_log", []),
        calendars=st.session_state.get("content_calendars", {}),
        same_batch_messages=same_batch_bodies,
        context="cold email",
    )
    return f"""{_research_block(research)}

Write a cold email using the research above.
- Offer: {offer}
- CTA: {cta_type}
- Sender: {sender_name}, {sender_title}, {sender_email}
- Free tools entry: baess.app/tools (no signup for calculators)
{topics_focus_block()}
Make it feel like {sender_name} personally researched this company before writing.{history_avoid}{optional_instructions_block(custom_instructions)}"""

def build_followup_prompt(research: dict, num: int, context: str, orig_subject: str, custom_instructions: str = "") -> str:
    instructions = {
        2: f"Re: {orig_subject} — Gently bump the thread. Mention a specific BAESS product or free tool for their segment. 3–4 sentences.",
        3: "New subject line. Sharp industry observation from the research + free tool at baess.app/tools. 2–3 sentences.",
        4: f"Re: {orig_subject} — They replied with interest. Propose a 20-min demo call. Under 5 sentences.",
        5: "Final break-up email. Friendly, no guilt. Leave door open. 3 sentences max.",
    }
    history_avoid = avoid_repetition_block(
        email_log=st.session_state.get("email_log", []),
        context="cold email follow-up",
    )
    return f"""{_research_block(research)}

Write follow-up email #{num}:
- Context: {context or 'no additional context'}
- Original subject: {orig_subject or 'BAESS outreach'}
- Sender: {sender_name}, {sender_title}, {sender_email}
- Instruction: {instructions.get(num, 'Professional follow-up.')}
{topics_focus_block()}{history_avoid}{optional_instructions_block(custom_instructions)}"""

# ── Helpers ───────────────────────────────────────────────────────────────────
def parse_email(raw: str) -> tuple[str, str]:
    if "---" in raw:
        parts = raw.split("---", 1)
        return parts[0].replace("SUBJECT:", "").strip(), parts[1].strip()
    return "BAESS – free solar engineering tool", raw.strip()


def render_email(subject: str, body: str, label: str = "📨 Generated Email"):
    st.markdown(f'<div class="badge-blue">{label} — Subject: {subject}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="output-card">{body}</div>', unsafe_allow_html=True)
    st.code(f"Subject: {subject}\n\n{body}", language=None)
    st.caption("👆 Copy button above — paste directly into Zoho Mail.")


def cache_key(row: dict) -> str:
    return f"{row.get('company','').lower()}|{row.get('website','').lower()}"


def get_or_research(row: dict) -> dict | None:
    key = cache_key(row)
    if key in st.session_state.email_research_cache:
        return st.session_state.email_research_cache[key]
    research = research_company_row(row, call_ai)
    if research:
        st.session_state.email_research_cache[key] = research
    return research


def show_research_card(research: dict):
    conf = research.get("data_confidence", "unknown")
    icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "⚪")
    contact = research.get("name") or research.get("title") or "Generic contact"
    with st.expander(f"{icon} {research.get('company', '?')} ({research.get('country', '')}) — {contact}"):
        st.markdown(f"**Type:** {research.get('company_type', 'Other')}")
        st.markdown(research.get("company_research", ""))
        if research.get("recommended_baess_products"):
            st.markdown("**BAESS fit:** " + ", ".join(research["recommended_baess_products"]))
        if research.get("outreach_hooks"):
            st.markdown("**Hooks:** " + " · ".join(f"_{h}_" for h in research["outreach_hooks"]))


def log_email(research: dict, subject: str, body: str, stage: str):
    st.session_state.email_count += 1
    st.session_state.setdefault("email_log", []).append({
        "timestamp": datetime.now().isoformat(),
        "company": research.get("company", ""),
        "country": research.get("country", ""),
        "website": research.get("website", ""),
        "contact": research.get("name", ""),
        "title": research.get("title", ""),
        "to_email": research.get("email", ""),
        "subject": subject,
        "body": body,
        "stage": stage,
    })

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_batch, tab_followup, tab_templates = st.tabs([
    "📋 Batch Generator", "🔄 Follow-up", "📖 Templates & Checklist"
])

# ── Tab 1: Batch paste (main workflow) ────────────────────────────────────────
with tab_batch:
    st.subheader(f"Paste up to {MAX_BATCH} prospects")
    st.markdown(
        "Paste CSV or tab-separated rows. **Required:** company, country. "
        "**Optional:** website, email, name, title."
    )

    SAMPLE = (
        "company,country,website,email,name,title\n"
        "SolarPros Australia,Australia,https://solarpros.com.au,john@solarpros.com.au,John Smith,Operations Manager\n"
        "GreenSun Dubai,UAE,https://greensun.ae,,,\n"
    )
    st.download_button("⬇ Download CSV template", SAMPLE,
                       file_name="email_prospects.csv", mime="text/csv")

    with st.expander("📌 Column format & examples"):
        st.markdown("""
**With header row** (comma or tab separated):
```
company,country,website,email,name,title
SolarPros Australia,Australia,https://solarpros.com.au,john@solarpros.com.au,John Smith,Ops Manager
GreenSun Dubai,UAE,https://greensun.ae,,,
```

**Without header** — fixed column order:
`company | country | website | email | name | title`

Name and title can be left blank — the AI will use a generic greeting and focus on company research.
""")

    pasted = st.text_area(
        "Paste rows here",
        height=220,
        placeholder=(
            "company,country,website,email,name,title\n"
            "SolarPros Australia,Australia,https://solarpros.com.au,john@solarpros.com.au,John Smith,Ops Manager\n"
            "GreenSun Dubai,UAE,https://greensun.ae,,,"
        ),
        key="batch_paste",
    )

    batch_custom = st.text_area(
        "Custom instructions (optional)",
        placeholder=(
            "e.g. These are GCC prospects — lead with BESS Designer and free battery sizing calculator. "
            "Do not mention Founding Member pricing. Keep emails under 120 words."
        ),
        height=88,
        key="batch_custom",
        help="Applied to every email in this batch. Leave blank to use default system context.",
    )

    if pasted.strip():
        preview_rows, parse_warn = parse_pasted_rows(pasted, max_rows=MAX_BATCH)
        if parse_warn:
            st.warning(parse_warn)
        if preview_rows:
            st.markdown(f"**Preview — {len(preview_rows)} row(s) detected**")
            st.dataframe(preview_rows, use_container_width=True)

    if st.button(f"⚡ Research & Generate Emails (max {MAX_BATCH})", type="primary", use_container_width=True):
        rows, err = parse_pasted_rows(pasted, max_rows=MAX_BATCH)
        if err and not rows:
            st.error(err)
        elif not rows:
            st.warning("Paste at least one row with company and country.")
        else:
            if err:
                st.warning(err)

            results = []
            batch_bodies: list[str] = []
            prog = st.progress(0)
            status = st.empty()

            for i, row in enumerate(rows):
                label = f"{row.get('company', '?')}, {row.get('country', '')}"
                status.text(f"{i + 1}/{len(rows)} — Researching {label}...")
                research = get_or_research(row)
                if not research:
                    results.append({**row, "subject": "", "body": "", "error": "Research failed"})
                    prog.progress((i + 1) / len(rows))
                    continue

                status.text(f"{i + 1}/{len(rows)} — Writing email for {label}...")
                raw = call_ai(
                    EMAIL_SYSTEM,
                    build_email_prompt(research, batch_custom, same_batch_bodies=batch_bodies),
                    max_tokens=800,
                )
                subject, body = parse_email(raw) if raw else ("", "")
                results.append({
                    **row,
                    "company_type": research.get("company_type", ""),
                    "subject": subject,
                    "body": body,
                    "research_confidence": research.get("data_confidence", ""),
                    "generated_at": datetime.now().isoformat(),
                })
                if subject and body:
                    log_email(research, subject, body, "Email 1")
                    batch_bodies.append(body)
                    if "last_subject" not in st.session_state:
                        st.session_state["last_subject"] = subject
                prog.progress((i + 1) / len(rows))

            ok = [r for r in results if r.get("body")]
            status.success(f"✅ {len(ok)} email(s) generated ({len(results) - len(ok)} failed).")

            st.markdown("---")
            st.subheader("Research summaries")
            for row in rows:
                cached = st.session_state.email_research_cache.get(cache_key(row))
                if cached:
                    show_research_card(cached)

            st.markdown("---")
            st.subheader("Generated emails")
            for r in ok:
                to_line = f" → {r['email']}" if r.get("email") else ""
                render_email(
                    r["subject"], r["body"],
                    label=f"📨 {r.get('company', '')}, {r.get('country', '')}{to_line}",
                )

            if results:
                out = io.StringIO()
                w = csv.DictWriter(out, fieldnames=list(results[0].keys()))
                w.writeheader()
                w.writerows(results)
                st.download_button(
                    "⬇ Download batch as CSV", out.getvalue(),
                    file_name=f"baess_emails_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv", use_container_width=True,
                )

# ── Tab 2: Follow-up ──────────────────────────────────────────────────────────
with tab_followup:
    st.subheader("Follow-up for a pasted prospect")
    st.caption("Paste a single row (same format as batch) to research the company, then generate a follow-up.")

    fu_paste = st.text_area(
        "Prospect row",
        height=80,
        placeholder="GreenSun Dubai,UAE,https://greensun.ae,info@greensun.ae,Ahmed Hassan,Director",
        key="fu_paste",
    )
    fu_subject = st.text_input(
        "Original subject",
        value=st.session_state.get("last_subject", ""),
        placeholder="Auto-filled from last generated email, or type manually",
    )
    STAGES = {
        "Email 2 — No reply after 3 days (value nudge)":         2,
        "Email 3 — No reply after 7 days (short, fresh angle)":  3,
        "Email 4 — They replied with interest → book call":      4,
        "Email 5 — Final break-up email":                        5,
    }
    fu_label = st.selectbox("Which follow-up?", list(STAGES.keys()))
    fu_num = STAGES[fu_label]
    fu_ctx = st.text_area("Situation context (optional)", key="fu_ctx",
                          placeholder="They opened the email twice but didn't reply.", height=72)
    fu_custom = st.text_area(
        "Custom instructions (optional)",
        key="fu_custom",
        placeholder="e.g. Follow-up should only mention the free ROI calculator, not paid products.",
        height=72,
    )

    if st.button("⚡ Research & Generate Follow-up", type="primary", use_container_width=True):
        rows, err = parse_pasted_rows(fu_paste, max_rows=1)
        if not rows:
            st.warning(err or "Paste one row with company and country.")
        else:
            research = get_or_research(rows[0])
            if research:
                show_research_card(research)
                with st.spinner(f"Writing follow-up email {fu_num}..."):
                    raw = call_ai(
                        REPLY_SYSTEM,
                        build_followup_prompt(research, fu_num, fu_ctx, fu_subject, fu_custom),
                        max_tokens=700,
                    )
                if raw:
                    subject, body = parse_email(raw)
                    st.session_state["last_subject"] = fu_subject or subject
                    log_email(research, subject, body, f"Email {fu_num}")
                    render_email(subject, body, label=f"📩 Follow-up {fu_num}")

# ── Tab 3: Templates & checklist ─────────────────────────────────────────────
with tab_templates:
    st.subheader("Segment email templates")
    st.caption("Reference examples aligned to BAESS Labs products — AI personalises from live research.")
    for seg, d in EMAIL_TEMPLATES.items():
        with st.expander(f"📧 {seg}"):
            st.markdown(f"**Subject:** `{d['Subject']}`")
            st.markdown(f"**Opening:** {d['Opening']}")
            st.markdown(f"**CTA angle:** {d['CTA angle']}")
            st.caption(f"💡 {d['Why it works']}")

    st.markdown("---")
    st.subheader("BAESS product quick reference")
    st.markdown("""
| Product | Best for |
|---------|----------|
| **Free tools** (`baess.app/tools`) | Lead gen — 27+ calculators, no signup |
| **PV AI Designer Pro** | Full PV workflow: layout → DC/AC → AI BOQ → financials |
| **PV 3D Designer** | Helioscope-style 3D roof + module placement |
| **BESS Designer** | Battery storage sizing, load profiles, BOQ, finance |
| **Solar Simulator** | Fast feasibility / early proposals |
| **AI BOQ Generator** | Standalone BOQ without full design walkthrough |
| **Solar AI Chat** | Structured AI calculations with PDF/Excel export |
""")

    st.markdown("---")
    st.subheader("Deliverability checklist")
    for c in [
        "Send max 50–80 emails/day via Zoho Mail — not Zoho Campaigns",
        "Use plain text only — no images, no HTML, no logo in body",
        "Set up SPF, DKIM, DMARC on your domain before sending anything",
        "Personalise with company name + country at minimum",
        "Send Tuesday–Thursday; skip Monday mornings and Fridays",
    ]:
        st.checkbox(c, key=f"chk_{c[:40]}")

# ── Session log ───────────────────────────────────────────────────────────────
st.markdown("---")
if st.session_state.get("email_log"):
    st.download_button(
        "⬇ Download session log (JSON)",
        json.dumps(st.session_state.email_log, indent=2),
        file_name=f"email_log_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
        mime="application/json",
    )

st.caption("BAESS Labs — baess.app | Cold Email Generator v2.3")
