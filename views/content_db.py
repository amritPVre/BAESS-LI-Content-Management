"""Neon PostgreSQL persistence for LinkedIn content calendars and production prompts."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any

import streamlit as st

try:
    import psycopg2
    from psycopg2.extras import Json, RealDictCursor
except ImportError:
    psycopg2 = None  # type: ignore


def _database_url() -> str:
    try:
        return (st.secrets.get("DATABASE_URL") or st.secrets.get("NEON_DATABASE_URL") or "").strip()
    except (KeyError, AttributeError, FileNotFoundError):
        return ""


def db_available() -> bool:
    url = _database_url()
    return bool(psycopg2 and url and "PASTE_" not in url and "postgresql" in url)


@contextmanager
def get_conn():
    if not db_available():
        raise RuntimeError("DATABASE_URL not configured in .streamlit/secrets.toml")
    conn = psycopg2.connect(_database_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS content_calendars (
        id SERIAL PRIMARY KEY,
        week_start DATE UNIQUE NOT NULL,
        week_theme TEXT,
        strategic_focus TEXT,
        calendar_json JSONB NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS content_prompts (
        id SERIAL PRIMARY KEY,
        week_start DATE NOT NULL,
        post_day VARCHAR(20) NOT NULL,
        post_format VARCHAR(32) NOT NULL,
        post_title TEXT,
        prompts_json JSONB NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (week_start, post_day, post_format)
    );

    CREATE INDEX IF NOT EXISTS idx_content_prompts_week
        ON content_prompts (week_start);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)


def prompt_storage_key(week_start: str, post_day: str, post_format: str) -> str:
    return f"{week_start}|{post_day}|{post_format}"


def save_calendar(week_start: str, calendar: dict, strategic_focus: str = "") -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO content_calendars (week_start, week_theme, strategic_focus, calendar_json, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (week_start) DO UPDATE SET
                    week_theme = EXCLUDED.week_theme,
                    strategic_focus = EXCLUDED.strategic_focus,
                    calendar_json = EXCLUDED.calendar_json,
                    updated_at = NOW()
                """,
                (
                    week_start,
                    calendar.get("week_theme", ""),
                    strategic_focus,
                    Json(calendar),
                ),
            )


def load_all_calendars() -> dict[str, dict]:
    if not db_available():
        return {}
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT week_start, calendar_json FROM content_calendars ORDER BY week_start DESC"
            )
            rows = cur.fetchall()
    out = {}
    for row in rows:
        ws = row["week_start"].isoformat() if isinstance(row["week_start"], date) else str(row["week_start"])
        cal = row["calendar_json"]
        if isinstance(cal, str):
            cal = json.loads(cal)
        cal["week_start"] = ws
        out[ws] = cal
    return out


def save_prompts(
    week_start: str,
    post_day: str,
    post_format: str,
    post_title: str,
    prompts: dict,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO content_prompts
                    (week_start, post_day, post_format, post_title, prompts_json, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (week_start, post_day, post_format) DO UPDATE SET
                    post_title = EXCLUDED.post_title,
                    prompts_json = EXCLUDED.prompts_json,
                    updated_at = NOW()
                """,
                (week_start, post_day, post_format, post_title, Json(prompts)),
            )


def load_all_prompts() -> dict[str, dict]:
    if not db_available():
        return {}
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT week_start, post_day, post_format, prompts_json
                FROM content_prompts ORDER BY week_start DESC, post_day
                """
            )
            rows = cur.fetchall()
    out = {}
    for row in rows:
        ws = row["week_start"].isoformat() if isinstance(row["week_start"], date) else str(row["week_start"])
        key = prompt_storage_key(ws, row["post_day"], row["post_format"])
        pr = row["prompts_json"]
        if isinstance(pr, str):
            pr = json.loads(pr)
        out[key] = pr
    return out


def load_prompts_for_week(week_start: str) -> dict[str, dict]:
    if not db_available():
        return {}
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT post_day, post_format, prompts_json
                FROM content_prompts WHERE week_start = %s
                """,
                (week_start,),
            )
            rows = cur.fetchall()
    out = {}
    for row in rows:
        key = prompt_storage_key(week_start, row["post_day"], row["post_format"])
        pr = row["prompts_json"]
        if isinstance(pr, str):
            pr = json.loads(pr)
        out[key] = pr
    return out


def delete_calendar(week_start: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM content_prompts WHERE week_start = %s", (week_start,))
            cur.execute("DELETE FROM content_calendars WHERE week_start = %s", (week_start,))


def sync_from_db(session_state: Any) -> bool:
    """Load calendars + prompts from Neon into session state. Returns True if synced."""
    if not db_available():
        return False
    try:
        init_db()
        session_state.content_calendars = load_all_calendars()
        session_state.content_prompts = load_all_prompts()
        session_state.content_weeks = len(session_state.content_calendars)
        return True
    except Exception as e:
        session_state.db_sync_error = str(e)
        return False
