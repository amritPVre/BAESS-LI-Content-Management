"""SQLAlchemy engine and session management for Neon PostgreSQL."""

from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=300,
        pool_reset_on_return="rollback",
        connect_args={"connect_timeout": 10},
    )
    logger.info("Database engine initialized")
    return engine


def reset_engine_cache() -> None:
    """Clear cached engine after .env changes or connection failures."""
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        if session.is_active:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
