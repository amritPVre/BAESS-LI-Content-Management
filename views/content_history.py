"""Anti-repetition guardrails — summarize prior generated content for AI prompts."""

from __future__ import annotations

import re
from typing import Any


def _snippet(text: str, n: int = 120) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text[:n] + ("…" if len(text) > n else "")


def collect_calendar_history(
    calendars: dict[str, dict],
    exclude_week: str | None = None,
    max_weeks: int = 16,
) -> list[dict]:
    """Extract themes, titles, hooks from saved content calendars."""
    items = []
    for ws in sorted(calendars.keys(), reverse=True):
        if exclude_week and ws == exclude_week:
            continue
        cal = calendars[ws]
        posts_summary = []
        for p in cal.get("posts", []):
            posts_summary.append({
                "day": p.get("day", ""),
                "post_date": p.get("post_date", ""),
                "post_time": p.get("post_time", ""),
                "format": p.get("format", ""),
                "title": p.get("title", ""),
                "hook": _snippet(p.get("hook", ""), 100),
                "angle": _snippet(p.get("angle", ""), 80),
                "baess_tie_in": p.get("baess_tie_in", ""),
                "competitor_or_trend": _snippet(p.get("competitor_or_trend_angle", ""), 80),
            })
        items.append({
            "week_start": ws,
            "week_theme": cal.get("week_theme", ""),
            "posts": posts_summary,
        })
        if len(items) >= max_weeks:
            break
    return items


def collect_prompt_history(
    prompts: dict[str, dict],
    exclude_week: str | None = None,
    max_items: int = 40,
) -> list[dict]:
    """Extract captions and titles from saved production prompts."""
    items = []
    for key in sorted(prompts.keys(), reverse=True):
        if exclude_week and key.startswith(f"{exclude_week}|"):
            continue
        pr = prompts[key]
        parts = key.split("|")
        items.append({
            "week": parts[0] if parts else "",
            "day": parts[1] if len(parts) > 1 else "",
            "format": parts[2] if len(parts) > 2 else "",
            "caption_snippet": _snippet(pr.get("linkedin_caption", ""), 150),
            "title": pr.get("title", ""),
            "hook": _snippet(pr.get("hook_first_3_sec", ""), 80),
        })
        if len(items) >= max_items:
            break
    return items


def collect_dm_history(dm_log: list[dict], max_items: int = 30) -> list[dict]:
    items = []
    for entry in reversed(dm_log[-max_items:]):
        items.append({
            "name": entry.get("name", ""),
            "company": entry.get("company", ""),
            "role": entry.get("role", ""),
            "stage": entry.get("stage", ""),
            "message_snippet": _snippet(entry.get("message", ""), 100),
        })
    return items


def collect_email_history(email_log: list[dict], max_items: int = 30) -> list[dict]:
    items = []
    for entry in reversed(email_log[-max_items:]):
        items.append({
            "company": entry.get("company", ""),
            "country": entry.get("country", ""),
            "subject": entry.get("subject", ""),
            "body_snippet": _snippet(entry.get("body", ""), 120),
            "stage": entry.get("stage", ""),
        })
    return items


def _format_calendar_lines(history: list[dict]) -> list[str]:
    lines = []
    for w in history:
        lines.append(f"- Week {w['week_start']} theme: {w.get('week_theme', '')}")
        for p in w.get("posts", []):
            lines.append(
                f"  · {p.get('post_date', '')} {p.get('day', '')} {p.get('post_time', '')} "
                f"[{p.get('format', '')}] \"{p.get('title', '')}\" — hook: {p.get('hook', '')} | "
                f"BAESS: {p.get('baess_tie_in', '')}"
            )
            if p.get("competitor_or_trend"):
                lines.append(f"    trend/comp: {p['competitor_or_trend']}")
    return lines


def _format_prompt_lines(history: list[dict]) -> list[str]:
    return [
        f"- {h.get('week', '')} {h.get('day', '')} ({h.get('format', '')}): "
        f"\"{h.get('title', '')}\" — {_snippet(h.get('caption_snippet', ''), 100)}"
        for h in history
    ]


def _format_dm_lines(history: list[dict]) -> list[str]:
    return [
        f"- {h.get('company', '')} / {h.get('name', '')} ({h.get('stage', '')}): "
        f"{h.get('message_snippet', '')}"
        for h in history
    ]


