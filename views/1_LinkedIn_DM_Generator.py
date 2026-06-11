"""
BAESS Outreach Suite — LinkedIn DM Generator (Page 1)
Reads all config from st.session_state set by app.py sidebar.
Prospects are loaded via LinkedIn profile URL → live scrape → AI research → DM.
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
from baess_context import BAESS_PLATFORM_CONTEXT, DM_TEMPLATES, optional_instructions_block, topics_focus_block
from content_history import avoid_repetition_block
from linkedin_research import (
    validate_linkedin_url,
    normalize_linkedin_url,
    run_full_research,
)

st.title("💼 LinkedIn DM Generator")
st.caption(
    "Paste a LinkedIn profile URL — the app fetches public data, researches the person "
    "and their company, then writes personalised DMs."
)

# ── Guard ─────────────────────────────────────────────────────────────────────
if not get_api_key():
    st.warning("⚠️ Add your DeepSeek API key to `.streamlit/secrets.toml`.")
    st.stop()

# ── Pull shared config ────────────────────────────────────────────────────────
offer_type   = st.session_state.get("offer_type",   "Founding Member – ₹1,499/month locked forever")
sender_name  = st.session_state.get("sender_name",  "Amrit")
sender_role  = st.session_state.get("sender_title", "Founder, BAESS Labs")

MAX_BATCH = 10

# Distinct opener/structure patterns — rotated across batch so DMs don't look templated
DM_VARIATION_STYLES = [
    "Open with a genuine question about their work. Avoid 'Hi [Name], hope you're well'.",
    "Open with a specific observation about their company — statement first, question later.",
    "Start with a peer pain point in their segment, then ask if it resonates. No product name in sentence 1.",
    "Open with something specific from the research hook — casual, as if you already know their space.",
    "Use a short compliment tied to one research detail, then pivot to curiosity. Max 3 sentences total.",
    "Start mid-thought — no formal greeting. Example rhythm: observation → why you're reaching out → soft ask.",
    "Lead with their country/market context, then connect to one BAESS topic. Vary sentence lengths.",
    "Terse format: one context sentence, one value sentence, one CTA. Under 60 words.",
    "Open with 'Quick question —' or similar, but do NOT copy that phrase verbatim — invent your own casual hook.",
    "Story-style opener: 'Was looking at [company]'s work on X…' — conversational, founder voice.",
]

if "linkedin_research_cache" not in st.session_state:
    st.session_state.linkedin_research_cache = {}


def parse_pasted_urls(text: str, max_urls: int = MAX_BATCH) -> tuple[list[str], str | None]:
    """One LinkedIn URL per line, max 10."""
    lines = []
    for raw in text.strip().splitlines():
        url = raw.strip()
        if url and not url.lower().startswith("linkedin_url"):
            lines.append(normalize_linkedin_url(url))
    warning = None
    if len(lines) > max_urls:
        warning = f"Only the first {max_urls} URLs will be processed."
        lines = lines[:max_urls]
    return lines, warning


# ── System prompts ────────────────────────────────────────────────────────────
DM_SYSTEM = f"""You are a B2B outreach specialist writing LinkedIn DMs for BAESS Labs.
The DMs are sent by the founder. Use accurate product names and honest positioning.

{BAESS_PLATFORM_CONTEXT}

Rules:
- Sound like a real person, not a sales bot. Conversational, warm, direct.
- Max 4 sentences for the first DM. No bullet points. No jargon overload.
- Reference something specific from the research (person role OR company detail).
- Mention the most relevant BAESS product naturally (free tools, PV AI Designer Pro, BESS Designer, etc.).
- Do NOT overclaim vs PVsyst/Helioscope — position as faster web workflow and AI BOQ, not bankable yield replacement.
- End with a single soft call to action — not a hard pitch.
- NEVER use: 'revolutionize', 'game-changer', 'excited to share', 'hope this finds you well'.
- If an anti-repetition block is provided, MUST use fresh angles — never reuse prior hooks, openers, or CTAs.
- Output ONLY the DM text. No subject line, no preamble, no commentary."""

FOLLOWUP_SYSTEM = f"""You are writing a LinkedIn follow-up DM for BAESS Labs.
Tone: genuine curiosity, not pushy. Shorter than the previous message.
Goal: book a 20-minute demo call or nudge toward baess.app/tools free calculators.
Use the research brief and BAESS product fit to stay specific.

