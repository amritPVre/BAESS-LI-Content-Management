"""Mount lead_engine package and initialize Neon tables (lead + outreach)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_LE = Path(__file__).resolve().parent.parent / "lead_engine"
if str(_LE) not in sys.path:
    sys.path.insert(0, str(_LE))


def get_ai_provider() -> str:
    return st.session_state.get("lead_ai_provider", "deepseek")


def render_lead_header(title: str, subtitle: str = "") -> None:
    from utils.streamlit_ui import render_header

    render_header(title, subtitle)


def ensure_lead_engine_db() -> None:
    from database.connection import get_engine, reset_engine_cache
    from database.init_db import init_database
    from database.migrate import run_migrations
    from models import Base

    try:
        if not st.session_state.get("lead_db_initialized"):
            init_database(seed=True)
            st.session_state["lead_db_initialized"] = True
        else:
            engine = get_engine()
            Base.metadata.create_all(bind=engine)
            run_migrations(engine)
        from outreach_db import init_outreach_schema

        init_outreach_schema(get_engine())
    except Exception as exc:
        reset_engine_cache()
        st.error(f"Lead engine database error: {exc}")
        st.info("Set `DATABASE_URL` in `.streamlit/secrets.toml` (Neon pooled URI).")
        st.stop()


def sync_lead_database() -> tuple[bool, str]:
    from database.connection import reset_engine_cache
    from database.init_db import init_database

    try:
        reset_engine_cache()
        init_database(seed=True)
        st.session_state["lead_db_initialized"] = True
        return True, "Database synced — tables and countries ready."
    except Exception as exc:
        reset_engine_cache()
        return False, str(exc)
