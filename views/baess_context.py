"""BAESS Labs platform knowledge for outreach prompts — sourced from BAESS_PLATFORM_DOCUMENTATION.md."""

BAESS_PLATFORM_CONTEXT = """
BAESS Labs (https://baess.app) is a browser-based solar engineering and business platform.
One web login spans tools usually split across desktop yield software, CAD plugins, CRM suites, and spreadsheets.

CORE PRODUCTS (authenticated):
- PV AI Designer Pro (/advanced-calculator): Full PV workflow — location, real module/inverter catalog,
  map-based areas with 3D building & shading, DC/AC electrical sizing, losses, yield (NREL PVWatts paths),
  AI BOQ, NPV/IRR financials, AI feasibility reports.
- PV 3D Designer (/pv-3d-designer): Helioscope-style — Google Maps satellite, 3D roof extrusion,
  per-face tilt/azimuth, scale-accurate module placement in 3D.
- Solar Simulator (/solar-calculator): Fast feasibility and proposal-style PV + financial modeling.
- BESS Designer (/bess-designer): Battery storage — load profiles (residential/commercial/industrial/utility),
  sizing, cable sizing, optional DG hybrid, BOQ, costing, financial analysis (10 kWh–10 MWh range).
- AI BOQ Generator (/boq-generator): Standalone bill-of-quantities via AI chat or structured form.
- Solar AI Chat (/solar-ai-chat): Multi-session AI for structured solar calculations with PDF/Excel export.
- Solar Components Library: Thousands of real panel and inverter models from Supabase-backed database.

FREE PUBLIC TOOLS (no login, baess.app/tools): 27+ IEC-framed calculators including string sizing,
inverter sizing, DC/AC cable sizing, ROI/payback/NPV/IRR, BESS sizing, load calculator, voltage drop,
inter-row pitch, GCR, annual PR, earthing, short-circuit — many with PDF reports.

KEY DIFFERENTIATORS FOR OUTREACH:
- Unified web suite: PV layout + electrical BOS + BOQ + finance in one product, zero install.
- AI at choke points: BOQ generation, feasibility reports, chat calculators — targets slow manual takeoffs.
- Real equipment database vs generic placeholder specs.
- Combined PV + BESS in one account (unusual vs PV-only competitors).
- Free tools as trust builders and lead funnel — no signup for basic engineering checks.

POSITIONING (honest, do not overclaim):
- vs PVsyst: web-first, faster collaboration and AI BOQ; not certification-grade hourly simulation depth.
- vs Helioscope/Aurora: engineer-first detailed DC/AC/BOQ tabs; not a full sales CRM OS.
- vs PVcase: browser accessibility for non-CAD users; not Revit-native BIM replacement.
- GTM line: AI-augmented web suite for 10× faster deliverables on mid-complexity projects.

TARGET USERS: EPC/design engineers, developers/PMs doing early feasibility, BESS integrators,
installers and students using free tools.
"""

# Segment-specific angles for templates and prompt hints
SEGMENT_ANGLES = {
    "C&I EPC contractor": {
        "products": ["PV AI Designer Pro", "AI BOQ Generator", "free string sizing & cable calculators"],
        "pain": "Hours on BOQ, string sizing, and DC/AC config before every bid — often across spreadsheets and separate tools.",
        "hook": "End-to-end PV workflow from site map to AI BOQ and financials in one browser session.",
    },
    "Residential installer": {
        "products": ["Free tools at baess.app/tools", "Solar Simulator", "string sizing calculator"],
        "pain": "Still sizing strings and proposals in spreadsheets; hard to quote quickly with real equipment data.",
        "hook": "Browser-based string sizing and ROI tools with a live panel/inverter database — no install.",
    },
    "Large-scale developer": {
        "products": ["Solar Simulator", "PV AI Designer Pro financials", "AI feasibility reports"],
        "pain": "Early-stage screening needs yield + economics fast, before commissioning full PVsyst studies.",
        "hook": "Feasibility with production estimates, BOQ, and NPV/IRR for pre-detailed-yield screening.",
    },
    "BESS integrator": {
        "products": ["BESS Designer", "battery storage sizing calculator (free)", "hybrid PV+BESS paths"],
        "pain": "BESS sizing, load profiles, and financial case usually spread across multiple tools.",
        "hook": "Full BESS study path — load profiles, sizing, cables, BOQ, and finance in one platform.",
    },
    "Solar consultant/designer": {
        "products": ["Free calculator hub", "Solar AI Chat", "panel comparison tool", "AI reports"],
        "pain": "Repeated what-if calculations and narrative reports eat billable hours.",
        "hook": "27+ free calculators plus AI chat with exportable artifacts for client deliverables.",
    },
    "Other": {
        "products": ["Free tools at baess.app/tools", "PV AI Designer Pro"],
        "pain": "Fragmented solar engineering workflow across disconnected tools.",
        "hook": "One web platform for PV design, BOQ, BESS, and financials.",
    },
}

