"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _PROJECT_ROOT / ".env"

def _reload_env_file() -> None:
    """Reload .env on every settings read (picks up edits without full restart)."""
    try:
        from dotenv import load_dotenv

        load_dotenv(_ENV_FILE, override=True)
    except ImportError:
        pass


_reload_env_file()


@lru_cache
def _streamlit_secrets_available() -> bool:
    """True only when a secrets.toml file exists (avoids Streamlit warnings)."""
    candidates = [
        _PROJECT_ROOT / ".streamlit" / "secrets.toml",
        Path.home() / ".streamlit" / "secrets.toml",
    ]
    return any(path.is_file() for path in candidates)


def _get_config_value(key: str, default: str = "") -> str:
    """Read from .env / environment variables, then Streamlit Cloud secrets."""
    value = os.getenv(key, "").strip()
    if value:
        return value
    if not _streamlit_secrets_available():
        return default
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    return default


@dataclass(frozen=True)
class Settings:
    """Central configuration for BAESS Lead Engine."""

    database_url: str
    log_level: str = "INFO"
    request_timeout: int = 30
    request_delay_seconds: float = 2.5
    enrichment_delay_min: float = 20.0
    enrichment_delay_max: float = 30.0
    enrichment_batch_size: int = 30
    enrichment_cooldown_seconds: int = 300
    research_delay_min: float = 2.0
    research_delay_max: float = 4.0
    research_batch_size: int = 10
    research_cooldown_seconds: int = 300
    research_max_pages: int = 5
    website_delay_min: float = 1.0
    website_delay_max: float = 2.0
    research_request_timeout: int = 12
    deepseek_model: str = "deepseek-chat"
    openai_model: str = "gpt-4o-mini"
    proxy_enabled: bool = False
    proxy_use_for_enf: bool = False
    proxy_list: str = ""
    proxy_rotate_every: int = 2
    proxy_max_failures: int = 3
    max_retries: int = 3
    retry_backoff_factor: float = 1.5
    user_agent: str = (
        "BAESS-Lead-Engine/1.0 (+https://baess.com; respectful-crawler)"
    )
    enf_base_url: str = "https://www.enfsolar.com"
    default_ai_provider: str = "openai"
    openai_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    companies_per_page: int = 25
    http_impersonate: str = "chrome120"
    zeptomail_send_token: Optional[str] = None
    zeptomail_from_address: Optional[str] = None
    zeptomail_from_name: str = "BAESS Labs"
    zeptomail_reply_to: Optional[str] = None
    daily_send_limit: int = 100
    follow_up_days: int = 7
    max_follow_up_sequence: int = 3
    zoho_client_id: Optional[str] = None
    zoho_client_secret: Optional[str] = None
    zoho_refresh_token: Optional[str] = None
    zoho_account_id: Optional[str] = None
    zoho_mail_api_base: str = "https://mail.zoho.com/api"
    zoho_accounts_base: str = "https://accounts.zoho.com"

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = _get_config_value("DATABASE_URL")
        if not database_url:
            raise ValueError(
                "DATABASE_URL is required. Set it in .env locally or in "
                "Streamlit Cloud secrets with your Neon PostgreSQL connection string."
            )
        return cls(
            database_url=database_url,
            log_level=_get_config_value("LOG_LEVEL", "INFO").upper(),
            request_timeout=int(_get_config_value("REQUEST_TIMEOUT", "30")),
            request_delay_seconds=float(
                _get_config_value("REQUEST_DELAY_SECONDS", "2.5")
            ),
            enrichment_delay_min=float(
                _get_config_value("ENRICHMENT_DELAY_MIN", "20")
            ),
            enrichment_delay_max=float(
                _get_config_value("ENRICHMENT_DELAY_MAX", "30")
            ),
            enrichment_batch_size=int(
                _get_config_value("ENRICHMENT_BATCH_SIZE", "30")
            ),
            enrichment_cooldown_seconds=int(
                _get_config_value("ENRICHMENT_COOLDOWN_SECONDS", "300")
            ),
            research_delay_min=float(_get_config_value("RESEARCH_DELAY_MIN", "2")),
            research_delay_max=float(_get_config_value("RESEARCH_DELAY_MAX", "4")),
            research_batch_size=int(_get_config_value("RESEARCH_BATCH_SIZE", "10")),
            research_cooldown_seconds=int(
                _get_config_value("RESEARCH_COOLDOWN_SECONDS", "300")
            ),
            research_max_pages=int(_get_config_value("RESEARCH_MAX_PAGES", "5")),
            website_delay_min=float(_get_config_value("WEBSITE_DELAY_MIN", "1")),
            website_delay_max=float(_get_config_value("WEBSITE_DELAY_MAX", "2")),
            research_request_timeout=int(
                _get_config_value("RESEARCH_REQUEST_TIMEOUT", "12")
            ),
            deepseek_model=_get_config_value("DEEPSEEK_MODEL", "deepseek-chat"),
            openai_model=_get_config_value("OPENAI_MODEL", "gpt-4o-mini"),
            proxy_enabled=_get_config_value("PROXY_ENABLED", "false").lower()
            in ("1", "true", "yes"),
            proxy_use_for_enf=_get_config_value("PROXY_USE_FOR_ENF", "false")
            .lower()
            in ("1", "true", "yes"),
            proxy_list=_get_config_value("PROXY_LIST", ""),
            proxy_rotate_every=int(_get_config_value("PROXY_ROTATE_EVERY", "2")),
            proxy_max_failures=int(_get_config_value("PROXY_MAX_FAILURES", "3")),
            max_retries=int(_get_config_value("MAX_RETRIES", "3")),
            retry_backoff_factor=float(
                _get_config_value("RETRY_BACKOFF_FACTOR", "1.5")
            ),
            user_agent=_get_config_value("USER_AGENT") or cls.user_agent,
            enf_base_url=_get_config_value(
                "ENF_BASE_URL", "https://www.enfsolar.com"
            ).rstrip("/"),
            default_ai_provider=_get_config_value(
                "DEFAULT_AI_PROVIDER", "openai"
            ).lower(),
            openai_api_key=_get_config_value("OPENAI_API_KEY") or None,
            deepseek_api_key=_get_config_value("DEEPSEEK_API_KEY") or None,
            companies_per_page=int(_get_config_value("COMPANIES_PER_PAGE", "25")),
            http_impersonate=_get_config_value("HTTP_IMPERSONATE", "chrome120"),
            zeptomail_send_token=_get_config_value("ZEPTOMAIL_SEND_TOKEN") or None,
            zeptomail_from_address=_get_config_value("ZEPTOMAIL_FROM_ADDRESS") or None,
            zeptomail_from_name=_get_config_value(
                "ZEPTOMAIL_FROM_NAME", "BAESS Labs"
            ),
            zeptomail_reply_to=_get_config_value("ZEPTOMAIL_REPLY_TO") or None,
            daily_send_limit=int(_get_config_value("DAILY_SEND_LIMIT", "100")),
            follow_up_days=int(_get_config_value("FOLLOW_UP_DAYS", "7")),
            max_follow_up_sequence=int(
                _get_config_value("MAX_FOLLOW_UP_SEQUENCE", "3")
            ),
            zoho_client_id=_get_config_value("ZOHO_CLIENT_ID") or None,
            zoho_client_secret=_get_config_value("ZOHO_CLIENT_SECRET") or None,
            zoho_refresh_token=_get_config_value("ZOHO_REFRESH_TOKEN") or None,
            zoho_account_id=_get_config_value("ZOHO_ACCOUNT_ID") or None,
            zoho_mail_api_base=_get_config_value(
                "ZOHO_MAIL_API_BASE", "https://mail.zoho.com/api"
            ).rstrip("/"),
            zoho_accounts_base=_get_config_value(
                "ZOHO_ACCOUNTS_BASE", "https://accounts.zoho.com"
            ).rstrip("/"),
        )


def get_settings() -> Settings:
    """Load settings from environment (not cached — safe for Streamlit hot-reload)."""
    _reload_env_file()
    return Settings.from_env()
