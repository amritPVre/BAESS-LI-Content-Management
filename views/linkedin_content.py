"""LinkedIn content calendar + creative prompt generation for BAESS Labs page."""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from baess_context import BAESS_PLATFORM_CONTEXT, get_outreach_topics, topics_focus_block

ROOT = Path(__file__).resolve().parent.parent
DOCS_PATH = ROOT / "BAESS_PLATFORM_DOCUMENTATION.md"

WEEKLY_SLOTS = [
    {
        "format": "static",
        "label": "Static Image Post",
        "icon": "🖼️",
        "optimal_window": "Tuesday 10:00–11:00 AM",
        "why": "Highest B2B feed engagement — executives scan LinkedIn before morning meetings; static visuals stop the scroll.",
    },
    {
        "format": "carousel",
        "label": "Carousel Post",
        "icon": "📑",
        "optimal_window": "Wednesday 12:00–1:00 PM",
        "why": "Mid-week lunch-scroll peak; swipeable carousels get 2–3× dwell time vs single images in B2B feeds.",
    },
    {
        "format": "infographic",
        "label": "Infographic Post",
        "icon": "📊",
        "optimal_window": "Thursday 9:00–10:00 AM",
        "why": "Senior professionals engage with data-rich saves/shares early Thursday before week-end wind-down.",
    },
    {
        "format": "reel",
        "label": "Short Video / Reel",
        "icon": "🎬",
        "optimal_window": "Thursday 5:00–6:00 PM",
        "why": "Mobile evening consumption peak; LinkedIn autoplay video/Reels spike Tue/Thu 5–7 PM for professional audiences.",
    },
]

LINKEDIN_TIMING_RESEARCH = """
LINKEDIN B2B ENGAGEMENT RESEARCH (executive / decision-maker audiences, 2024–2025 aggregates):
Sources align across Sprout Social, Hootsuite, Buffer B2B studies, and LinkedIn algorithm behaviour reports.

TOP 4 POSTING DAYS (ranked — use these, NOT generic Mon→Thu):
1. TUESDAY — #1 overall B2B engagement day; feed competition is high but reach is highest for quality posts.
2. WEDNESDAY — #2; mid-week intent peak; best for carousels and thought-leadership saves.
3. THURSDAY — #3; strong AM for infographics/data; strong PM (5–7 PM) for video/Reels autoplay.
4. MONDAY — #4 (optional 5th slot avoided); use ONLY if a format cannot fit Tue–Thu; prefer 8:00–9:00 AM.

AVOID posting for executive reach: Friday after 2 PM, Saturday, Sunday (engagement drops 60–80% vs Tue).

TOP TIME WINDOWS (local audience timezone):
- Tue 10:00–11:00 AM — peak B2B morning scan (best: static image, bold hook)
- Wed 12:00–1:00 PM — lunch mobile scroll (best: carousel)
- Thu 9:00–10:00 AM — data/infographic saves before meetings stack up
- Thu 5:00–6:00 PM — video/Reels autoplay + evening mobile (best: reel, 40 sec)

Format-to-slot mapping (MANDATORY):
- static → Tuesday morning window
- carousel → Wednesday midday window
- infographic → Thursday morning window
- reel → Thursday evening window

Rules for timing output:
- Assign exact post_time in HH:MM (24h or 12h with AM/PM) within the window — pick a precise minute (e.g. 10:30 AM), not a range.
- Compute post_date as the actual calendar date within the planning week (week_start = Monday of that week).
- Include timezone (e.g. IST Asia/Kolkata), time_utc equivalent, and timing_rationale (1–2 sentences: why this slot drives reach for this format + audience).
- engagement_score: estimate High / Very High based on day+time combo for B2B executives.
"""

EXECUTIVE_AUDIENCE = """
Primary audience (veteran solar industry leaders — NOT beginners):
Founders, owners, CXOs, project heads, engineering heads, directors, VPs, presidents,
senior managers, general managers, project managers, senior consultants at EPCs,
developers, BESS integrators, and large installers.

Content bar: executive-grade thought leadership. NO basic solar Q&A, "did you know" facts,
or entry-level explainers. Assume they know string sizing, PR, LCOE, and procurement.

What works for this audience:
- Workflow economics: cost of fragmented tool stacks, bid-cycle compression, BOQ labour hours
- Competitive intelligence: honest positioning vs PVsyst, Helioscope, Aurora, PVcase, Rated Power
- Feature depth: AI BOQ, layout+SLD automation, PV+BESS unified stack, 3D designer, component DB scale
- Industry trends: C&I margin pressure, BESS attach rates, AI in takeoffs, web vs desktop toolchain shifts
- Price/accessibility narrative without sounding cheap — value per deliverable hour
"""

PIXAR_CHARACTER = """
Visual brand character (use in ALL image/video prompts for consistency):
Pixar-style 3D cartoon male character, mid-30s, friendly professional solar engineer,
warm skin tone, short dark hair, smart-casual attire (navy polo or light jacket),
expressive but credible — NOT childish. Same character in every frame/slide.
Style: Pixar/DreamWorks quality 3D render, soft studio lighting, clean backgrounds,
solar engineering context (screens, rooftops, BESS containers, dashboards) when relevant.
"""

