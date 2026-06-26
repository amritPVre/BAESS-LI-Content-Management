"""Bulk email send persistence and shared daily send counts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from models.bulk_email_send import BulkEmailSend, BulkSendStatus
from models.outreach_message import OutreachMessage, OutreachStatus


def init_bulk_email_schema(engine: Engine) -> None:
    from database.migrate import run_migrations

    run_migrations(engine)


def count_sent_today_all(session: Session) -> int:
    """Campaign + bulk sends counted toward the shared daily ZeptoMail cap."""
    start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    campaign = (
        session.query(OutreachMessage)
        .filter(
            OutreachMessage.status == OutreachStatus.SENT,
            OutreachMessage.sent_at >= start,
        )
        .count()
    )
    bulk = (
        session.query(BulkEmailSend)
        .filter(
            BulkEmailSend.status == BulkSendStatus.SENT,
            BulkEmailSend.sent_at >= start,
        )
        .count()
    )
    return campaign + bulk


def create_bulk_job_rows(
    session: Session,
    *,
    job_name: str,
    subject_template: str,
    body_template: str,
    recipients: list[dict[str, str]],
    rendered: list[dict[str, str]],
) -> str:
    job_id = str(uuid4())
    for recipient, rendered_row in zip(recipients, rendered):
        session.add(
            BulkEmailSend(
                job_id=job_id,
                job_name=job_name or None,
                recipient_email=recipient["email"],
                recipient_name=recipient.get("name") or None,
                first_name=recipient.get("first_name") or None,
                subject=rendered_row["subject"],
                body_text=rendered_row["body"],
                status=BulkSendStatus.PENDING,
            )
        )
    session.flush()
    return job_id


def list_pending_for_job(session: Session, job_id: str) -> list[BulkEmailSend]:
    return (
        session.query(BulkEmailSend)
        .filter(
            BulkEmailSend.job_id == job_id,
            BulkEmailSend.status == BulkSendStatus.PENDING,
        )
        .order_by(BulkEmailSend.created_at.asc())
        .all()
    )


def mark_bulk_sent(session: Session, row: BulkEmailSend, *, zepto_reference: str) -> None:
    row.status = BulkSendStatus.SENT
    row.zepto_email_reference = zepto_reference
    row.zepto_client_reference = str(row.id)
    row.sent_at = datetime.now(timezone.utc)
    row.error_message = None


def mark_bulk_failed(session: Session, row: BulkEmailSend, error: str) -> None:
    row.status = BulkSendStatus.FAILED
    row.error_message = error[:2000]


def mark_bulk_bounced(session: Session, row: BulkEmailSend) -> None:
    row.status = BulkSendStatus.BOUNCED
    row.bounced_at = datetime.now(timezone.utc)


def mark_bulk_replied(session: Session, row: BulkEmailSend) -> None:
    row.status = BulkSendStatus.REPLIED
    row.replied_at = datetime.now(timezone.utc)


def list_sent_pending_bulk_sync(session: Session, limit: int = 500) -> list[BulkEmailSend]:
    return (
        session.query(BulkEmailSend)
        .filter(
            BulkEmailSend.status == BulkSendStatus.SENT,
            BulkEmailSend.bounced_at.is_(None),
            BulkEmailSend.replied_at.is_(None),
        )
        .order_by(BulkEmailSend.sent_at.desc())
        .limit(limit)
        .all()
    )


def bulk_stats(session: Session) -> dict[str, int]:
    rows = (
        session.query(BulkEmailSend.status, func.count(BulkEmailSend.id))
        .group_by(BulkEmailSend.status)
        .all()
    )
    stats = {s.value: 0 for s in BulkSendStatus}
    for status, count in rows:
        key = status.value if hasattr(status, "value") else str(status)
        stats[key] = count
    return stats


def recent_jobs(session: Session, limit: int = 10) -> list[dict[str, Any]]:
    rows = (
        session.query(
            BulkEmailSend.job_id,
            BulkEmailSend.job_name,
            func.count(BulkEmailSend.id),
            func.min(BulkEmailSend.created_at),
        )
        .group_by(BulkEmailSend.job_id, BulkEmailSend.job_name)
        .order_by(func.min(BulkEmailSend.created_at).desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "job_id": job_id,
            "job_name": job_name or "Bulk send",
            "total": total,
            "created_at": created,
        }
        for job_id, job_name, total, created in rows
    ]