EMAIL_TEMPLATES = {
    "C&I EPC engineer": {
        "Subject": "BOQ + string sizing in one browser session",
        "Opening": "If your team still jumps between spreadsheets for string sizing, DC cable checks, and BOQ before every C&I bid — BAESS Labs runs that workflow in the browser: map-based layout, real inverter/panel catalog, AI BOQ, and financials in one session.",
        "CTA angle": "Try the free string sizing calculator at baess.app/tools — or book a 20-min walkthrough of PV AI Designer Pro.",
        "Why it works": "Names the exact pre-bid pain (BOQ + electrical sizing) and points to a specific free tool as low-friction entry.",
    },
    "Residential installer": {
        "Subject": "String sizing with real panel data — free",
        "Opening": "Most residential installers I talk to are still quoting with generic module specs. BAESS has 27+ free calculators at baess.app/tools — string sizing, ROI, system size — all tied to a live panel/inverter database.",
        "CTA angle": "No signup needed for the free tools. Worth 5 minutes before your next quote.",
        "Why it works": "Peer tone, specific free-tool hook, zero commitment ask.",
    },
    "Large-scale developer / PM": {
        "Subject": "Feasibility screening before PVsyst",
        "Opening": "Before you commission a full hourly yield study, teams often need a fast read on production, BOQ, and NPV/IRR. BAESS Solar Simulator and PV AI Designer Pro do that in the browser — useful for early-stage go/no-go.",
        "CTA angle": "Happy to show a 20-min demo on a sample site, or you can poke around the free ROI calculator first.",
        "Why it works": "Honest positioning vs PVsyst — screening, not bankable sign-off.",
    },
    "BESS integrator": {
        "Subject": "BESS sizing + finance in one place",
        "Opening": "Sizing a BESS project and building the financial case usually means load profiles in one tool, cable sizing in another, and BOQ in a spreadsheet. BAESS BESS Designer covers load profiles, sizing, cables, BOQ, and NPV/IRR in one web workflow.",
        "CTA angle": "There's also a free battery storage sizing calculator at baess.app/tools if you want to test the logic first.",
        "Why it works": "Names the multi-tool fragmentation pain; highlights the combined BESS path.",
    },
    "Solar consultant / designer": {
        "Subject": "27 free solar calculators + AI chat",
        "Opening": "If client what-ifs and report drafts eat your billable hours — BAESS has a free calculator hub (string sizing, cable sizing, ROI, panel comparison) plus Solar AI Chat for structured calculations with PDF export.",
        "CTA angle": "Start with the free tools; no card needed.",
        "Why it works": "Speaks to consultant workflow (repeated calcs + deliverables).",
    },
}

DM_TEMPLATES = {
    "C&I EPC engineer": {
        "Example opener": "Saw you're doing C&I rooftop work at [Company] — curious if your team still runs BOQ and string sizing in separate spreadsheets before bids? I built BAESS Labs to pull that into one browser workflow (map layout → DC/AC sizing → AI BOQ).",
        "Value drop (DM 3)": "We have a free string sizing calculator at baess.app/tools if you want to sanity-check a module/inverter combo — no signup.",
    },
    "BESS integrator": {
        "Example opener": "Noticed [Company]'s work in BESS/hybrid — most integrators I talk to split load profiling, sizing, and finance across different tools. We built a BESS Designer that runs the full path in one web session.",
        "Value drop (DM 3)": "There's a free battery storage sizing calculator on baess.app/tools — takes 2 min.",
    },
    "Developer / PM": {
        "Example opener": "Quick question — when you're screening a site before detailed yield work, what do you use for early BOQ + NPV? We built BAESS for that feasibility layer in the browser.",
        "Value drop (DM 3)": "Free ROI calculator at baess.app/tools if useful for a quick sanity check.",
    },
}

def segment_hint(company_type: str) -> str:
    """Return outreach angle text for a company type."""
    seg = SEGMENT_ANGLES.get(company_type) or SEGMENT_ANGLES["Other"]
    return (
        f"Segment: {company_type}\n"
        f"Pain: {seg['pain']}\n"
        f"Relevant products: {', '.join(seg['products'])}\n"
        f"Angle: {seg['hook']}"
    )