CALENDAR_SYSTEM = f"""You are a LinkedIn content strategist for BAESS Labs (baess.app).
You plan a 4-post weekly calendar for the company LinkedIn page.

{BAESS_PLATFORM_CONTEXT}

{EXECUTIVE_AUDIENCE}

{LINKEDIN_TIMING_RESEARCH}

Posting cadence: exactly 4 posts per week on the TOP engagement days/times above — NOT sequential Mon–Thu by default.
Each post must land on its format-specific optimal day and precise time window.

Rules:
- Each post must have a distinct angle — no repetition across the week OR across prior weeks (see anti-repetition block in user prompt if provided).
- Tie at least 2 posts to specific BAESS products/features from documentation.
- At least 1 post should include competitive positioning (honest, not trash-talk).
- At least 1 post should reference an industry trend relevant to EPC/developer leadership.
- Hooks must stop a VP mid-scroll — sharp, specific, zero fluff.
- Timing is critical: use research-backed days/times; never place all 4 posts on Mon–Thu morning without variation.
- Output ONLY valid JSON, no markdown fences. Schema:
{{
  "week_theme": "one-line strategic theme for the week",
  "week_start": "YYYY-MM-DD",
  "audience_timezone": "e.g. IST (Asia/Kolkata, UTC+5:30)",
  "posts": [
    {{
      "format": "static|carousel|infographic|reel",
      "day": "Tuesday",
      "post_date": "YYYY-MM-DD",
      "post_time": "10:30 AM",
      "timezone": "IST",
      "time_utc": "05:00 UTC",
      "engagement_score": "Very High",
      "timing_rationale": "Why this exact slot maximizes reach for this format and executive audience",
      "title": "internal working title",
      "hook": "scroll-stopping first line for caption",
      "angle": "why this matters to executives",
      "baess_tie_in": "specific product/feature",
      "competitor_or_trend_angle": "optional competitive or trend hook",
      "caption_outline": ["bullet 1", "bullet 2"],
      "hashtags": ["5-8 relevant hashtags without # symbol"]
    }}
  ]
}}
Include exactly 4 posts: static (Tue AM), carousel (Wed midday), infographic (Thu AM), reel (Thu PM).
Sort posts chronologically by post_date and post_time in the JSON array."""

PROMPT_SYSTEM_STATIC = f"""You are a creative director generating production prompts for BAESS Labs LinkedIn.

{BAESS_PLATFORM_CONTEXT}
{EXECUTIVE_AUDIENCE}
{PIXAR_CHARACTER}

Generate a complete static image post package for an image-generation app (Midjourney, DALL-E, Ideogram, etc.).
Output ONLY valid JSON, no markdown fences. Schema:
{{
  "format": "static",
  "linkedin_caption": "full ready-to-post caption, 150-220 words, executive tone",
  "image_gen_prompt": "detailed prompt for hero image, include Pixar character spec",
  "negative_prompt": "what to avoid in image gen",
  "text_overlay": "compact headline + subline for designer to place on image",
  "alt_text": "accessibility alt text",
  "design_notes": "layout, colours (#0f172a navy, #7dd3fc cyan brand), composition"
}}"""

PROMPT_SYSTEM_CAROUSEL = f"""You are a creative director for BAESS Labs LinkedIn carousel posts.

{BAESS_PLATFORM_CONTEXT}
{EXECUTIVE_AUDIENCE}
{PIXAR_CHARACTER}

Generate a 5-7 slide carousel with per-slide image prompts.
Output ONLY valid JSON, no markdown fences. Schema:
{{
  "format": "carousel",
  "linkedin_caption": "full caption with 'Swipe →' hook, 120-180 words",
  "slides": [
    {{
      "slide_num": 1,
      "headline": "on-slide text, max 8 words",
      "body": "on-slide supporting text, max 20 words",
      "image_gen_prompt": "detailed prompt including Pixar character when relevant",
      "design_notes": "visual direction"
    }}
  ],
  "cover_slide_prompt": "hero slide image prompt",
  "cta_slide": "final slide text + visual direction"
}}"""

PROMPT_SYSTEM_INFOGRAPHIC = f"""You are a creative director for BAESS Labs LinkedIn infographic posts.

{BAESS_PLATFORM_CONTEXT}
{EXECUTIVE_AUDIENCE}
{PIXAR_CHARACTER}

Generate an executive-grade infographic brief (not beginner stats).
Output ONLY valid JSON, no markdown fences. Schema:
{{
  "format": "infographic",
  "linkedin_caption": "full caption, 130-200 words",
  "title": "infographic headline",
  "sections": [
    {{
      "section_title": "string",
      "data_points": ["2-4 sharp bullet stats or comparisons — must be defensible/general industry framed"],
      "visual_direction": "how to visualize this section"
    }}
  ],
  "infographic_image_prompt": "single tall infographic image gen prompt, include Pixar character as guide/host if fitting",
  "colour_palette": "brand-aligned hex colours",
  "footer_cta": "compact CTA line"
}}"""