{BAESS_PLATFORM_CONTEXT}

Output ONLY the DM text. No labels, no commentary."""

# ── Prompt builders ───────────────────────────────────────────────────────────
def _research_block(r: dict) -> str:
    hooks = r.get("outreach_hooks") or []
    hooks_txt = "\n".join(f"  - {h}" for h in hooks) if hooks else "  (none)"
    products = r.get("recommended_baess_products") or []
    products_txt = ", ".join(products) if products else "infer from role/company"
    return f"""Prospect research brief:
- Name: {r.get('name', '')}
- Role: {r.get('role', '')}
- Company: {r.get('company', '')}
- Location: {r.get('location') or 'not specified'}
- Person (light): {r.get('person_summary', '')}
- Company (deep): {r.get('company_research', '')}
- Recommended BAESS products: {products_txt}
- Personalisation hooks:
{hooks_txt}
- LinkedIn: {r.get('linkedin_url', '')}
- Data confidence: {r.get('data_confidence', 'unknown')}"""


def build_dm_prompt(
    research: dict,
    custom_instructions: str = "",
    variation_style: str = "",
    prior_dms: list[str] | None = None,
):
    anti_spam = ""
    if variation_style:
        anti_spam += f"\n- REQUIRED structure/style for this DM: {variation_style}"
    if prior_dms:
        anti_spam += "\n- Do NOT reuse openings, phrases, CTA wording, or sentence patterns from these prior DMs in this batch:"
        for i, snippet in enumerate(prior_dms, 1):
            preview = snippet[:150] + "…" if len(snippet) > 150 else snippet
            anti_spam += f"\n  [{i}] {preview}"
        anti_spam += (
            "\n- This DM must be structurally and lexically distinct — different opener type, "
            "sentence count, rhythm, and CTA phrasing. LinkedIn flags identical templates as spam."
        )
    history_avoid = avoid_repetition_block(
        dm_log=st.session_state.get("dm_log", []),
        calendars=st.session_state.get("content_calendars", {}),
        same_batch_messages=prior_dms,
        context="LinkedIn DM",
    )
    return f"""{_research_block(research)}

Write a personalised first LinkedIn DM using the research above.
- Offer to mention naturally: {offer_type}
- Sender: {sender_name}, {sender_role}
- Free tools entry point: baess.app/tools (no signup for calculators)
{topics_focus_block()}
Must feel written specifically for this person, not a template.{history_avoid}{anti_spam}{optional_instructions_block(custom_instructions)}"""

def build_followup_prompt(research: dict, num: int, context: str, custom_instructions: str = ""):
    defaults = {
        2: "They saw the DM but did not reply after 4 days.",
        3: "Still no reply after 7 days total.",
        4: "They replied with interest but haven't booked a call yet.",
        5: "They asked for more info but went quiet again.",
    }
    instructions = {
        2: "Gentle nudge. Reference something specific from the research. End with a question.",
        3: "2 sentences max. Offer a relevant free tool at baess.app/tools for their role. No hard ask.",
        4: "They showed interest. Ask directly for a 20-min call. Casual tone.",
        5: "Final message. Acknowledge you've reached out a few times. Leave door open. No pressure.",
    }
    return f"""{_research_block(research)}

