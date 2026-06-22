"""Outreach campaign persistence — drafts, sends, follow-ups."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, or_
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, joinedload

from models.company import Company, ResearchStatus
from models.company_contact import CompanyContact
from models.outreach_message import OutreachMessage, OutreachStatus


def init_outreach_schema(engine: Engine) -> None:
    from database.migrate import run_migrations

    run_migrations(engine)


def _active_statuses() -> tuple[OutreachStatus, ...]:
    return (
        OutreachStatus.DRAFT,
        OutreachStatus.QUEUED,
        OutreachStatus.SENT,
    )


def eligible_contacts_query(session: Session, country: str | None = None):
    """Contacts ready for first outreach email (research done, has email, no active outreach)."""
    blocked = (
        session.query(OutreachMessage.contact_id)
        .filter(OutreachMessage.status != OutreachStatus.FAILED)
        .distinct()
        .subquery()
    )
    q = (
        session.query(CompanyContact)
        .join(Company, CompanyContact.company_id == Company.id)
        .filter(
            Company.research_status == ResearchStatus.COMPLETED,
            CompanyContact.email.isnot(None),
            CompanyContact.email != "",
            ~CompanyContact.id.in_(session.query(blocked.c.contact_id)),
        )
        .options(joinedload(CompanyContact.company).joinedload(Company.profile))
    )
    if country and country != "All":
        q = q.filter(Company.country == country)
    return q.order_by(CompanyContact.updated_at.desc())


def list_eligible_contacts(
    session: Session, country: str | None = None, limit: int = 25
) -> list[dict[str, Any]]:
    rows = eligible_contacts_query(session, country).limit(limit).all()
    out = []
    for c in rows:
        co = c.company
        prof = co.profile if co else None
        out.append(
            {
                "contact_id": c.id,
                "company_id": co.id if co else None,
                "company_name": co.company_name if co else "",
                "country": co.country if co else "",
                "website": co.website if co else "",
                "email": c.email,
                "name": c.full_name or "",
                "title": c.job_title or "",
                "battery_storage": prof.battery_storage if prof else "",
                "installation_size": prof.installation_size if prof else "",
                "operating_area": prof.operating_area if prof else "",
            }
        )
    return out


def contact_has_draft(session: Session, contact_id: int, sequence_num: int = 1) -> bool:
    return (
        session.query(OutreachMessage)
        .filter(
            OutreachMessage.contact_id == contact_id,
            OutreachMessage.sequence_num == sequence_num,
            OutreachMessage.status == OutreachStatus.DRAFT,
        )
        .first()
        is not None
    )


def save_draft(
    session: Session,
    *,
    company_id: int,
    contact_id: int,
    subject: str,
    body_text: str,
    sequence_num: int = 1,
    parent_message_id: str | None = None,
) -> OutreachMessage:
    existing = (
        session.query(OutreachMessage)
        .filter(
            OutreachMessage.contact_id == contact_id,
            OutreachMessage.sequence_num == sequence_num,
            OutreachMessage.status == OutreachStatus.DRAFT,
        )
        .first()
    )
    if existing:
        existing.subject = subject
        existing.body_text = body_text
        existing.updated_at = datetime.now(timezone.utc)
        return existing
    msg = OutreachMessage(
        company_id=company_id,
        contact_id=contact_id,
        sequence_num=sequence_num,
        parent_message_id=parent_message_id,
        subject=subject,
        body_text=body_text,
        status=OutreachStatus.DRAFT,
    )
    session.add(msg)
    session.flush()
    return msg


def list_drafts(session: Session, limit: int = 50) -> list[OutreachMessage]:
    return (
        session.query(OutreachMessage)
        .filter(OutreachMessage.status == OutreachStatus.DRAFT)
        .options(
            joinedload(OutreachMessage.company),
            joinedload(OutreachMessage.contact),
        )
        .order_by(OutreachMessage.created_at.desc())
        .limit(limit)
        .all()
    )


def get_message(session: Session, message_id: str) -> OutreachMessage | None:
    return (
        session.query(OutreachMessage)
        .options(
            joinedload(OutreachMessage.company).joinedload(Company.profile),
            joinedload(OutreachMessage.contact),
        )
        .filter(OutreachMessage.id == message_id)
        .first()
    )


def count_sent_today(session: Session) -> int:
    start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (
        session.query(OutreachMessage)
        .filter(
            OutreachMessage.status == OutreachStatus.SENT,
            OutreachMessage.sent_at >= start,
        )
        .count()
    )


def mark_sent(
    session: Session,
    msg: OutreachMessage,
    *,
    zepto_reference: str,
    follow_up_days: int,
) -> None:
    now = datetime.now(timezone.utc)
    msg.status = OutreachStatus.SENT
    msg.zepto_email_reference = zepto_reference
    msg.zepto_client_reference = str(msg.id)
    msg.sent_at = now
    msg.follow_up_due_at = now + timedelta(days=follow_up_days)
    msg.error_message = None


def mark_failed(session: Session, msg: OutreachMessage, error: str) -> None:
    msg.status = OutreachStatus.FAILED
    msg.error_message = error[:2000]


def mark_bounced(session: Session, msg: OutreachMessage) -> None:
    msg.status = OutreachStatus.BOUNCED
    msg.bounced_at = datetime.now(timezone.utc)


def mark_replied(session: Session, msg: OutreachMessage) -> None:
    msg.status = OutreachStatus.REPLIED
    msg.replied_at = datetime.now(timezone.utc)


def list_sent_pending_sync(session: Session, limit: int = 100) -> list[OutreachMessage]:
    return (
        session.query(OutreachMessage)
        .filter(
            OutreachMessage.status == OutreachStatus.SENT,
            OutreachMessage.bounced_at.is_(None),
            OutreachMessage.replied_at.is_(None),
        )
        .order_by(OutreachMessage.sent_at.desc())
        .limit(limit)
        .all()
    )


def list_follow_up_due(
    session: Session, max_sequence: int = 3, limit: int = 25
) -> list[OutreachMessage]:
    now = datetime.now(timezone.utc)
    return (
        session.query(OutreachMessage)
        .filter(
            OutreachMessage.status == OutreachStatus.SENT,
            OutreachMessage.bounced_at.is_(None),
            OutreachMessage.replied_at.is_(None),
            OutreachMessage.follow_up_due_at <= now,
            OutreachMessage.sequence_num < max_sequence,
        )
        .options(
            joinedload(OutreachMessage.company).joinedload(Company.profile),
            joinedload(OutreachMessage.contact),
        )
        .order_by(OutreachMessage.follow_up_due_at.asc())
        .limit(limit)
        .all()
    )


def has_follow_up_draft(session: Session, parent_id: str) -> bool:
    return (
        session.query(OutreachMessage)
        .filter(
            OutreachMessage.parent_message_id == parent_id,
            OutreachMessage.status == OutreachStatus.DRAFT,
        )
        .first()
        is not None
    )


def campaign_stats(session: Session) -> dict[str, int]:
    rows = (
        session.query(OutreachMessage.status, func.count(OutreachMessage.id))
        .group_by(OutreachMessage.status)
        .all()
    )
    stats = {s.value: 0 for s in OutreachStatus}
    for status, count in rows:
        key = status.value if hasattr(status, "value") else str(status)
        stats[key] = count
    return stats
