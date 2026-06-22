"""Automatic table creation and database initialization."""

from __future__ import annotations

from database.connection import get_engine, get_session, reset_engine_cache
from database.migrate import run_migrations
from database.seed import seed_countries, seed_default_settings
from models import Base
from models.company import Company, EnrichmentStatus
from utils.logging import get_logger

logger = get_logger(__name__)


def init_database(seed: bool = True) -> None:
    """Create all tables and optionally seed reference data."""
    reset_engine_cache()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    logger.info("Database tables verified/created")
    if seed:
        seed_countries()
        seed_default_settings()
        _reset_stuck_enrichments()
        logger.info("Reference data seeded")


def _reset_stuck_enrichments() -> None:
    """Reset in-progress enrichments interrupted by app restarts."""
    with get_session() as session:
        updated = (
            session.query(Company)
            .filter(Company.enrichment_status == EnrichmentStatus.IN_PROGRESS)
            .update({Company.enrichment_status: EnrichmentStatus.PENDING})
        )
        if updated:
            logger.info("Reset %d stuck in-progress enrichments", updated)