Write follow-up DM #{num} for this prospect.
- Situation: {context or defaults.get(num, 'No reply yet.')}
- Instruction: {instructions.get(num, 'Follow up professionally.')}
- Offer: {offer_type}
- Sender: {sender_name}, {sender_role}
{topics_focus_block()}{avoid_repetition_block(dm_log=st.session_state.get("dm_log", []), context="LinkedIn follow-up DM")}{optional_instructions_block(custom_instructions)}"""

# ── Research UI helper ────────────────────────────────────────────────────────
def get_or_run_research(url: str, force: bool = False) -> dict | None:
    url = normalize_linkedin_url(url)
    if not validate_linkedin_url(url):
        st.warning("Please enter a valid LinkedIn profile URL (e.g. https://linkedin.com/in/username).")
        return None

    cached = st.session_state.linkedin_research_cache.get(url)
    if cached and not force:
        return cached

    with st.spinner("Fetching profile → researching company → synthesising brief..."):
        research = run_full_research(url, call_ai)
    if research:
        st.session_state.linkedin_research_cache[url] = research
    return research


def show_research_summary(research: dict):
    conf = research.get("data_confidence", "unknown")
    conf_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "⚪")
    with st.expander(f"{conf_icon} Research brief — {research.get('name', 'Prospect')} @ {research.get('company', '?')}", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Name", research.get("name", "—"))
        c2.metric("Role", (research.get("role") or "—")[:40])
        c3.metric("Confidence", conf)
        st.markdown(f"**Person:** {research.get('person_summary', '')}")
        st.markdown(f"**Company:** {research.get('company_research', '')}")
        if research.get("outreach_hooks"):
            st.markdown("**Hooks:** " + " · ".join(f"_{h}_" for h in research["outreach_hooks"]))
        if research.get("recommended_baess_products"):
            st.markdown("**BAESS fit:** " + ", ".join(research["recommended_baess_products"]))
        scrape = research.get("profile_scrape", {})
        if scrape.get("fetch_error"):
            st.caption(f"⚠️ Profile fetch limited: {scrape['fetch_error']}. AI filled gaps from URL + web search.")

# ── Render helper ─────────────────────────────────────────────────────────────
def render_output(label, text, badge="badge-blue"):
    st.markdown(f'<div class="{badge}">{label}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="output-card">{text}</div>', unsafe_allow_html=True)
    st.code(text, language=None)
    st.caption("👆 Click the copy icon to grab the text.")

def log_dm(research: dict, text: str, stage: str):
    st.session_state.dm_count += 1
    st.session_state.setdefault("dm_log", []).append({
        "timestamp": datetime.now().isoformat(),
        "linkedin_url": research.get("linkedin_url", ""),
        "name": research.get("name", ""),
        "role": research.get("role", ""),
        "company": research.get("company", ""),
        "message": text,
        "stage": stage,
    })

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["✍️ Single DM", "🔄 Follow-up Sequence", "📋 Bulk Generator", "📖 DM Templates"])

# ── Tab 1: Single DM ──────────────────────────────────────────────────────────
with tab1:
    st.subheader("Generate a personalised first DM")
    p_url = st.text_input(
        "LinkedIn profile URL *",
        placeholder="https://www.linkedin.com/in/rajesh-kumar",
        key="single_url",
    )
    dm_custom = st.text_area(
        "Custom instructions (optional)",
        placeholder="e.g. Mention we just launched BESS Designer. Keep it under 3 sentences. Focus on their utility-scale work.",
        height=72,
        key="dm_custom",
    )
    col_a, col_b = st.columns(2)
    with col_a:
        do_research_only = st.button("🔍 Research only", use_container_width=True)
    with col_b:
        do_generate = st.button("⚡ Research & Generate DM", type="primary", use_container_width=True)

    if do_research_only and p_url:
        research = get_or_run_research(p_url, force=True)
        if research:
            show_research_summary(research)

    if do_generate and p_url:
        research = get_or_run_research(p_url)
        if research:
            show_research_summary(research)
            with st.spinner("Writing personalised DM..."):
                text = call_ai(DM_SYSTEM, build_dm_prompt(research, dm_custom))
            if text:
                log_dm(research, text, "DM 1")
                render_output("📨 First DM", text)

# ── Tab 2: Follow-up sequence ─────────────────────────────────────────────────
with tab2:
    st.subheader("Follow-up DM sequence")
    fu_url = st.text_input(
        "LinkedIn profile URL *",
        placeholder="https://www.linkedin.com/in/rajesh-kumar",
        key="fu_url",
    )

    STAGES = {
        "DM 2 — No reply after 4 days (gentle nudge)":          2,
        "DM 3 — No reply after 7 days (short value drop)":       3,
        "DM 4 — They replied with interest → book the call":     4,
        "DM 5 — Final message, leave the door open":             5,
    }
    fu_label   = st.selectbox("Which follow-up?", list(STAGES.keys()))
    fu_num     = STAGES[fu_label]
    fu_context = st.text_area(
        "Situation context (optional)",
        placeholder="They commented on a BESS sizing post last week.",
        height=72,
        key="fu_ctx",
    )
    fu_custom = st.text_area(
        "Custom instructions (optional)",
        placeholder="e.g. DM 3 should only mention the free BESS sizing calculator.",
        height=72,
        key="fu_custom",
    )

    st.info("""
