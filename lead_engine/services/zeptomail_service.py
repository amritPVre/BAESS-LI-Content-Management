"""ZeptoMail transactional send for outreach campaigns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

ZEPTO_SEND_URL = "https://api.zeptomail.com/v1.1/email"


@dataclass
class SendResult:
    success: bool
    email_reference: str = ""
    request_id: str = ""
    error: str = ""


def zeptomail_configured() -> bool:
    s = get_settings()
    return bool(
        s.zeptomail_send_token
        and s.zeptomail_from_address
        and "PASTE_" not in (s.zeptomail_send_token or "")
    )


def send_outreach_email(
    *,
    to_email: str,
    to_name: str,
    subject: str,
    body_text: str,
    message_id: str,
) -> SendResult:
    settings = get_settings()
    if not zeptomail_configured():
        return SendResult(
            success=False,
            error="ZeptoMail not configured — set ZEPTOMAIL_SEND_TOKEN and ZEPTOMAIL_FROM_ADDRESS in secrets.",
        )

    html_body = body_text.replace("\n", "<br>\n")
    payload: dict[str, Any] = {
        "from": {
            "address": settings.zeptomail_from_address,
            "name": settings.zeptomail_from_name,
        },
        "to": [
            {
                "email_address": {
                    "address": to_email,
                    "name": to_name or to_email,
                }
            }
        ],
        "subject": subject,
        "htmlbody": f"<div>{html_body}</div>",
        "textbody": body_text,
        "track_clicks": True,
        "track_opens": True,
        "client_reference": message_id,
        "mime_headers": {"X-BAESS-Message-Id": message_id},
    }
    if settings.zeptomail_reply_to:
        payload["reply_to"] = [
            {"address": settings.zeptomail_reply_to, "name": settings.zeptomail_from_name}
        ]

    token = settings.zeptomail_send_token.strip()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Zoho-enczapikey {token}",
    }

    try:
        resp = requests.post(
            ZEPTO_SEND_URL, json=payload, headers=headers, timeout=45
        )
        data = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            err = data.get("message") or data.get("error") or resp.text
            logger.error("ZeptoMail send failed: %s", err)
            return SendResult(success=False, error=str(err)[:500])

        email_info = (data.get("data") or [{}])[0] if isinstance(data.get("data"), list) else data
        ref = (
            email_info.get("email_reference")
            or data.get("email_reference")
            or data.get("request_id")
            or ""
        )
        return SendResult(
            success=True,
            email_reference=str(ref),
            request_id=str(data.get("request_id") or ""),
        )
    except requests.RequestException as exc:
        logger.exception("ZeptoMail request error")
        return SendResult(success=False, error=str(exc))


def send_test_email(
    *,
    to_email: str,
    to_name: str = "",
    subject: str | None = None,
    body_text: str | None = None,
) -> SendResult:
    """Send a one-off test email (not saved to outreach_messages or daily cap)."""
    from uuid import uuid4

    settings = get_settings()
    default_subject = "BAESS Outreach — test email"
    default_body = (
        "Hi,\n\n"
        "This is a test send from the BAESS Outreach Suite.\n\n"
        f"From: {settings.zeptomail_from_address}\n"
        f"Reply-To: {settings.zeptomail_reply_to or settings.zeptomail_from_address}\n\n"
        "If you reply, it should land in the configured Zoho Mail inbox.\n\n"
        "— BAESS Labs"
    )
    return send_outreach_email(
        to_email=to_email.strip(),
        to_name=to_name.strip() or to_email.strip(),
        subject=subject or default_subject,
        body_text=body_text or default_body,
        message_id=f"test-{uuid4()}",
    )
