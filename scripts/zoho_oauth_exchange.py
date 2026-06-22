#!/usr/bin/env python3
"""One-time Zoho India OAuth: exchange code → refresh token + account ID."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / ".streamlit" / "secrets.toml"


def load_secrets() -> dict:
    try:
        import tomllib

        return tomllib.loads(SECRETS.read_bytes())
    except ImportError:
        import tomli

        return tomli.loads(SECRETS.read_text(encoding="utf-8"))


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/zoho_oauth_exchange.py AUTHORIZATION_CODE")
        sys.exit(1)

    code = sys.argv[1].strip()
    secrets = load_secrets()

    client_id = (secrets.get("ZOHO_CLIENT_ID") or "").strip()
    client_secret = (secrets.get("ZOHO_CLIENT_SECRET") or "").strip()
    redirect_uri = (secrets.get("ZOHO_REDIRECT_URI") or "http://localhost:8080").strip()
    accounts_base = (secrets.get("ZOHO_ACCOUNTS_BASE") or "https://accounts.zoho.in").rstrip("/")
    mail_base = (secrets.get("ZOHO_MAIL_API_BASE") or "https://mail.zoho.in/api").rstrip("/")
    target_email = (secrets.get("ZEPTOMAIL_REPLY_TO") or secrets.get("AUTH_EMAIL") or "").strip().lower()

    if not client_id or not client_secret or "PASTE_" in client_id:
        print("ERROR: Set ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET in .streamlit/secrets.toml first.")
        sys.exit(1)

    print(f"Exchanging code via {accounts_base} ...")
    token_resp = requests.post(
        f"{accounts_base}/oauth/v2/token",
        params={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    print(f"Token HTTP {token_resp.status_code}")
    token_data = token_resp.json()
    if token_resp.status_code >= 400 or "access_token" not in token_data:
        print(json.dumps(token_data, indent=2))
        sys.exit(1)

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")
    print("access_token: OK")
    if refresh_token:
        print(f"refresh_token: {refresh_token[:20]}... (full token below)")
    else:
        print("WARNING: No refresh_token — revoke app access in Zoho and re-auth with prompt=consent")

    print(f"\nFetching mail accounts from {mail_base}/accounts ...")
    acc_resp = requests.get(
        f"{mail_base}/accounts",
        headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
        timeout=30,
    )
    print(f"Accounts HTTP {acc_resp.status_code}")
    acc_data = acc_resp.json()
    if acc_resp.status_code >= 400:
        print(json.dumps(acc_data, indent=2))
        sys.exit(1)

    accounts = acc_data.get("data") or acc_data.get("accounts") or []
    account_id = ""
    for acc in accounts:
        email = (
            acc.get("primaryEmailAddress")
            or acc.get("emailAddress")
            or acc.get("accountDisplayName")
            or ""
        ).lower()
        if target_email and target_email in email or email == target_email:
            account_id = str(acc.get("accountId") or acc.get("account_id") or "")
            print(f"Matched account: {email} -> accountId={account_id}")
            break

    if not account_id and accounts:
        account_id = str(accounts[0].get("accountId") or "")
        print(f"Using first accountId={account_id}")

    print("\n" + "=" * 60)
    print("Add these to .streamlit/secrets.toml (and Streamlit Cloud Secrets):\n")
    if refresh_token:
        print(f'ZOHO_REFRESH_TOKEN = "{refresh_token}"')
    print(f'ZOHO_ACCOUNT_ID = "{account_id}"')
    print(f'ZOHO_ACCOUNTS_BASE = "{accounts_base}"')
    print(f'ZOHO_MAIL_API_BASE = "{mail_base}"')
    print("=" * 60)


if __name__ == "__main__":
    main()
