-- Neon schema for BAESS Outreach Suite — LinkedIn Content Calendar
-- Tables are also auto-created on first app load via content_db.init_db()

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

CREATE INDEX IF NOT EXISTS idx_content_prompts_week ON content_prompts (week_start);