PROMPT_SYSTEM_REEL = f"""You are a creative director for BAESS Labs LinkedIn short-form video (40 sec max).

{BAESS_PLATFORM_CONTEXT}
{EXECUTIVE_AUDIENCE}
{PIXAR_CHARACTER}

Structure: exactly 4 clips × 10 seconds each = 40 seconds total.
Each clip needs: visual prompt (for video gen e.g. Runway, Pika, Kling), voiceover script (compact, executive tone),
on-screen text overlay (max 6 words per clip), and transition note.

Output ONLY valid JSON, no markdown fences. Schema:
{{
  "format": "reel",
  "linkedin_caption": "full caption for reel post, 100-160 words",
  "total_duration_sec": 40,
  "character_ref": "repeat Pixar character description for consistency across clips",
  "clips": [
    {{
      "clip_num": 1,
      "duration_sec": 10,
      "scene_description": "what happens visually",
      "video_gen_prompt": "detailed prompt for AI video tool, Pixar 3D style",
      "voiceover": "exact VO script, ~25-30 words max for 10 sec",
      "text_overlay": "bold on-screen text, max 6 words",
      "audio_note": "music/SFX suggestion"
    }}
  ],
  "full_voiceover_script": "all clips concatenated",
  "hook_first_3_sec": "pattern interrupt for LinkedIn autoplay",
  "end_card": "final frame CTA visual + text"
}}"""


def load_platform_docs(max_chars: int = 12000) -> str:
    try:
        text = DOCS_PATH.read_text(encoding="utf-8")
        return text[:max_chars] if len(text) > max_chars else text
    except OSError:
        return BAESS_PLATFORM_CONTEXT


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def week_start_options() -> list[datetime]:
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    return [datetime.combine(monday + timedelta(weeks=i), datetime.min.time()) for i in range(4)]


def build_calendar_user_prompt(
    week_start: datetime,
    focus: str,
    topics_block: str,
    custom: str,
    avoid_block: str = "",
    audience_timezone: str = "IST (Asia/Kolkata, UTC+5:30)",
) -> str:
    parts = [
        f"Planning week starting: {week_start.strftime('%Y-%m-%d')} (Monday).",
        f"Primary audience timezone for scheduling: {audience_timezone}.",
        f"Documentation excerpt:\n{load_platform_docs(8000)}",
        topics_block,
        LINKEDIN_TIMING_RESEARCH,
    ]
    if avoid_block:
        parts.append(avoid_block)
    if focus.strip():
        parts.append(f"Strategic focus for this week: {focus.strip()}")
    if custom.strip():
        parts.append(f"Additional instructions: {custom.strip()}")
    parts.append("Generate the 4-post calendar JSON now.")
    return "\n\n".join(parts)


def build_prompt_user_prompt(post_brief: dict, format_type: str, custom: str, avoid_block: str = "") -> str:
    brief = json.dumps(post_brief, indent=2)
    parts = [f"Post brief from calendar:\n{brief}"]
    if avoid_block:
        parts.append(avoid_block)
    if custom.strip():
        parts.append(f"Additional instructions: {custom}")
    parts.append(f"Generate full production prompts for format: {format_type}.")
    return "\n\n".join(parts)


PROMPT_SYSTEMS = {
    "static": PROMPT_SYSTEM_STATIC,
    "carousel": PROMPT_SYSTEM_CAROUSEL,
    "infographic": PROMPT_SYSTEM_INFOGRAPHIC,
    "reel": PROMPT_SYSTEM_REEL,
}

FORMAT_LABELS = {s["format"]: s["label"] for s in WEEKLY_SLOTS}
SLOT_BY_FORMAT = {s["format"]: s for s in WEEKLY_SLOTS}

DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
FULL_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def slot_for_format(fmt: str) -> dict:
    return SLOT_BY_FORMAT.get(fmt, {})


def normalize_day_key(day: str) -> str:
    return (day or "").strip().lower()[:3]


def sort_posts_chronologically(posts: list[dict]) -> list[dict]:
    day_rank = {d: i for i, d in enumerate(DAY_ORDER)}

    def sort_key(p: dict):
        date = p.get("post_date") or ""
        day = normalize_day_key(p.get("day", ""))
        return (date, day_rank.get(day, 99), p.get("post_time", ""))

    return sorted(posts, key=sort_key)


def format_schedule_label(post: dict) -> str:
    parts = [
        post.get("day", ""),
        post.get("post_date", ""),
        post.get("post_time", ""),
        post.get("timezone", ""),
    ]
    core = " · ".join(x for x in parts if x)
    utc = post.get("time_utc", "")
    score = post.get("engagement_score", "")
    extras = " · ".join(x for x in (utc, score) if x)
    return f"{core} ({extras})" if extras else core

