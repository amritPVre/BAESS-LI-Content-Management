"""
BAESS APP — Outreach Suite  v2.1
Multi-page Streamlit app using st.navigation() (Streamlit ≥ 1.36)

Run with:  streamlit run app.py
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "views"))
from auth_gate import render_logout_sidebar, require_auth
from baess_context import OUTREACH_TOPIC_GROUPS, get_outreach_topics

st.set_page_config(
    page_title="BAESS Outreach Suite",
    page_icon="assets/favicon.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not require_auth():
    st.stop()

# ── Shared CSS (injected once, inherited by all pages) ────────────────────────
st.markdown("""
<style>
    .output-card {
        background: #0f172a;
        border: 1px solid #1e3a5f;
        border-radius: 10px;
        padding: 1.3rem 1.5rem;
        margin-bottom: 1rem;
        color: #e2e8f0;
        font-size: 14px;
        line-height: 1.75;
        white-space: pre-wrap;
    }
    .badge-blue {
        display: inline-block;
        background: #1e3a5f;
        color: #7dd3fc;
        border-radius: 6px;
        padding: 3px 13px;
        font-size: 12px;
        font-weight: 700;
        margin-bottom: 7px;
    }
    .badge-green {
        display: inline-block;
        background: #1a2e1a;
        color: #86efac;
        border-radius: 6px;
        padding: 3px 13px;
        font-size: 12px;
        font-weight: 700;
        margin-bottom: 7px;
    }
    .block-container { padding-top: 1.5rem; }
    .stTextArea textarea { font-size: 14px; }
</style>
""", unsafe_allow_html=True)

# ── Shared sidebar config (rendered on every page) ────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ BAESS Outreach Suite")
    st.caption("baess.app — AI-powered solar engineering")
    render_logout_sidebar()
    st.markdown("---")

    st.subheader("🤖 AI Model")
    st.caption("DeepSeek Chat — key loaded from `.streamlit/secrets.toml`")
    if "api_key" not in st.session_state:
        try:
            st.session_state.api_key = st.secrets["DEEPSEEK_API_KEY"]
        except (KeyError, AttributeError, FileNotFoundError):
            st.session_state.api_key = ""
    if not st.session_state.api_key or st.session_state.api_key == "PASTE_YOUR_DEEPSEEK_API_KEY_HERE":
        st.error("Set `DEEPSEEK_API_KEY` in `.streamlit/secrets.toml`")

    st.markdown("---")
    st.subheader("👤 Sender Identity")
    st.text_input("Your name",      value="Amrit",               key="sender_name")
    st.text_input("Your title",     value="Founder, BAESS Labs",  key="sender_title")
    st.text_input("Reply-to email", value="amrit@baess.app",      key="sender_email")

    st.markdown("---")
    st.subheader("🎯 Active Offer")
    st.selectbox("Lead with", [
        "Founding Member – ₹1,499/month locked forever",
        "14-day free trial, no card needed",
        "Free demo call + platform walkthrough",
    ], key="offer_type")
    st.selectbox("Primary CTA", [
        "Try the free tools at baess.app/tools",
        "Book a 20-min demo of PV AI Designer Pro",
        "Book a 20-min BESS Designer walkthrough",
        "Reply to get a personal walkthrough",
    ], key="cta_type")

    st.markdown("---")
    st.subheader("📌 Topics to highlight")
    st.caption("Select one or more — DMs and emails will lead with these. Leave empty for AI to pick from research.")
    st.multiselect(
        "Products",
        OUTREACH_TOPIC_GROUPS["Products"],
        key="outreach_topics_main",
        placeholder="PV AI Designer Pro, BESS Designer, Free Tools…",
    )
    st.multiselect(
        "Features & sub-specialties",
        OUTREACH_TOPIC_GROUPS["Features & sub-specialties"],
        key="outreach_topics_sub",
        placeholder="AI BOQ, AI Report, Layout + SLD…",
    )
    selected = get_outreach_topics()
    if selected:
        st.caption("Selected: " + " · ".join(selected))

    st.markdown("---")
    st.subheader("📊 Session Stats")
    if "dm_count"    not in st.session_state: st.session_state.dm_count    = 0
    if "email_count" not in st.session_state: st.session_state.email_count = 0
    if "content_weeks" not in st.session_state: st.session_state.content_weeks = 0
    c1, c2, c3 = st.columns(3)
    c1.metric("DMs",    st.session_state.dm_count)
    c2.metric("Emails", st.session_state.email_count)
    c3.metric("Content weeks", st.session_state.content_weeks)

# ── Define pages and run navigation ──────────────────────────────────────────
pg = st.navigation([
    st.Page("views/home.py",                          title="🏠 Home",                         ),
    st.Page("views/1_LinkedIn_DM_Generator.py",       title="💼 LinkedIn DM Generator",        ),
    st.Page("views/2_Cold_Email_Generator.py",        title="📧 Cold Email Generator",         ),
    st.Page("views/3_LinkedIn_Content_Calendar.py",   title="📅 LinkedIn Content Calendar",    ),
])
pg.run()
