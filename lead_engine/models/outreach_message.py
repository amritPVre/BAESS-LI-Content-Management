from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, str_enum_column

if TYPE_CHECKING:
    from models.company import Company
    from models.company_contact import CompanyContact


class OutreachStatus(str, enum.Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    SENT = "sent"
    BOUNCED = "bounced"
    REPLIED = "replied"
    FAILED = "failed"
    SKIPPED = "skipped"


class OutreachMessage(Base):
    __tablename__ = "outreach_messages"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), nullable=False, index=True
    )
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("company_contacts.id"), nullable=False, index=True
    )
    sequence_num: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_message_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("outreach_messages.id"), nullable=True
    )
    subject: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[OutreachStatus] = str_enum_column(
        OutreachStatus, default=OutreachStatus.DRAFT, nullable=False, index=True
    )
    zepto_email_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    zepto_client_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    opened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    bounced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    replied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    follow_up_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    company: Mapped["Company"] = relationship()
    contact: Mapped["CompanyContact"] = relationship()
