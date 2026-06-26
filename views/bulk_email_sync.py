"""Bulk email bounce/reply sync — self-contained in views for Streamlit Cloud."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class BulkBounceSyncResult:
    checked: int = 0
    bounced: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class BulkReplySyncResult:
    checked: int = 0
    matched: int = 0
    errors: list[str] = field(default_factory=list)


def sync_bulk_bounces(rows: list) -> BulkBounceSyncResult:
    from models.bulk_email_send import BulkSendStatus
    from services.zeptomail_sync import (
        fetch_email_log_by_reference,
        is_bounce_payload,
        zeptomail_configured,
    )

    result = BulkBounceSyncResult()
    if not zeptomail_configured():
        result.errors.append("ZeptoMail not configured")
        return result

    for row in rows:
        ref = row.zepto_email_reference
        if not ref:
            continue
        result.checked += 1
        payload = fetch_email_log_by_reference(ref)
        if payload and is_bounce_payload(payload):
            result.bounced += 1
            row.status = BulkSendStatus.BOUNCED
            row.bounced_at = datetime.now(timezone.utc)
    return result


def sync_bulk_replies(rows: list) -> BulkReplySyncResult:
    try:
        from services.zoho_mail_sync import sync_replies_for_bulk_sends

        raw = sync_replies_for_bulk_sends(rows)
        return BulkReplySyncResult(
            checked=raw.checked,
            matched=raw.matched,
            errors=list(raw.errors),
        )
    except ImportError:
        result = BulkReplySyncResult()
        result.errors.append(
            "Reply sync module outdated on server — reboot app after deploying latest main."
        )
        return result
