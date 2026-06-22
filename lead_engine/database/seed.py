"""Seed country sources and default application settings."""

from __future__ import annotations

from config.settings import get_settings
from database.connection import get_session
from models.app_setting import AppSetting
from models.country_source import CountrySource
from utils.logging import get_logger
from utils.url_helpers import build_enf_directory_url

logger = get_logger(__name__)

PRELOADED_COUNTRIES = [
    ("Germany", "Germany"),
    ("France", "France"),
    ("Italy", "Italy"),
    ("Spain", "Spain"),
    ("Netherlands", "Netherlands"),
    ("United Kingdom", "United Kingdom"),
    ("United States", "United States"),
    ("United Arab Emirates", "UAE"),
    ("Saudi Arabia", "Saudi Arabia"),
    ("Oman", "Oman"),
    ("Egypt", "Egypt"),
    ("South Africa", "South Africa"),
    ("Nigeria", "Nigeria"),
    ("India", "India"),
    ("Australia", "Australia"),
    ("New Zealand", "New Zealand"),
    ("Philippines", "Philippines"),
]


def seed_countries() -> int:
    inserted = 0
    with get_session() as session:
        for country_name, country_slug in PRELOADED_COUNTRIES:
            exists = (
                session.query(CountrySource)
                .filter(CountrySource.country_slug == country_slug)
                .first()
            )
            if exists:
                continue
            session.add(
                CountrySource(
                    country_name=country_name,
                    country_slug=country_slug,
                    enf_directory_url=build_enf_directory_url(country_slug, page=1),
                    current_page=1,
                    is_active=True,
                )
            )
            inserted += 1
    logger.info("Seeded %d country sources", inserted)
    return inserted


def seed_default_settings() -> None:
    settings = get_settings()
    defaults = [
        (
            "ai_provider",
            settings.default_ai_provider,
            "Active AI provider for research (deepseek or openai)",
        ),
        (
            "crawl_delay_seconds",
            str(settings.request_delay_seconds),
            "Minimum delay between HTTP requests in seconds",
        ),
        (
            "app_version",
            "1.0.0",
            "BAESS Lead Engine version",
        ),
    ]
    with get_session() as session:
        for key, value, description in defaults:
            existing = (
                session.query(AppSetting).filter(AppSetting.key == key).first()
            )
            if existing:
                continue
            session.add(AppSetting(key=key, value=value, description=description))
