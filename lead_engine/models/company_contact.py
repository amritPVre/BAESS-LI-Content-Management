from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, str_enum_column

if TYPE_CHECKING:
    from models.company import Company


class ContactSource(str, enum.Enum):
    WEBSITE = "website"
    AI = "ai"
    LINKEDIN_SEARCH = "linkedin_search"


class CompanyContact(Base):
    __tablename__ = "company_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    full_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True, index=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    source: Mapped[ContactSource] = str_enum_column(
        ContactSource, default=ContactSource.AI, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    company: Mapped["Company"] = relationship(back_populates="contacts")
