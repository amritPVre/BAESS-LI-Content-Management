"""Lightweight schema migrations for existing Neon databases."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from utils.logging import get_logger

logger = get_logger(__name__)

# Legacy SQLAlchemy enums stored member NAMES; app now uses lowercase values.
_ENUM_NORMALIZERS = {
    "companies": {
        "source_type": {
            "ENF_INSTALLER": "enf_installer",
        },
        "crawl_status": {
            "PENDING": "pending",
            "DISCOVERED": "discovered",
            "ENRICHED": "enriched",
            "FAILED": "failed",
        },
        "enrichment_status": {
            "PENDING": "pending",
            "IN_PROGRESS": "in_progress",
            "COMPLETED": "completed",
            "FAILED": "failed",
        },
        "research_status": {
            "PENDING": "pending",
            "IN_PROGRESS": "in_progress",
            "COMPLETED": "completed",
            "FAILED": "failed",
            "SKIPPED": "skipped",
        },
    },
    "crawl_jobs": {
        "job_type": {
            "DISCOVERY": "discovery",
            "ENRICHMENT": "enrichment",
            "RESEARCH": "research",
        },
        "status": {
            "PENDING": "pending",
            "RUNNING": "running",
            "COMPLETED": "completed",
            "FAILED": "failed",
        },
    },
    "company_contacts": {
        "source": {
            "WEBSITE": "website",
            "AI": "ai",
            "LINKEDIN_SEARCH": "linkedin_search",
        },
    },
}


def run_migrations(engine: Engine) -> None:
    """Apply additive schema changes safe for existing deployments."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if "companies" in table_names:
        columns = {c["name"] for c in inspector.get_columns("companies")}
        with engine.begin() as conn:
            if "research_status" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE companies "
                        "ADD COLUMN research_status VARCHAR(50) "
                        "NOT NULL DEFAULT 'pending'"
                    )
                )
                logger.info("Added companies.research_status column")
            if "researched_at" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE companies "
                        "ADD COLUMN researched_at TIMESTAMPTZ NULL"
                    )
                )
                logger.info("Added companies.researched_at column")

    _normalize_enum_values(engine, table_names)
    _fix_known_directory_urls(engine, table_names)
    _ensure_outreach_messages(engine, table_names)


def _ensure_outreach_messages(engine: Engine, table_names: list[str]) -> None:
    if "outreach_messages" in table_names:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE outreach_messages (
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
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX idx_outreach_status ON outreach_messages(status)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX idx_outreach_follow_up ON outreach_messages(follow_up_due_at) "
                "WHERE status = 'sent'"
            )
        )
        logger.info("Created outreach_messages table")


def _fix_known_directory_urls(engine: Engine, table_names: list[str]) -> None:
    """Correct ENF directory URLs where the auto slug differs from ENF's real path."""
    if "country_sources" not in table_names:
        return
    fixes = [
        {
            "country_name": "United Arab Emirates",
            "country_slug": "UAE",
            "enf_directory_url": "https://www.enfsolar.com/directory/installer/UAE",
        }
    ]
    with engine.begin() as conn:
        for fix in fixes:
            result = conn.execute(
                text(
                    "UPDATE country_sources "
                    "SET country_slug = :country_slug, "
                    "enf_directory_url = :enf_directory_url "
                    "WHERE country_name = :country_name"
                ),
                fix,
            )
            if result.rowcount:
                logger.info(
                    "Fixed directory URL for %s", fix["country_name"]
                )


def _normalize_enum_values(engine: Engine, table_names: list[str]) -> None:
    """Convert legacy uppercase enum names to lowercase values in VARCHAR columns."""
    with engine.begin() as conn:
        for table, columns in _ENUM_NORMALIZERS.items():
            if table not in table_names:
                continue
            for column, mapping in columns.items():
                for legacy, normalized in mapping.items():
                    result = conn.execute(
                        text(
                            f"UPDATE {table} SET {column} = :normalized "
                            f"WHERE {column} = :legacy"
                        ),
                        {"legacy": legacy, "normalized": normalized},
                    )
                    if result.rowcount:
                        logger.info(
                            "Normalized %s.%s: %s -> %s (%d rows)",
                            table,
                            column,
                            legacy,
                            normalized,
                            result.rowcount,
                        )
