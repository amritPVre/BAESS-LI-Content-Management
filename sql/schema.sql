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

-- Outreach email campaigns (requires lead_engine companies + company_contacts tables)
CREATE TABLE IF NOT EXISTS outreach_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id INTEGER NOT NULL REFERENCES companies(id),
    contact_id INTEGER NOT NULL REFERENCES company_contacts(id),
    sequence_num INTEGER NOT NULL DEFAULT 1,
    parent_message_id UUID REFERENCES outreach_messages(id),
    subject TEXT,
    body_text TEXT NOT NULL,
    body_html TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    zepto_email_reference TEXT,
    zepto_client_reference TEXT,
    sent_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,
    bounced_at TIMESTAMPTZ,
    replied_at TIMESTAMPTZ,
    follow_up_due_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (contact_id, sequence_num)
);

CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach_messages(status);

CREATE TABLE IF NOT EXISTS bulk_email_sends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL,
    job_name VARCHAR(255),
    recipient_email VARCHAR(320) NOT NULL,
    recipient_name VARCHAR(255),
    first_name VARCHAR(120),
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    zepto_email_reference TEXT,
    zepto_client_reference TEXT,
    sent_at TIMESTAMPTZ,
    bounced_at TIMESTAMPTZ,
    replied_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bulk_email_status ON bulk_email_sends(status);
CREATE INDEX IF NOT EXISTS idx_bulk_email_job ON bulk_email_sends(job_id);
CREATE INDEX IF NOT EXISTS idx_bulk_email_recipient ON bulk_email_sends(recipient_email);