def optional_instructions_block(custom: str) -> str:
    """Append custom instructions only when provided."""
    custom = (custom or "").strip()
    if not custom:
        return ""
    return (
        "\n\nPRIORITY — Custom instructions for this batch "
        "(follow these over default tone/angle when they conflict; ignore if empty):\n"
        f"{custom}"
    )


# ── Outreach topic picker (sidebar) ─────────────────────────────────────────

OUTREACH_TOPIC_GROUPS = {
    "Products": [
        "PV AI Designer Pro",
        "PV 3D Designer",
        "BESS Designer",
        "Solar Simulator",
        "Free Tools",
    ],
    "Features & sub-specialties": [
        "AI BOQ",
        "AI Feasibility Report",
        "Layout + SLD Automation",
        "DC/AC Electrical Sizing",
        "Financial Analysis (NPV/IRR)",
        "Solar AI Chat",
        "Shading & 3D Building",
        "Component Library (panels/inverters)",
    ],
}

OUTREACH_TOPIC_DETAILS = {
    "PV AI Designer Pro": (
        "Flagship PV app (/advanced-calculator): location → component selection → map-based areas → "
        "DC/AC config → losses → yield (PVWatts) → AI BOQ → financials → AI reports."
    ),
    "PV 3D Designer": (
        "Helioscope-style workflow (/pv-3d-designer): satellite map, 3D roof extrusion, "
        "per-face tilt/azimuth, scale-accurate module placement."
    ),
    "BESS Designer": (
        "Full battery path (/bess-designer): load profiles, sizing, cables, optional DG hybrid, "
        "BOQ, costing, financial analysis — 10 kWh to 10 MWh."
    ),
    "Solar Simulator": (
        "Fast feasibility (/solar-calculator): early-stage PV sizing and financial modeling for proposals."
    ),
    "Free Tools": (
        "27+ public calculators at baess.app/tools — string sizing, ROI, BESS sizing, cable sizing, etc. "
        "No login required; strong lead-gen entry point."
    ),
    "AI BOQ": (
        "AI bill-of-quantities: standalone /boq-generator (chat + form) or integrated tab in PV AI Designer Pro. "
        "Targets slow manual quantity takeoffs."
    ),
    "AI Feasibility Report": (
        "AI-generated feasibility-style reports from project results and BOQ — consumes AI credits; "
        "inside PV AI Designer Pro."
    ),
    "Layout + SLD Automation": (
        "Map-based polygon layout, CAD-oriented layout sections, string routing concepts, electrical overlays, "
        "and design summary — reduces manual layout/SLD prep time."
    ),
    "DC/AC Electrical Sizing": (
        "String sizing, DCDB, DC/AC cable sizing, combiners, transformers, central inverter flows — "
        "inside PV AI Designer Pro DC/AC tabs."
    ),
    "Financial Analysis (NPV/IRR)": (
        "NPV, IRR, payback linked to BOQ and production — in PV AI Designer Pro, BESS Designer, and Solar Simulator."
    ),
    "Solar AI Chat": (
        "Multi-session AI for structured solar tasks (/solar-ai-chat) with artifact canvas and PDF/Excel export."
    ),
    "Shading & 3D Building": (
        "3D building tooling and shading configuration in PV AI Designer Pro areas workflow."
    ),
    "Component Library (panels/inverters)": (
        "Thousands of real panel/inverter models from Supabase-backed database used across all calculators."
    ),
}

ALL_OUTREACH_TOPICS = [
    t for group in OUTREACH_TOPIC_GROUPS.values() for t in group
]


def get_outreach_topics() -> list[str]:
    """Read merged topic selection from Streamlit session state."""
    import streamlit as st
    main = st.session_state.get("outreach_topics_main") or []
    sub = st.session_state.get("outreach_topics_sub") or []
    return list(dict.fromkeys(main + sub))  # preserve order, dedupe


def topics_focus_block(topics: list[str] | None = None) -> str:
    """Build prompt section for selected outreach topics. Empty if none selected."""
    if topics is None:
        topics = get_outreach_topics()
    if not topics:
        return (
            "\n- Topics to highlight: (none selected — infer best-fit BAESS products from research "
            "and segment; do not force irrelevant features.)"
        )
    lines = ["\n- Topics to highlight (PRIORITY — lead with these in the message):"]
    for t in topics:
        detail = OUTREACH_TOPIC_DETAILS.get(t, "")
        lines.append(f"  • {t}: {detail}" if detail else f"  • {t}")
    lines.append("- Weave selected topics naturally; if multiple, pick the 1–2 most relevant to this prospect.")
    return "\n".join(lines)
