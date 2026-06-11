"""Simple email + password gate for a private single-user app."""

from __future__ import annotations

import streamlit as st


def _secret(key: str) -> str:
    try:
        return (st.secrets.get(key) or "").strip()
    except (KeyError, AttributeError, FileNotFoundError):
        return ""


def auth_configured() -> bool:
    """True when AUTH_EMAIL and AUTH_PASSWORD are set in secrets."""
    email = _secret("AUTH_EMAIL")
    password = _secret("AUTH_PASSWORD")
    if not email or not password:
        return False
    if "PASTE_" in email or "PASTE_" in password:
        return False
    return True


def _credentials_valid(email: str, password: str) -> bool:
    import secrets as py_secrets

    expected_email = _secret("AUTH_EMAIL").lower()
    expected_password = _secret("AUTH_PASSWORD")
    return (
        py_secrets.compare_digest(email.strip().lower(), expected_email)
        and py_secrets.compare_digest(password, expected_password)
    )


def render_login_page() -> None:
    st.markdown("## BAESS Outreach Suite")
    st.caption("Private app — sign in to continue.")

    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Email", placeholder="you@baess.app")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)

    if submitted:
        if _credentials_valid(email, password):
            st.session_state.authenticated = True
            st.session_state.auth_email = email.strip().lower()
            st.rerun()
        else:
            st.error("Invalid email or password.")


def render_logout_sidebar() -> None:
    if not auth_configured() or not st.session_state.get("authenticated"):
        return
    email = st.session_state.get("auth_email") or _secret("AUTH_EMAIL")
    st.caption(f"Signed in as **{email}**")
    if st.button("Log out", use_container_width=True, key="sidebar_logout"):
        st.session_state.authenticated = False
        st.session_state.pop("auth_email", None)
        st.rerun()


def require_auth() -> bool:
    """
    Enforce login when AUTH_EMAIL / AUTH_PASSWORD are configured in secrets.
    Returns True if the user may proceed, False if the app should st.stop().
    """
    if not auth_configured():
        return True

    if st.session_state.get("authenticated"):
        return True

    render_login_page()
    return False
