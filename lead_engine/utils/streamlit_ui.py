"""Shared Streamlit UI components and styling."""

from __future__ import annotations

import streamlit as st

from database.connection import get_session, reset_engine_cache
from database.init_db import init_database
from models.app_setting import AppSetting


def inject_custom_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'DM Sans', sans-serif;
        }

        .main .block-container {
            padding-top: 2rem;
            max-width: 1200px;
        }

        .baess-header {
            background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0d9488 100%);
            padding: 1.5rem 2rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            color: white;
        }

        .baess-header h1 {
            margin: 0;
            font-size: 1.75rem;
            font-weight: 700;
        }

        .baess-header p {
            margin: 0.25rem 0 0 0;
            opacity: 0.85;
            font-size: 0.95rem;
        }

        div[data-testid="stMetric"] {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 0.75rem 1rem;
        }

        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #0d9488, #14b8a6);
            border: none;
            font-weight: 600;
        }

        .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, #0f766e, #0d9488);
        }

        section[data-testid="stSidebar"] {
            background: #f8fafc;
        }

        .status-pill {
            display: inline-block;
            padding: 0.15rem 0.6rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .pill-success { background: #d1fae5; color: #065f46; }
        .pill-warning { background: #fef3c7; color: #92400e; }
        .pill-danger { background: #fee2e2; color: #991b1b; }
        .pill-info { background: #dbeafe; color: #1e40af; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="baess-header">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> str:
    st.sidebar.markdown("## ⚡ BAESS Lead Engine")
    st.sidebar.caption("Solar industry lead discovery & enrichment")
    st.sidebar.divider()

    ai_provider = st.sidebar.selectbox(
        "AI Provider",
        options=["deepseek", "openai"],
        index=0,
        help="DeepSeek powers Phase 3 company research",
    )
    st.session_state["ai_provider"] = ai_provider

    st.sidebar.divider()
    st.sidebar.markdown("**Crawl Policy**")
    st.sidebar.info(
        "Discovery: 1 page (~5s). Enrichment: 30/batch (20–30s). "
        "Research: 10/batch (~20 min, emails + key people)."
    )

    try:
        from utils.proxy_manager import ProxyManager

        proxy_manager = ProxyManager()
        proxy = proxy_manager.status()
        if proxy["enabled"]:
            st.sidebar.markdown("**Proxies**")
            enf_mode = "ENF+Research" if proxy["enf_proxied"] else "Research only"
            st.sidebar.caption(
                f"{proxy['active']}/{proxy['total']} active · `{proxy['current']}` · {enf_mode}"
            )
            if proxy["active"] < proxy["total"]:
                st.sidebar.caption(
                    f"{proxy.get('exhausted', 0)} proxy(s) cooling down from failures."
                )
            if st.sidebar.button("Reset Proxy Pool", key="reset_proxy_pool"):
                proxy_manager.reset_failures()
                st.sidebar.success("Proxy pool reset")
                st.rerun()
    except Exception:
        pass

    if st.sidebar.button("Initialize / Sync Database"):
        with st.spinner("Creating tables and seeding countries..."):
            try:
                init_database(seed=True)
                _save_ai_provider(ai_provider)
            except Exception as exc:
                reset_engine_cache()
                st.sidebar.error("Database sync failed.")
                if "could not translate host name" in str(exc).lower():
                    st.sidebar.warning(
                        "Cannot reach Neon host — check your internet/DNS connection, "
                        "then retry. If it persists, copy a fresh connection string "
                        "from the Neon dashboard into `.env` as `DATABASE_URL`."
                    )
                else:
                    st.sidebar.warning(str(exc))
            else:
                st.sidebar.success("Database ready")
                st.rerun()

    st.sidebar.divider()
    st.sidebar.caption("v1.0.0 · ENF Solar Directory")
    return ai_provider


def _save_ai_provider(provider: str) -> None:
    try:
        with get_session() as session:
            setting = (
                session.query(AppSetting)
                .filter(AppSetting.key == "ai_provider")
                .first()
            )
            if setting:
                setting.value = provider
            else:
                session.add(
                    AppSetting(
                        key="ai_provider",
                        value=provider,
                        description="Active AI provider",
                    )
                )
    except Exception:
        pass


def ensure_database_initialized() -> None:
    try:
        if not st.session_state.get("db_initialized"):
            init_database(seed=True)
            st.session_state["db_initialized"] = True
        else:
            from database.connection import get_engine
            from database.migrate import run_migrations
            from models import Base

            engine = get_engine()
            Base.metadata.create_all(bind=engine)
            run_migrations(engine)
    except Exception as exc:
        reset_engine_cache()
        st.error(f"Database connection failed: {exc}")
        if "could not translate host name" in str(exc).lower():
            st.info(
                "Your PC could not resolve the Neon database hostname. "
                "Check internet/DNS/VPN, then refresh. If it keeps failing, "
                "update `DATABASE_URL` in `.env` with a fresh string from "
                "[Neon Console](https://console.neon.tech) → Connection Details."
            )
        else:
            st.info(
                "Set `DATABASE_URL` in your `.env` or Streamlit secrets. "
                "Example: `postgresql://user:pass@host/db?sslmode=require`"
            )
        st.stop()