**5-message sequence:**
| Stage | When | Purpose |
|-------|------|---------|
| DM 1 | Day 1 | Personalised intro (Tab 1) |
| DM 2 | Day 4 | Gentle nudge + question |
| DM 3 | Day 7 | Short value drop, no ask |
| DM 4 | On interest | Demo call booking |
| DM 5 | Day 14 | Final, leave door open |
""")

    if st.button("⚡ Research & Generate Follow-up DM", type="primary", use_container_width=True):
        if not fu_url:
            st.warning("Please enter a LinkedIn profile URL.")
        else:
            research = get_or_run_research(fu_url)
            if research:
                show_research_summary(research)
                with st.spinner(f"Writing DM {fu_num}..."):
                    text = call_ai(
                        FOLLOWUP_SYSTEM,
                        build_followup_prompt(research, fu_num, fu_context, fu_custom),
                    )
                if text:
                    log_dm(research, text, f"DM {fu_num}")
                    render_output(f"📨 Follow-up DM {fu_num}", text, "badge-green")

# ── Tab 3: Bulk generator ─────────────────────────────────────────────────────
with tab3:
    st.subheader(f"Paste up to {MAX_BATCH} LinkedIn profile URLs")
    st.markdown(
        "One URL per line. The app researches each profile live and writes **unique** DMs — "
        "varied structure and wording so LinkedIn does not flag them as spam."
    )

    with st.expander("📌 Format & example"):
        st.markdown("""
```
https://www.linkedin.com/in/prospect-one
https://www.linkedin.com/in/prospect-two
linkedin.com/in/prospect-three
```

