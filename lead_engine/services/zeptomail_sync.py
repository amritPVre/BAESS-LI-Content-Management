"""Poll ZeptoMail email logs for bounces and delivery failures."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from config.settings import get_settings
from services.zeptomail_service import _auth_headers, zeptomail_configured
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DeliverySyncResult:
    checked: int = 0
    bounced: int = 0
    errors: list[str] | None = None


def fetch_email_log_by_reference(email_reference: str) -> dict | None:
    if not email_reference:
        return None
    base = get_settings().zeptomail_api_base.rstrip("/")
    url = f"{base}/v1.1/email/email-reference/{email_reference}"
    try:
        resp = requests.get(url, headers=_auth_headers(), timeout=30)
        if resp.status_code >= 400:
            return None
        return resp.json()
    except requests.RequestException:
        logger.exception("ZeptoMail log fetch failed for %s", email_reference)
        return None


def is_bounce_payload(payload: dict) -> bool:
    """Detect hard/soft bounce from ZeptoMail log response."""
    text = str(payload).lower()
    if "hardbounce" in text or "hard_bounce" in text:
        return True
    if payload.get("is_hb") or payload.get("is_mailfailure"):
        return True
    event_data = payload.get("event_data") or []
    for block in event_data if isinstance(event_data, list) else []:
        obj = (block or {}).get("object", "")
        if obj and "bounce" in str(obj).lower():
            return True
    status = str(payload.get("status") or "").lower()
    if "bounce" in status or "fail" in status:
        return True
    return False


def sync_delivery_for_messages(messages: list) -> DeliverySyncResult:
    """Check ZeptoMail logs for sent outreach messages."""
    from datetime import datetime, timezone

    from models.outreach_message import OutreachStatus

    if not zeptomail_configured():
        return DeliverySyncResult(errors=["ZeptoMail not configured"])

    result = DeliverySyncResult(errors=[])
    for msg in messages:
        ref = msg.zepto_email_reference
        if not ref:
            continue
        result.checked += 1
        payload = fetch_email_log_by_reference(ref)
        if not payload:
            continue
        if payload and is_bounce_payload(payload):
            result.bounced += 1
            msg.status = OutreachStatus.BOUNCED
            msg.bounced_at = datetime.now(timezone.utc)
    return result


def sync_delivery_for_bulk_sends(rows: list) -> DeliverySyncResult:
    """Check ZeptoMail logs for bulk email sends."""
    from datetime import datetime, timezone

    from models.bulk_email_send import BulkSendStatus

    if not zeptomail_configured():
        return DeliverySyncResult(errors=["ZeptoMail not configured"])

    result = DeliverySyncResult(errors=[])
    for row in rows:
        ref = row.zepto_email_reference
        if not ref:
            continue
        result.checked += 1
        payload = fetch_email_log_by_reference(ref)
        if not payload:
            continue
        if is_bounce_payload(payload):
            result.bounced += 1
            row.status = BulkSendStatus.BOUNCED
            row.bounced_at = datetime.now(timezone.utc)
    return result
