#!/usr/bin/env python3
"""Start localhost:8080, open Zoho auth in browser, exchange code automatically."""

from __future__ import annotations

import http.server
import json
import socketserver
import sys
import threading
import urllib.parse
import webbrowser
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


def exchange_and_print(code: str, secrets: dict) -> int:
    client_id = (secrets.get("ZOHO_CLIENT_ID") or "").strip()
    client_secret = (secrets.get("ZOHO_CLIENT_SECRET") or "").strip()
    redirect_uri = (secrets.get("ZOHO_REDIRECT_URI") or "http://localhost:8080").strip()
    accounts_base = (secrets.get("ZOHO_ACCOUNTS_BASE") or "https://accounts.zoho.in").rstrip("/")
    mail_base = (secrets.get("ZOHO_MAIL_API_BASE") or "https://mail.zoho.in/api").rstrip("/")
    target_email = (secrets.get("ZEPTOMAIL_REPLY_TO") or secrets.get("AUTH_EMAIL") or "").strip().lower()
    if target_email in ("", "you@yourdomain.com"):
        target_email = (secrets.get("AUTH_EMAIL") or "").strip().lower()

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
    token_data = token_resp.json()
    if token_resp.status_code >= 400 or "access_token" not in token_data:
        print(json.dumps(token_data, indent=2))
        return 1

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")
    print("access_token: OK")

    acc_resp = requests.get(
        f"{mail_base}/accounts",
        headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
        timeout=30,
    )
    acc_data = acc_resp.json()
    if acc_resp.status_code >= 400:
        print(json.dumps(acc_data, indent=2))
        return 1

    accounts = acc_data.get("data") or acc_data.get("accounts") or []
    account_id = ""
    for acc in accounts:
        email = (
            acc.get("primaryEmailAddress")
            or acc.get("emailAddress")
            or acc.get("accountDisplayName")
            or ""
        ).lower()
        if target_email and (target_email in email or email == target_email):
            account_id = str(acc.get("accountId") or acc.get("account_id") or "")
            print(f"Matched account: {email} -> accountId={account_id}")
            break
    if not account_id and accounts:
        account_id = str(accounts[0].get("accountId") or "")
        print(f"Using first accountId={account_id}")

    text = SECRETS.read_text(encoding="utf-8")
    if refresh_token:
        text = _replace_secret(text, "ZOHO_REFRESH_TOKEN", refresh_token)
    if account_id:
        text = _replace_secret(text, "ZOHO_ACCOUNT_ID", account_id)
    SECRETS.write_text(text, encoding="utf-8")
    print("\nUpdated .streamlit/secrets.toml with ZOHO_REFRESH_TOKEN and ZOHO_ACCOUNT_ID.")
    return 0


def _replace_secret(text: str, key: str, value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    lines = text.splitlines(keepends=True)
    prefix = f"{key} ="
    for i, line in enumerate(lines):
        if line.lstrip().startswith(prefix):
            eol = "\n" if line.endswith("\n") else ""
            lines[i] = f'{key} = "{escaped}"{eol}'
            return "".join(lines)
    return text + f'\n{key} = "{escaped}"\n'


def main() -> None:
    secrets = load_secrets()
    client_id = (secrets.get("ZOHO_CLIENT_ID") or "").strip()
    redirect_uri = (secrets.get("ZOHO_REDIRECT_URI") or "http://localhost:8080").strip()
    accounts_base = (secrets.get("ZOHO_ACCOUNTS_BASE") or "https://accounts.zoho.in").rstrip("/")

    if not client_id:
        print("ERROR: ZOHO_CLIENT_ID missing in secrets.toml")
        sys.exit(1)

    scope = "ZohoMail.accounts.READ,ZohoMail.messages.READ"
    auth_url = (
        f"{accounts_base}/oauth/v2/auth?"
        f"scope={urllib.parse.quote(scope)}&"
        f"client_id={urllib.parse.quote(client_id)}&"
        f"response_type=code&access_type=offline&prompt=consent&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}"
    )

    result: dict[str, str | None] = {"code": None}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            pass

        def do_GET(self) -> None:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in qs:
                result["code"] = qs["code"][0]
                body = b"<html><body><h2>Zoho authorized.</h2><p>You can close this tab.</p></body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self.send_response(400)
                self.end_headers()

    print(f"Listening on {redirect_uri} ...")
    print("Opening Zoho login in your browser — click Accept, then wait here.")
    with socketserver.TCPServer(("127.0.0.1", 8080), Handler) as httpd:
        webbrowser.open(auth_url)
        httpd.serve_forever()

    code = result.get("code")
    if not code:
        print("ERROR: No authorization code received.")
        sys.exit(1)

    sys.exit(exchange_and_print(str(code), secrets))


if __name__ == "__main__":
    main()
