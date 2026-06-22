from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.company import Company
    from models.crawl_job import CrawlJob


class CountrySource(Base):
    __tablename__ = "country_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    country_slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    enf_directory_url: Mapped[str] = mapped_column(String(500), nullable=False)
    current_page: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_crawled_at: Mapped[Optional[datetime]] = mapped_column(
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

    companies: Mapped[List["Company"]] = relationship(back_populates="country_source")
    crawl_jobs: Mapped[List["CrawlJob"]] = relationship(back_populates="country_source")