def _format_email_lines(history: list[dict]) -> list[str]:
    return [
        f"- {h.get('company', '')}, {h.get('country', '')} — subject: \"{h.get('subject', '')}\" | "
        f"{h.get('body_snippet', '')}"
        for h in history
    ]


def _load_calendars_from_store() -> dict:
    try:
        import streamlit as st
        if st.session_state.get("content_calendars"):
            return st.session_state.content_calendars
    except Exception:
        pass
    try:
        from content_db import db_available, load_all_calendars
        if db_available():
            return load_all_calendars()
    except Exception:
        pass
    return {}


def _load_prompts_from_store() -> dict:
    try:
        import streamlit as st
        if st.session_state.get("content_prompts"):
            return st.session_state.content_prompts
    except Exception:
        pass
    try:
        from content_db import db_available, load_all_prompts
        if db_available():
            return load_all_prompts()
    except Exception:
        pass
    return {}


def avoid_repetition_block(
    *,
    calendars: dict | None = None,
    prompts: dict | None = None,
    dm_log: list | None = None,
    email_log: list | None = None,
    exclude_week: str | None = None,
    same_batch_messages: list[str] | None = None,
    context: str = "content",
) -> str:
    """
    Build a prompt section listing prior content the AI must not repeat.
    Returns empty string if no history exists.
    """
    if calendars is None:
        calendars = _load_calendars_from_store()
    if prompts is None:
        prompts = _load_prompts_from_store()

    try:
        import streamlit as st
        if dm_log is None:
            dm_log = st.session_state.get("dm_log", [])
        if email_log is None:
            email_log = st.session_state.get("email_log", [])
    except Exception:
        dm_log = dm_log or []
        email_log = email_log or []

    sections: list[str] = []

    if calendars:
        cal_hist = collect_calendar_history(calendars, exclude_week=exclude_week)
        if cal_hist:
            lines = _format_calendar_lines(cal_hist)
            sections.append("PREVIOUS LINKEDIN CONTENT CALENDARS:\n" + "\n".join(lines))

    if prompts:
        pr_hist = collect_prompt_history(prompts, exclude_week=exclude_week)
        if pr_hist:
            lines = _format_prompt_lines(pr_hist)
            sections.append("PREVIOUS PRODUCTION PROMPTS / CAPTIONS:\n" + "\n".join(lines))

    if dm_log:
        dm_hist = collect_dm_history(dm_log)
        if dm_hist:
            lines = _format_dm_lines(dm_hist)
            sections.append("PREVIOUS LINKEDIN DMs:\n" + "\n".join(lines))

    if email_log:
        em_hist = collect_email_history(email_log)
        if em_hist:
            lines = _format_email_lines(em_hist)
            sections.append("PREVIOUS COLD EMAILS:\n" + "\n".join(lines))

    if same_batch_messages:
        lines = [f"- {_snippet(m, 100)}" for m in same_batch_messages if m.strip()]
        if lines:
            sections.append("ALREADY GENERATED IN THIS BATCH (must differ):\n" + "\n".join(lines))

    if not sections:
        return ""

    return (
        f"\n\nMANDATORY — ANTI-REPETITION GUARDRAIL ({context}):\n"
        "Review all prior content below. You MUST NOT repeat or closely paraphrase:\n"
        "- Week themes, post titles, hooks, angles, BAESS product angles, competitive frames, or trend angles\n"
        "- Subject lines, opening sentences, caption structures, or CTA phrasing\n"
        "- DM/email opener patterns already used\n\n"
        "Choose fresh topic combinations, fresh hooks, and distinct framing. "
        "If a BAESS product or competitor comparison was used recently, use a different one.\n\n"
        + "\n\n".join(sections)
    )


def topics_used_flat(calendars: dict, exclude_week: str | None = None) -> set[str]:
    """Quick set of normalized titles/themes for programmatic checks."""
    used: set[str] = set()
    for ws, cal in calendars.items():
        if exclude_week and ws == exclude_week:
            continue
        if cal.get("week_theme"):
            used.add(cal["week_theme"].strip().lower())
        for p in cal.get("posts", []):
            for field in ("title", "hook", "baess_tie_in", "angle"):
                val = (p.get(field) or "").strip().lower()
                if val:
                    used.add(val)
    return used
