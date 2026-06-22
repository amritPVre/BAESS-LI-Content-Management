"""AI email drafting for DB-backed outreach campaigns."""

from __future__ import annotations

from typing import Any

import streamlit as st

from ai_client import call_ai, get_api_key
from baess_context import FOUR_LINE_OUTREACH_STRUCTURE, load_outreach_knowledge, topics_focus_block
from content_history import avoid_repetition_block

_OUTREACH_DOCS = load_outreach_knowledge()

EMAIL_SYSTEM = f"""You are a B2B cold email specialist for BAESS Labs (https://baess.app).

{FOUR_LINE_OUTREACH_STRUCTURE}

PRODUCT & PLATFORM KNOWLEDGE (use for line 2 — pick 1–2 problems max):
{_OUTREACH_DOCS}

Rules:
- Subject line: under 8 words, specific to their situation.
- Body: exactly 4 content sentences (them → value → question → CTA). Plain text.
- Signature: sender name, title, email from the prompt.
- Output format exactly:
  SUBJECT: [subject line]
  ---
  [email body with greeting, 4 sentences, signature]"""

FOLLOWUP_SYSTEM = f"""You are writing a follow-up email for BAESS Labs cold outreach.
Shorter than the original. Use company context below.

PRODUCT & PLATFORM KNOWLEDGE:
{_OUTREACH_DOCS}

Output format exactly:
SUBJECT: [subject line]
---
[email body]
No commentary."""


def contact_to_research(row: dict[str, Any]) -> dict[str, Any]:
    """Map Neon contact row to cold-email research dict."""
    parts = []
    if row.get("battery_storage"):
        parts.append(f"Battery/storage: {row['battery_storage']}")
    if row.get("installation_size"):
        parts.append(f"Installation scale: {row['installation_size']}")
    if row.get("operating_area"):
        parts.append(f"Operating area: {row['operating_area']}")
    return {
        "company": row.get("company_name", ""),
        "country": row.get("country", ""),
        "website": row.get("website") or "",
        "email": row.get("email") or "",
        "name": row.get("name") or "",
        "title": row.get("title") or "",
        "company_type": "Other",
        "company_research": ". ".join(parts) or "Solar installer from ENF directory.",
        "contact_greeting": f"Hi {row['name'].split()[0]}," if row.get("name") else "Hi there,",
    }


def parse_email(raw: str) -> tuple[str, str]:
    if "---" in raw:
        parts = raw.split("---", 1)
        return parts[0].replace("SUBJECT:", "").strip(), parts[1].strip()
    return "BAESS outreach", raw.strip()


def build_initial_prompt(research: dict[str, Any], custom: str = "") -> str:
    offer = st.session_state.get("offer_type", "")
    cta = st.session_state.get("cta_type", "")
    sender_name = st.session_state.get("sender_name", "Amrit")
    sender_title = st.session_state.get("sender_title", "Founder, BAESS Labs")
    sender_email = st.session_state.get("sender_email", "amrit@baess.app")
    history = avoid_repetition_block(
        email_log=st.session_state.get("email_log", []),
        context="campaign email",
    )
    return f"""Company research brief:
- Company: {research.get('company')}
- Country: {research.get('country')}
- Website: {research.get('website')}
- Contact: {research.get('name')} | {research.get('title')}
- To email: {research.get('email')}
- Context: {research.get('company_research')}

Write a cold email using the mandatory 4-line structure.
- Offer (line 4): {offer}
- CTA: {cta}
- Sender: {sender_name}, {sender_title}, {sender_email}
{topics_focus_block()}
{history}
{custom}"""


def build_followup_prompt(
    research: dict[str, Any],
    sequence_num: int,
    original_subject: str,
    original_body: str,
) -> str:
    fu_num = max(1, sequence_num - 1)
    instructions = {
        1: "First follow-up — gentle bump, 3–4 sentences, mention baess.app/tools.",
        2: "Second follow-up — shorter, friendly break-up tone, leave door open.",
    }
    return f"""Original email subject: {original_subject}
Original body excerpt: {original_body[:600]}

Company: {research.get('company')} ({research.get('country')})
Contact: {research.get('name')} | {research.get('email')}

Write follow-up #{fu_num}.
Instruction: {instructions.get(fu_num, 'Professional follow-up.')}
Sender: {st.session_state.get('sender_name')}, {st.session_state.get('sender_email')}
{topics_focus_block()}"""


def generate_initial_email(research: dict[str, Any], custom: str = "") -> tuple[str, str]:
    if not get_api_key():
        return "", ""
    raw = call_ai(EMAIL_SYSTEM, build_initial_prompt(research, custom), max_tokens=800)
    return parse_email(raw) if raw else ("", "")


def generate_followup_email(
    research: dict[str, Any],
    sequence_num: int,
    original_subject: str,
    original_body: str,
) -> tuple[str, str]:
    if not get_api_key():
        return "", ""
    prompt = build_followup_prompt(
        research, sequence_num, original_subject, original_body
    )
    raw = call_ai(FOLLOWUP_SYSTEM, prompt, max_tokens=600)
    return parse_email(raw) if raw else ("", "")
