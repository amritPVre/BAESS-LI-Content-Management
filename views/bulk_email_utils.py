"""CSV parsing and {first_name} template rendering for bulk email."""

from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

EMAIL_COLS = ("email", "e-mail", "e_mail", "email_address", "email address", "mail")
NAME_COLS = (
    "name",
    "full_name",
    "full name",
    "contact_name",
    "contact name",
    "recipient",
    "first_name",
    "firstname",
)


def extract_first_name(full_name: str) -> str:
    cleaned = (full_name or "").strip()
    if not cleaned:
        return "there"
    token = re.split(r"[\s,]+", cleaned)[0]
    return token or "there"


def render_template(template: str, *, name: str, email: str) -> str:
    first = extract_first_name(name)
    replacements = {
        "{first_name}": first,
        "{First_Name}": first.capitalize() if first != "there" else first,
        "{FIRST_NAME}": first.upper() if first != "there" else first,
        "{name}": name.strip() or first,
        "{Name}": (name.strip() or first).title(),
        "{email}": email.strip(),
    }
    out = template
    for key, value in replacements.items():
        out = out.replace(key, value)
    return out


def _pick_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {c.lower().strip(): c for c in columns}
    for cand in candidates:
        if cand in normalized:
            return normalized[cand]
    for col in columns:
        low = col.lower().strip()
        for cand in candidates:
            if cand in low:
                return col
    return None


def parse_recipients_csv(
    file_bytes: bytes, *, max_rows: int = 500
) -> tuple[list[dict[str, str]], str | None]:
    """Return list of {name, email, first_name} and optional error message."""
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as exc:
        return [], f"Could not read CSV: {exc}"

    if df.empty:
        return [], "CSV file is empty."

    email_col = _pick_column(list(df.columns), EMAIL_COLS)
    name_col = _pick_column(list(df.columns), NAME_COLS)
    if not email_col:
        return [], "CSV must include an email column (e.g. `email`, `Email`, `email_address`)."

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for _, row in df.iterrows():
        email = str(row.get(email_col, "")).strip().lower()
        if not email or "@" not in email or email in seen:
            continue
        seen.add(email)
        name = str(row.get(name_col, "")).strip() if name_col else ""
        rows.append(
            {
                "email": email,
                "name": name,
                "first_name": extract_first_name(name),
            }
        )
        if len(rows) >= max_rows:
            break

    if not rows:
        return [], "No valid email rows found in CSV."
    if len(seen) > max_rows:
        return rows, f"Only the first {max_rows} unique emails are loaded (batch cap)."
    return rows, None


def preview_rows(
    recipients: list[dict[str, str]], subject: str, body: str, limit: int = 5
) -> list[dict[str, Any]]:
    out = []
    for row in recipients[:limit]:
        out.append(
            {
                "email": row["email"],
                "name": row["name"] or row["first_name"],
                "subject": render_template(subject, name=row["name"], email=row["email"]),
                "body": render_template(body, name=row["name"], email=row["email"]),
            }
        )
    return out
