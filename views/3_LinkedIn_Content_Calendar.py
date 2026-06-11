"""
BAESS Outreach Suite — LinkedIn Content Calendar & Prompt Generator
Weekly 4-post plan + production prompts — calendar grid view + Neon persistence.
"""

import streamlit as st
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ai_client import get_api_key, call_ai
from baess_context import topics_focus_block
from content_db import (
    db_available,
    sync_from_db,
    save_calendar,
    save_prompts,
    delete_calendar,
    prompt_storage_key,
    load_prompts_for_week,
)
from content_history import avoid_repetition_block
from linkedin_content import (
    WEEKLY_SLOTS,
    FORMAT_LABELS,
    LINKEDIN_TIMING_RESEARCH,
    CALENDAR_SYSTEM,
    PROMPT_SYSTEMS,
    build_calendar_user_prompt,
    build_prompt_user_prompt,
    week_start_options,
    sort_posts_chronologically,
    format_schedule_label,
    slot_for_format,
    normalize_day_key,
    FULL_DAYS,
    DAY_LABELS,
    _parse_json,
    EXECUTIVE_AUDIENCE,
    PIXAR_CHARACTER,
)

# ── Calendar grid CSS ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    .cal-week-banner {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem 1.4rem;
        margin-bottom: 1.2rem;
        color: #e2e8f0;
    }
    .cal-week-banner h3 { margin: 0 0 0.3rem 0; color: #7dd3fc; font-size: 1.1rem; }
    .cal-week-banner p { margin: 0; color: #94a3b8; font-size: 0.9rem; }
    .cal-day-card {
        background: #0f172a;
        border: 1px solid #1e3a5f;
        border-radius: 10px;
        padding: 1rem;
        min-height: 220px;
        margin-bottom: 0.5rem;
    }
    .cal-day-card.has-prompts { border-color: #166534; }
    .cal-day-header {
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 0.6rem; padding-bottom: 0.5rem; border-bottom: 1px solid #1e3a5f;
    }
    .cal-day-name { font-weight: 700; color: #7dd3fc; font-size: 0.95rem; }
    .cal-day-date { color: #64748b; font-size: 0.8rem; }
    .cal-time-badge {
        display: inline-block; background: #422006; color: #fcd34d;
        border-radius: 6px; padding: 2px 8px; font-size: 0.72rem; font-weight: 700;
        margin-bottom: 0.35rem;
    }
    .cal-format-badge {
        display: inline-block; background: #1e3a5f; color: #bae6fd;
        border-radius: 6px; padding: 2px 8px; font-size: 0.72rem; font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .cal-engage-badge {
        display: inline-block; background: #14532d; color: #86efac;
        border-radius: 6px; padding: 2px 8px; font-size: 0.68rem; font-weight: 600;
        margin-left: 4px;
    }
    .cal-post-title { color: #f1f5f9; font-weight: 600; font-size: 0.92rem; margin-bottom: 0.4rem; line-height: 1.35; }
    .cal-hook { color: #94a3b8; font-size: 0.82rem; line-height: 1.45; margin-bottom: 0.5rem; }
    .cal-meta { color: #64748b; font-size: 0.75rem; margin-top: 0.4rem; }
    .cal-status-done { color: #86efac; font-size: 0.75rem; font-weight: 600; }
    .cal-status-pending { color: #fbbf24; font-size: 0.75rem; font-weight: 600; }
    .cal-empty-day {
        background: #0a0f1a; border: 1px dashed #334155; border-radius: 10px;
        padding: 1rem; min-height: 120px; color: #475569; font-size: 0.85rem;
        text-align: center; display: flex; align-items: center; justify-content: center;
    }
</style>
""", unsafe_allow_html=True)

st.title("📅 LinkedIn Content Calendar")
st.caption(
    "Plan 4 executive-grade posts per week — stored in Neon so your plans survive reloads."
)

if not get_api_key():
    st.warning("⚠️ Add your DeepSeek API key to `.streamlit/secrets.toml`.")
    st.stop()

if "content_calendars" not in st.session_state:
    st.session_state.content_calendars = {}
if "content_prompts" not in st.session_state:
    st.session_state.content_prompts = {}

if not st.session_state.get("db_synced"):
    if db_available():
        if sync_from_db(st.session_state):
            st.session_state.db_synced = True
    else:
        st.info(
            "Add `DATABASE_URL` (Neon PostgreSQL) to `.streamlit/secrets.toml` to persist calendars "
            "across reloads. Until then, data is session-only."
        )

if st.session_state.get("db_sync_error"):
    st.error(f"Database sync error: {st.session_state.db_sync_error}")

# ── Helpers ───────────────────────────────────────────────────────────────────
def _week_dates(week_start_str: str) -> list[datetime]:
    start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
    return [datetime.combine(start + timedelta(days=i), datetime.min.time()) for i in range(7)]


def _posts_by_day(cal: dict) -> dict[str, dict]:
    out = {}
    for p in cal.get("posts", []):
        key = normalize_day_key(p.get("day", ""))
        if key:
            out[key] = p
    return out


def render_schedule_table(cal: dict):
    """Chronological posting schedule with precision timing."""
    posts = sort_posts_chronologically(cal.get("posts", []))
    if not posts:
        return
    rows = []
    for i, p in enumerate(posts, 1):
        slot = slot_for_format(p.get("format", ""))
        rows.append({
            "#": i,
            "Format": f"{slot.get('icon', '')} {FORMAT_LABELS.get(p.get('format', ''), p.get('format', ''))}",
            "Day": p.get("day", ""),
            "Date": p.get("post_date", ""),
            "Time": p.get("post_time", ""),
            "Timezone": p.get("timezone", cal.get("audience_timezone", "")),
            "UTC": p.get("time_utc", ""),
            "Engagement": p.get("engagement_score", ""),
            "Title": p.get("title", ""),
        })
    st.markdown("#### 📆 Posting schedule — optimal days & times")
    st.dataframe(rows, use_container_width=True, hide_index=True)
    with st.expander("Why these slots? (LinkedIn B2B research)"):
        st.markdown(LINKEDIN_TIMING_RESEARCH)


def render_calendar_grid(week_start: str, cal: dict, use_post_expanders: bool = True):
    """7-day week view with posts on research-backed days/times."""
    theme = cal.get("week_theme", "—")
    tz = cal.get("audience_timezone", "IST")
    st.markdown(
        f'<div class="cal-week-banner"><h3>Week of {week_start}</h3>'
        f'<p><strong>Theme:</strong> {theme}<br>'
        f'<strong>Audience timezone:</strong> {tz}</p></div>',
        unsafe_allow_html=True,
    )

    render_schedule_table(cal)

    dates = _week_dates(week_start)
    by_day = _posts_by_day(cal)

    st.markdown("#### Weekly calendar")
    cols = st.columns(7)
    for i, full_day in enumerate(FULL_DAYS):
        post = by_day.get(normalize_day_key(full_day))
        date_str = dates[i].strftime("%b %d")
        with cols[i]:
            if post:
                slot = slot_for_format(post.get("format", ""))
                has_pr = _has_prompts(week_start, post)
                card_class = "cal-day-card has-prompts" if has_pr else "cal-day-card"
                status = (
                    '<span class="cal-status-done">✓ Prompts ready</span>'
                    if has_pr else '<span class="cal-status-pending">○ Prompts pending</span>'
                )
                hook = (post.get("hook") or "")[:100]
                if len(post.get("hook") or "") > 100:
                    hook += "…"
                engage = post.get("engagement_score", "")
                engage_badge = (
                    f'<span class="cal-engage-badge">{engage}</span>' if engage else ""
                )
                st.markdown(
                    f'<div class="{card_class}">'
                    f'<div class="cal-day-header">'
                    f'<span class="cal-day-name">{DAY_LABELS[i]}</span>'
                    f'<span class="cal-day-date">{date_str}</span></div>'
                    f'<span class="cal-time-badge">🕐 {post.get("post_time", "TBD")} {post.get("timezone", "")}</span>'
                    f'{engage_badge}'
                    f'<span class="cal-format-badge">{slot.get("icon", "")} '
                    f'{FORMAT_LABELS.get(post.get("format", ""), "")}</span>'
                    f'<div class="cal-post-title">{post.get("title", "Untitled")}</div>'
                    f'<div class="cal-hook">{hook}</div>'
                    f'<div class="cal-meta">{status}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="cal-empty-day">{DAY_LABELS[i]}<br>{date_str}<br>'
                    f'<em>No post</em></div>',
                    unsafe_allow_html=True,
                )

    st.markdown("---")
    st.markdown("#### Post details")
    sorted_posts = sort_posts_chronologically(cal.get("posts", []))
    for i, post in enumerate(sorted_posts):
        render_post_card(post, i, week_start, use_expander=use_post_expanders)


def _has_prompts(week_start: str, post: dict) -> bool:
    key = prompt_storage_key(week_start, post.get("day", ""), post.get("format", ""))
    return key in st.session_state.content_prompts


def render_json_block(data: dict, label: str = "Output"):
    st.markdown(f'<div class="badge-blue">{label}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="output-card">{json.dumps(data, indent=2)}</div>', unsafe_allow_html=True)
    st.download_button(
        f"⬇ Download {label} (JSON)",
        json.dumps(data, indent=2),
        file_name=f"{label.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
        mime="application/json",
        key=f"dl_{label}_{hash(json.dumps(data, sort_keys=True)) % 10**8}",
    )


def _render_post_card_body(post: dict, week_start: str, fmt: str):
    schedule = format_schedule_label(post)
    if schedule:
        st.markdown(f"**📆 Schedule:** {schedule}")
    if post.get("timing_rationale"):
        st.markdown(f"**⏱ Why this slot:** {post['timing_rationale']}")
    st.markdown(f"**Hook:** {post.get('hook', '')}")
    st.markdown(f"**Angle:** {post.get('angle', '')}")
    st.markdown(f"**BAESS tie-in:** {post.get('baess_tie_in', '')}")
    if post.get("competitor_or_trend_angle"):
        st.markdown(f"**Competitive / trend:** {post['competitor_or_trend_angle']}")
    if post.get("caption_outline"):
        st.markdown("**Caption outline:**")
        outline = post["caption_outline"]
        if isinstance(outline, list):
            for b in outline:
                st.markdown(f"- {b}")
        else:
            st.markdown(outline)
    if post.get("hashtags"):
        tags = post["hashtags"]
        st.caption(" ".join(f"#{t.lstrip('#')}" for t in tags))
    if week_start and _has_prompts(week_start, post):
        key = prompt_storage_key(week_start, post.get("day", ""), post.get("format", ""))
        show_key = f"show_pr_{week_start}_{post.get('day', '')}_{fmt}".replace(" ", "_")
        if st.checkbox("Show saved prompts", key=show_key):
            render_production_prompts(st.session_state.content_prompts[key], fmt)


def render_post_card(post: dict, idx: int, week_start: str = "", use_expander: bool = True):
    fmt = post.get("format", "")
    slot = slot_for_format(fmt)
    icon = slot.get("icon", "📌")
    pr_tag = " ✅" if week_start and _has_prompts(week_start, post) else ""
    time_lbl = post.get("post_time", "")
    title = (
        f"{icon} {post.get('day', '')} {time_lbl} — {FORMAT_LABELS.get(fmt, fmt)}: "
        f"{post.get('title', 'Untitled')}{pr_tag}"
    )
    if use_expander:
        with st.expander(title, expanded=False):
            _render_post_card_body(post, week_start, fmt)
    else:
        st.markdown(f"**{title}**")
        _render_post_card_body(post, week_start, fmt)
        st.markdown("")


def render_production_prompts(data: dict, fmt: str):
    if fmt == "static":
        st.markdown("**LinkedIn caption**")
        st.markdown(data.get("linkedin_caption", ""))
        st.markdown("**Image generation prompt**")
        st.code(data.get("image_gen_prompt", ""))
        if data.get("text_overlay"):
            st.markdown(f"**Text overlay:** {data['text_overlay']}")
        if data.get("negative_prompt"):
            st.caption(f"Negative prompt: {data['negative_prompt']}")
    elif fmt == "carousel":
        st.markdown("**LinkedIn caption**")
        st.markdown(data.get("linkedin_caption", ""))
        for slide in data.get("slides", []):
            st.markdown(f"---\n**Slide {slide.get('slide_num', '?')}:** {slide.get('headline', '')}")
            st.markdown(slide.get("body", ""))
            st.code(slide.get("image_gen_prompt", ""), language=None)
    elif fmt == "infographic":
        st.markdown("**LinkedIn caption**")
        st.markdown(data.get("linkedin_caption", ""))
        st.markdown(f"**Title:** {data.get('title', '')}")
        for sec in data.get("sections", []):
            st.markdown(f"**{sec.get('section_title', '')}**")
            for dp in sec.get("data_points", []):
                st.markdown(f"- {dp}")
        st.markdown("**Infographic image prompt**")
        st.code(data.get("infographic_image_prompt", ""))
    elif fmt == "reel":
        st.markdown("**LinkedIn caption**")
        st.markdown(data.get("linkedin_caption", ""))
        st.markdown(f"**Hook (first 3 sec):** {data.get('hook_first_3_sec', '')}")
        st.markdown("**Full voiceover**")
        st.code(data.get("full_voiceover_script", ""))
        for clip in data.get("clips", []):
            st.markdown(f"---\n### Clip {clip.get('clip_num', '?')} ({clip.get('duration_sec', 10)}s)")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Text overlay:** {clip.get('text_overlay', '')}")
                st.markdown(f"**Voiceover:** {clip.get('voiceover', '')}")
            with c2:
                st.markdown(f"**Scene:** {clip.get('scene_description', '')}")
            st.markdown("**Video gen prompt**")
            st.code(clip.get("video_gen_prompt", ""))


# ── Audience reference ────────────────────────────────────────────────────────
with st.expander("🎯 Executive audience & Pixar character spec"):
    st.markdown(EXECUTIVE_AUDIENCE)
    st.markdown("---")
    st.markdown(PIXAR_CHARACTER)

tab_cal, tab_prompts, tab_saved = st.tabs([
    "📅 Calendar View", "🎨 Generate Prompts", "💾 All Saved Weeks"
])

# ── Shared week selector ──────────────────────────────────────────────────────
week_options = {ws.strftime("Week of %b %d, %Y"): ws for ws in week_start_options()}
# Include weeks from DB not in default options
for ws_str in sorted(st.session_state.content_calendars.keys(), reverse=True):
    try:
        ws_dt = datetime.strptime(ws_str, "%Y-%m-%d")
        label = ws_dt.strftime("Week of %b %d, %Y")
        if label not in week_options:
            week_options[label] = ws_dt
    except ValueError:
        pass

sorted_labels = sorted(week_options.keys(), key=lambda l: week_options[l], reverse=True)

# ── Tab 1: Calendar view ──────────────────────────────────────────────────────
with tab_cal:
    c1, c2 = st.columns([2, 1])
    with c1:
        week_label = st.selectbox("Select week", sorted_labels, key="cal_week_select")
        week_start_dt = week_options[week_label]
        week_start_str = week_start_dt.strftime("%Y-%m-%d")
        st.session_state["active_calendar_key"] = week_start_str
    with c2:
        if db_available():
            st.success("🟢 Neon DB connected")
        else:
            st.warning("🟡 Session-only mode")

    cal = st.session_state.content_calendars.get(week_start_str)

    if cal:
        render_calendar_grid(week_start_str, cal)
        st.markdown("---")
        if st.button("🔄 Reload this week from database", use_container_width=True):
                if db_available():
                    sync_from_db(st.session_state)
                st.rerun()
    else:
        st.markdown(
            f'<div class="cal-empty-day" style="min-height:80px;margin:1rem 0;">'
            f'No calendar for <strong>{week_label}</strong> yet — generate below.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.subheader("Generate or regenerate week")
    tz_choice = st.selectbox(
        "Audience timezone (for scheduling)",
        [
            "IST (Asia/Kolkata, UTC+5:30)",
            "GST (Asia/Dubai, UTC+4)",
            "UTC",
            "CET (Europe/Berlin, UTC+1)",
            "EST (America/New_York, UTC-5)",
            "SGT (Asia/Singapore, UTC+8)",
        ],
        key="audience_tz",
        help="AI assigns precise post times in this timezone with UTC equivalents.",
    )
    strategic_focus = st.text_input(
        "Strategic focus (optional)",
        placeholder="e.g. AI BOQ vs manual takeoffs, BESS attach rates in C&I",
        key="cal_strategic_focus",
    )
    cal_custom = st.text_area(
        "Custom instructions (optional)",
        placeholder="e.g. Emphasise Founding Member pricing. Avoid mentioning PVsyst by name.",
        height=72,
        key="cal_custom",
    )

    col_gen, col_del = st.columns([3, 1])
    with col_gen:
        do_generate = st.button("⚡ Generate Weekly Calendar", type="primary", use_container_width=True)
    with col_del:
        if cal and st.button("🗑 Delete week", use_container_width=True):
            if db_available():
                try:
                    delete_calendar(week_start_str)
                except Exception as e:
                    st.error(str(e))
            st.session_state.content_calendars.pop(week_start_str, None)
            keys_to_drop = [k for k in st.session_state.content_prompts if k.startswith(week_start_str + "|")]
            for k in keys_to_drop:
                st.session_state.content_prompts.pop(k, None)
            st.session_state.content_weeks = len(st.session_state.content_calendars)
            st.rerun()

    if do_generate:
        avoid_block = avoid_repetition_block(
            calendars=st.session_state.content_calendars,
            prompts=st.session_state.content_prompts,
            exclude_week=week_start_str,
            context="LinkedIn weekly content calendar",
        )
        with st.spinner("Planning executive-grade content calendar…"):
            raw = call_ai(
                CALENDAR_SYSTEM,
                build_calendar_user_prompt(
                    week_start_dt,
                    strategic_focus,
                    topics_focus_block(),
                    cal_custom,
                    avoid_block=avoid_block,
                    audience_timezone=tz_choice,
                ),
                max_tokens=2500,
            )
        if raw:
            try:
                calendar = _parse_json(raw)
                calendar["week_start"] = week_start_str
                calendar["audience_timezone"] = tz_choice
                calendar["posts"] = sort_posts_chronologically(calendar.get("posts", []))
                st.session_state.content_calendars[week_start_str] = calendar
                st.session_state["active_calendar_key"] = week_start_str
                st.session_state.content_weeks = len(st.session_state.content_calendars)
                if db_available():
                    try:
                        save_calendar(week_start_str, calendar, strategic_focus)
                    except Exception as e:
                        st.error(f"Saved locally but DB write failed: {e}")
                st.success(f"Calendar ready — theme: **{calendar.get('week_theme', '')}**")
                st.rerun()
            except json.JSONDecodeError:
                st.error("Could not parse calendar JSON. Raw output below.")
                st.code(raw)

# ── Tab 2: Production prompts ─────────────────────────────────────────────────
with tab_prompts:
    st.subheader("Generate creative production prompts")
    st.caption("Prompts are saved to Neon automatically when DATABASE_URL is set.")

    active_key = st.session_state.get("active_calendar_key")
    calendars = st.session_state.content_calendars

    if not calendars:
        st.warning("Generate a weekly calendar first, or use manual mode below.")
        manual_mode = True
    else:
        manual_mode = st.checkbox("Manual mode (no calendar)", value=False)

    selected_post = None
    fmt = "static"
    cal_choice = active_key

    if not manual_mode and calendars:
        cal_choice = st.selectbox(
            "Select week",
            sorted(calendars.keys(), reverse=True),
            index=0 if active_key not in calendars else sorted(calendars.keys(), reverse=True).index(active_key),
        )
        cal = calendars[cal_choice]
        posts = cal.get("posts", [])
        if posts:
            post_labels = [
                f"{p.get('day', '?')} — {FORMAT_LABELS.get(p.get('format', ''), p.get('format', ''))}: "
                f"{p.get('title', '')}"
                + (" ✅" if _has_prompts(cal_choice, p) else "")
                for p in posts
            ]
            post_idx = st.selectbox("Select post", range(len(posts)), format_func=lambda i: post_labels[i])
            selected_post = posts[post_idx]
            fmt = selected_post.get("format", WEEKLY_SLOTS[min(post_idx, len(WEEKLY_SLOTS) - 1)]["format"])
        else:
            st.error("Calendar has no posts.")
    else:
        fmt = st.selectbox(
            "Content format",
            [s["format"] for s in WEEKLY_SLOTS],
            format_func=lambda x: FORMAT_LABELS.get(x, x),
        )
        manual_title = st.text_input("Post title / topic")
        manual_hook = st.text_area("Hook & angle", height=100)
        if manual_title:
            selected_post = {
                "format": fmt,
                "title": manual_title,
                "hook": manual_hook,
                "angle": manual_hook,
                "day": "Manual",
                "baess_tie_in": "From sidebar topics + documentation",
            }
            cal_choice = "manual"

    prompt_custom = st.text_area(
        "Custom instructions for prompts (optional)",
        placeholder="e.g. Carousel slide 1 must show PV AI Designer Pro UI. Reel clip 2: BESS containers.",
        height=72,
        key="prompt_custom",
    )

    if st.button("⚡ Generate Production Prompts", type="primary", use_container_width=True):
        if not selected_post:
            st.warning("Select or define a post first.")
        else:
            system = PROMPT_SYSTEMS.get(fmt, PROMPT_SYSTEMS["static"])
            ws = cal_choice if cal_choice != "manual" else "manual"
            avoid_block = avoid_repetition_block(
                calendars=st.session_state.content_calendars,
                prompts=st.session_state.content_prompts,
                exclude_week=ws if ws != "manual" else None,
                context="LinkedIn production prompts",
            )
            with st.spinner(f"Generating {FORMAT_LABELS.get(fmt, fmt)} prompts…"):
                raw = call_ai(
                    system,
                    build_prompt_user_prompt(selected_post, fmt, prompt_custom, avoid_block=avoid_block),
                    max_tokens=3500,
                )
            if raw:
                try:
                    prompts = _parse_json(raw)
                    day = selected_post.get("day", "Manual")
                    pfmt = selected_post.get("format", fmt)
                    save_key = prompt_storage_key(ws, day, pfmt)
                    st.session_state.content_prompts[save_key] = prompts
                    st.session_state["last_prompts"] = prompts
                    st.session_state["last_prompt_fmt"] = fmt
                    if db_available() and ws != "manual":
                        try:
                            save_prompts(ws, day, pfmt, selected_post.get("title", ""), prompts)
                        except Exception as e:
                            st.error(f"Prompts generated but DB save failed: {e}")
                    st.success("Production prompts ready and saved.")
                    st.rerun()
                except json.JSONDecodeError:
                    st.error("Could not parse prompts JSON.")
                    st.code(raw)

    if st.session_state.get("last_prompts"):
        st.markdown("---")
        render_production_prompts(
            st.session_state["last_prompts"],
            st.session_state.get("last_prompt_fmt", "static"),
        )
        render_json_block(st.session_state["last_prompts"], "Production Prompts")

# ── Tab 3: All saved weeks ────────────────────────────────────────────────────
with tab_saved:
    st.subheader("All saved weeks")
    if db_available():
        if st.button("🔄 Sync all from Neon"):
            sync_from_db(st.session_state)
            st.rerun()

    if st.session_state.content_calendars:
        for ws in sorted(st.session_state.content_calendars.keys(), reverse=True):
            cal = st.session_state.content_calendars[ws]
            n_prompts = sum(
                1 for p in cal.get("posts", [])
                if _has_prompts(ws, p)
            )
            with st.expander(f"📅 Week of {ws} — {cal.get('week_theme', '')} ({n_prompts}/4 prompts)"):
                render_calendar_grid(ws, cal, use_post_expanders=False)
                render_json_block(cal, f"Calendar_{ws}")
    else:
        st.caption("No saved calendars yet.")

st.caption("BAESS Labs — baess.app | LinkedIn Content Calendar v1.1")
