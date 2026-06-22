from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, str_enum_column

if TYPE_CHECKING:
    from models.company import Company
    from models.country_source import CountrySource


class CrawlJobType(str, enum.Enum):
    DISCOVERY = "discovery"
    ENRICHMENT = "enrichment"
    RESEARCH = "research"


class CrawlJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[CrawlJobType] = str_enum_column(CrawlJobType, nullable=False)
    status: Mapped[CrawlJobStatus] = str_enum_column(
        CrawlJobStatus, default=CrawlJobStatus.PENDING, nullable=False, index=True
    )
    country_source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("country_sources.id"), nullable=True
    )
    company_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("companies.id"), nullable=True
    )
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    companies_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    country_source: Mapped[Optional["CountrySource"]] = relationship(
        back_populates="crawl_jobs"
    )
    company: Mapped[Optional["Company"]] = relationship(back_populates="crawl_jobs")
