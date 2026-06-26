"""Sync inbound replies from Zoho Mail inbox into outreach_messages."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

TOKEN_URL_PATH = "/oauth/v2/token"


def _token_url() -> str:
    return get_settings().zoho_accounts_base + TOKEN_URL_PATH


@dataclass
class ReplySyncResult:
    checked: int = 0
    matched: int = 0
    errors: list[str] = field(default_factory=list)


def zoho_configured() -> bool:
    s = get_settings()
    return bool(
        s.zoho_client_id
        and s.zoho_client_secret
        and s.zoho_refresh_token
        and s.zoho_account_id
    )


def _access_token() -> str:
    s = get_settings()
    resp = requests.post(
        _token_url(),
        params={
            "refresh_token": s.zoho_refresh_token,
            "client_id": s.zoho_client_id,
            "client_secret": s.zoho_client_secret,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _list_inbox_messages(access_token: str, limit: int = 50) -> list[dict]:
    s = get_settings()
    url = f"{s.zoho_mail_api_base}/accounts/{s.zoho_account_id}/messages/view"
    resp = requests.get(
        url,
        headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
        params={"folderId": "inbox", "limit": limit, "sortBy": "date"},
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(resp.text[:300])
    data = resp.json()
    return data.get("data") or data.get("messages") or []


def _sender_email(item: dict) -> str:
    frm = item.get("fromAddress") or item.get("from") or ""
    if isinstance(frm, dict):
        return (frm.get("address") or frm.get("email") or "").lower()
    return str(frm).lower()


def sync_replies_for_messages(sent_messages: list) -> ReplySyncResult:
    """
    Match inbox senders to pending outreach_messages by recipient email.
    sent_messages: OutreachMessage rows with status sent, not replied/bounced.
    """
    result = ReplySyncResult()
    if not zoho_configured():
        result.errors.append(
            "Zoho Mail OAuth not configured — set ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, "
            "ZOHO_REFRESH_TOKEN, ZOHO_ACCOUNT_ID in secrets."
        )
        return result

    try:
        token = _access_token()
        inbox = _list_inbox_messages(token)
    except Exception as exc:
        result.errors.append(str(exc)[:300])
        return result

    pending_by_recipient: dict[str, list] = {}
    for msg in sent_messages:
        contact = msg.contact
        if not contact or not contact.email:
            continue
        pending_by_recipient.setdefault(contact.email.lower(), []).append(msg)

    result.checked = len(inbox)
    now = datetime.now(timezone.utc)
    for item in inbox:
        sender = _sender_email(item)
        if not sender or sender not in pending_by_recipient:
            continue
        for msg in pending_by_recipient[sender]:
            from models.outreach_message import OutreachStatus

            msg.status = OutreachStatus.REPLIED
            msg.replied_at = now
            result.matched += 1

    return result


def sync_replies_for_bulk_sends(sent_rows: list) -> ReplySyncResult:
    """Match Zoho inbox senders to bulk_email_sends by recipient email."""
    result = ReplySyncResult()
    if not zoho_configured():
        result.errors.append(
            "Zoho Mail OAuth not configured — set ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, "
            "ZOHO_REFRESH_TOKEN, ZOHO_ACCOUNT_ID in secrets."
        )
        return result

    try:
        token = _access_token()
        inbox = _list_inbox_messages(token, limit=200)
    except Exception as exc:
        result.errors.append(str(exc)[:300])
        return result

    pending_by_recipient: dict[str, list] = {}
    for row in sent_rows:
        email = (getattr(row, "recipient_email", "") or "").lower()
        if email:
            pending_by_recipient.setdefault(email, []).append(row)

    result.checked = len(inbox)
    now = datetime.now(timezone.utc)
    for item in inbox:
        sender = _sender_email(item)
        if not sender or sender not in pending_by_recipient:
            continue
        for row in pending_by_recipient[sender]:
            from models.bulk_email_send import BulkSendStatus

            row.status = BulkSendStatus.REPLIED
            row.replied_at = now
            result.matched += 1

    return result
