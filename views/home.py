"""
BAESS Outreach Suite — Home
Reads shared config from st.session_state set by app.py sidebar.
"""

import streamlit as st

st.title("🏠 BAESS Outreach Suite")
st.caption("Lead discovery, AI outreach, and LinkedIn content for BAESS Labs.")

st.markdown("---")
st.subheader("Pipeline")
st.markdown(
    """
1. **Lead Engine** — Discover installers on ENF → enrich profiles → research websites for emails & contacts (Neon DB)
2. **Email Campaigns** — Draft 4-line emails from DB contacts → send via ZeptoMail → sync replies → follow up
3. **LinkedIn DM / manual cold email** — Ad-hoc outreach when not using the lead database
4. **Content Calendar** — Weekly LinkedIn posts with creative prompts
"""
)

st.markdown("---")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("💼 LinkedIn DM Generator")
    st.markdown(
        "Personalised DMs from LinkedIn profile URLs — live research, "
        "bulk paste up to 10 URLs, anti-spam variation."
    )
    st.markdown("**Features:** single DM, follow-ups, bulk generator")

with col2:
    st.subheader("📧 Cold Email Generator")
    st.markdown(
        "Paste up to 10 prospect rows — company web research and "
        "executive-grade cold emails per batch."
    )
    st.markdown("**Features:** batch paste, follow-ups, CSV export")

with col3:
    st.subheader("📅 Content Calendar")
    st.markdown(
        "4 posts/week for the BAESS LinkedIn page — static, carousel, "
        "infographic, and 40-sec reel with full creative prompts."
    )
    st.markdown("**Audience:** founders, CXOs, VPs, engineering & project leaders")

st.markdown("---")

st.subheader("🚀 Getting Started")
st.markdown(
    """
1. **Add your DeepSeek API key** to `.streamlit/secrets.toml`.
2. **Set your sender identity** (name, title, reply-to email).
3. **Pick topics to highlight** in the sidebar — products (PV AI Designer Pro, BESS Designer, Free Tools) and features (AI BOQ, AI Report, Layout + SLD).
4. **Pick your offer and CTA** to match your current campaign.
5. **Navigate** to a generator page using the menu above.
6. **Content calendar:** plan Mon–Thu posts with image/video production prompts.
7. **Cold emails / DMs:** optionally add custom instructions per batch.
"""
)

st.info(
    "Add your DeepSeek API key in `.streamlit/secrets.toml` to unlock the generators. "
    "Outreach copy is grounded in BAESS Labs products: PV AI Designer Pro, BESS Designer, "
    "27+ free calculators at baess.app/tools, and more."
)
