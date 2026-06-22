from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, str_enum_column

if TYPE_CHECKING:
    from models.company_contact import CompanyContact
    from models.company_profile import CompanyProfile
    from models.country_source import CountrySource
    from models.crawl_job import CrawlJob


class SourceType(str, enum.Enum):
    ENF_INSTALLER = "enf_installer"


class CrawlStatus(str, enum.Enum):
    PENDING = "pending"
    DISCOVERED = "discovered"
    ENRICHED = "enriched"
    FAILED = "failed"


class EnrichmentStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("enf_profile_url", name="uq_companies_enf_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    enf_profile_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    website: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[SourceType] = str_enum_column(
        SourceType, default=SourceType.ENF_INSTALLER, nullable=False
    )
    crawl_status: Mapped[CrawlStatus] = str_enum_column(
        CrawlStatus, default=CrawlStatus.PENDING, nullable=False, index=True
    )
    enrichment_status: Mapped[EnrichmentStatus] = str_enum_column(
        EnrichmentStatus, default=EnrichmentStatus.PENDING, nullable=False
    )
    country_source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("country_sources.id"), nullable=True
    )
    discovered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    enriched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    research_status: Mapped[ResearchStatus] = str_enum_column(
        ResearchStatus, default=ResearchStatus.PENDING, nullable=False, index=True
    )
    researched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    country_source: Mapped[Optional["CountrySource"]] = relationship(
        back_populates="companies"
    )
    profile: Mapped[Optional["CompanyProfile"]] = relationship(
        back_populates="company", uselist=False
    )
    crawl_jobs: Mapped[list["CrawlJob"]] = relationship(back_populates="company")
    contacts: Mapped[list["CompanyContact"]] = relationship(back_populates="company")
