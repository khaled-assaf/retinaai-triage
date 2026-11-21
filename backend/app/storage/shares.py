"""Share tokens for public European Retina Passport links."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from .db import connect, iso, now_iso


def create_share(case_id: str, language: str, days_valid: int) -> dict:
    token = secrets.token_urlsafe(16)
    expires = iso(datetime.now(timezone.utc) + timedelta(days=days_valid))
    with connect() as conn:
        conn.execute(
            "INSERT INTO shares (token, case_id, language, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (token, case_id, language, now_iso(), expires),
        )
    return {"token": token, "case_id": case_id, "language": language, "expires_at": expires}


def get_valid_share(token: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM shares WHERE token = ?", (token,)).fetchone()
    if not row or row["expires_at"] < now_iso():
        return None
    return dict(row)