You can also upload a CSV (see below). Header row `linkedin_url` is optional when pasting is skipped.
""")

    bulk_paste = st.text_area(
        "Paste URLs here (one per line)",
        height=200,
        placeholder=(
            "https://www.linkedin.com/in/rajesh-kumar\n"
            "https://www.linkedin.com/in/priya-shah\n"
            "https://www.linkedin.com/in/john-smith-solar"
        ),
        key="bulk_paste_urls",
    )

    dm_bulk_custom = st.text_area(
        "Custom instructions (optional)",
        placeholder="e.g. Lead with free tools at baess.app/tools. Do not mention pricing.",
        height=72,
        key="dm_bulk_custom",
    )

    if bulk_paste.strip():
        preview_urls, parse_warn = parse_pasted_urls(bulk_paste)
        if parse_warn:
            st.warning(parse_warn)
        if preview_urls:
            st.markdown(f"**Preview — {len(preview_urls)} URL(s) detected**")
            st.dataframe(
                [{"#": i + 1, "linkedin_url": u} for i, u in enumerate(preview_urls)],
                use_container_width=True,
                hide_index=True,
            )

    if st.button(f"⚡ Research & Generate DMs (max {MAX_BATCH})", type="primary", use_container_width=True):
        urls, err = parse_pasted_urls(bulk_paste)
        if not urls:
            st.warning(err or "Paste at least one LinkedIn profile URL.")
        else:
            if err:
                st.warning(err)

            results, prior_dms = [], []
            prog = st.progress(0)
            status = st.empty()

            for i, url in enumerate(urls):
                status.text(f"{i + 1}/{len(urls)} — Researching {url[:55]}…")
                if not validate_linkedin_url(url):
                    results.append({"linkedin_url": url, "generated_dm": "", "error": "Invalid URL", "stage": "DM 1"})
                    prog.progress((i + 1) / len(urls))
                    continue

                research = get_or_run_research(url)
                if not research:
                    results.append({"linkedin_url": url, "generated_dm": "", "error": "Research failed", "stage": "DM 1"})
                    prog.progress((i + 1) / len(urls))
                    continue

                variation = DM_VARIATION_STYLES[i % len(DM_VARIATION_STYLES)]
                prospect_label = research.get("name") or url[:30]
                status.text(f"{i + 1}/{len(urls)} - Writing DM for {prospect_label}...")
                dm = call_ai(
                    DM_SYSTEM,
                    build_dm_prompt(
                        research,
                        st.session_state.get("dm_bulk_custom", ""),
                        variation_style=variation,
                        prior_dms=prior_dms,
                    ),
                )
                results.append({
                    "linkedin_url": url,
                    "name": research.get("name", ""),
                    "role": research.get("role", ""),
                    "company": research.get("company", ""),
                    "variation_style": variation[:60],
                    "generated_dm": dm,
                    "stage": "DM 1",
                    "generated_at": datetime.now().isoformat(),
                })
                if dm:
                    prior_dms.append(dm)
                    log_dm(research, dm, "DM 1")
                prog.progress((i + 1) / len(urls))

            ok = [r for r in results if r.get("generated_dm")]
            status.success(f"✅ {len(ok)} DM(s) generated ({len(results) - len(ok)} failed). Each uses a distinct structure.")

            if ok:
                st.markdown("---")
                st.subheader("Research summaries")
                for url in urls:
                    cached = st.session_state.linkedin_research_cache.get(normalize_linkedin_url(url))
                    if cached:
                        show_research_summary(cached)

                st.markdown("---")
                st.subheader("Generated DMs")
                for r in ok:
                    render_output(
                        f"📨 {r.get('name', '')} @ {r.get('company', '')}",
                        r["generated_dm"],
                    )

            if results:
                out = io.StringIO()
                w = csv.DictWriter(out, fieldnames=list(results[0].keys()))
                w.writeheader()
                w.writerows(results)
                st.download_button(
                    "⬇ Download batch as CSV", out.getvalue(),
                    file_name=f"baess_dms_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv", use_container_width=True,
                )

    st.markdown("---")
    with st.expander("⬆ Or upload CSV instead"):
        SAMPLE = (
            "linkedin_url\n"
            "https://www.linkedin.com/in/example-prospect-1\n"
            "https://www.linkedin.com/in/example-prospect-2\n"
        )
        st.download_button("⬇ Download sample CSV", SAMPLE,
                           file_name="linkedin_urls.csv", mime="text/csv", key="dm_csv_sample")
        uploaded = st.file_uploader("Upload LinkedIn URLs CSV", type="csv", key="dm_csv")
        if uploaded:
            try:
                rows = list(csv.DictReader(io.StringIO(uploaded.read().decode("utf-8"))))[:MAX_BATCH]
                urls_from_csv = [r.get("linkedin_url", "").strip() for r in rows if r.get("linkedin_url", "").strip()]
                if urls_from_csv:
                    st.success(f"Loaded {len(urls_from_csv)} URL(s). Paste into the box above or generate from CSV:")
                    st.code("\n".join(urls_from_csv))
            except Exception as e:
                st.error(f"CSV error: {e}")

# ── Tab 4: DM Templates ───────────────────────────────────────────────────────
with tab4:
    st.subheader("LinkedIn DM templates by segment")
    st.caption("Reference examples — AI personalises from live research; do not copy verbatim.")
    for seg, d in DM_TEMPLATES.items():
        with st.expander(f"💼 {seg}"):
            st.markdown(f"**Example opener:** {d['Example opener']}")
            st.markdown(f"**Value drop (DM 3):** {d['Value drop (DM 3)']}")

# ── Session log ───────────────────────────────────────────────────────────────
st.markdown("---")
if st.session_state.get("dm_log"):
    st.download_button(
        "⬇ Download session log (JSON)",
        json.dumps(st.session_state.dm_log, indent=2),
        file_name=f"dm_log_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
        mime="application/json",
    )

st.caption("BAESS Labs — baess.app | LinkedIn DM Generator v2.4")
