"""Follow-up tracking: referrals, rescreens, retakes, clinician reviews.

Status lifecycle:  pending -> scheduled -> attended
                                       \\-> unconfirmed (automatically, 24 h after the appointment
                                                        if nobody confirmed attendance)
                                                        -> attended | missed (staff confirm)
                   any open status -> cancelled
Medical decision: a passed appointment is never marked "missed" automatically.
A pending follow-up past its due date is "overdue" (computed, not stored).
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from .db import connect, iso, now_iso

OPEN_STATUSES = ("pending", "scheduled", "unconfirmed", "missed")
# A scheduled appointment becomes "attendance unconfirmed" this long after its start
# time, unless someone marked it attended. Staff then confirm attended or missed.
MISSED_GRACE = timedelta(hours=24)

_SELECT = """
    SELECT f.*, p.full_name, p.country, p.language, c.triage_level
    FROM followups f
    LEFT JOIN patients p ON p.patient_ref = f.patient_ref
    LEFT JOIN cases c ON c.case_id = f.case_id
"""


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _to_followup(row: sqlite3.Row) -> dict:
    due = date.fromisoformat(row["due_date"])
    days = (due - _today()).days
    return {
        "followup_id": row["followup_id"],
        "case_id": row["case_id"],
        "patient_ref": row["patient_ref"],
        "patient_name": row["full_name"],
        "country": row["country"],
        "language": row["language"] or "en",
        "triage_level": row["triage_level"],
        "type": row["type"],
        "status": row["status"],
        "due_date": row["due_date"],
        "days_until_due": days,
        "overdue": row["status"] == "pending" and days < 0,
        "appointment_at": row["appointment_at"],
        "reminders_sent": row["reminders_sent"],
        "last_reminder_at": row["last_reminder_at"],
        "note": row["note"],
        "resolved_case_id": row["resolved_case_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_followup(
    case_id: str,
    patient_ref: Optional[str],
    type_: str,
    due_date: date,
    *,
    status: str = "pending",
    appointment_at: Optional[str] = None,
    created_at: Optional[str] = None,
) -> dict:
    ts = created_at or now_iso()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO followups (case_id, patient_ref, type, due_date, status, appointment_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (case_id, patient_ref, type_, due_date.isoformat(), status, appointment_at, ts, ts),
        )
        fid = f"f_{cur.lastrowid:04d}"
        conn.execute("UPDATE followups SET followup_id = ? WHERE id = ?", (fid, cur.lastrowid))
    result = get_followup(fid)
    assert result is not None
    return result


def get_followup(followup_id: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(_SELECT + " WHERE f.followup_id = ?", (followup_id,)).fetchone()
    return _to_followup(row) if row else None


def get_case_followup(case_id: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute(_SELECT + " WHERE f.case_id = ? ORDER BY f.id DESC LIMIT 1", (case_id,)).fetchone()
    return _to_followup(row) if row else None


def sweep_missed(now: Optional[datetime] = None) -> int:
    """Mark scheduled appointments that are long past as "unconfirmed" (attendance not
    confirmed). Returns how many changed. Name kept for compatibility."""
    cutoff = iso((now or datetime.now(timezone.utc)) - MISSED_GRACE)
    with connect() as conn:
        cur = conn.execute(
            "UPDATE followups SET status = 'unconfirmed', updated_at = ? "
            "WHERE status = 'scheduled' AND appointment_at IS NOT NULL AND appointment_at < ?",
            (now_iso(), cutoff),
        )
        return cur.rowcount


def _sort_key(f: dict):
    # What needs attention first: missed / unconfirmed, then overdue, then upcoming by due date, then closed.
    if f["status"] in ("missed", "unconfirmed"):
        bucket = 0
    elif f["overdue"]:
        bucket = 1
    elif f["status"] in ("pending", "scheduled"):
        bucket = 2
    else:
        bucket = 3
    return (bucket, f["due_date"])


def list_followups(
    status: Optional[str] = None,
    type_: Optional[str] = None,
    patient_ref: Optional[str] = None,
    overdue: Optional[bool] = None,
    open_only: bool = False,
    limit: int = 500,
) -> list[dict]:
    sweep_missed()
    sql = _SELECT + " WHERE 1 = 1"
    params: list = []
    if status:
        sql += " AND f.status = ?"
        params.append(status)
    if open_only:
        sql += f" AND f.status IN ({', '.join('?' * len(OPEN_STATUSES))})"
        params += list(OPEN_STATUSES)
    if type_:
        sql += " AND f.type = ?"
        params.append(type_)
    if patient_ref:
        sql += " AND f.patient_ref = ?"
        params.append(patient_ref)
    with connect() as conn:
        items = [_to_followup(r) for r in conn.execute(sql, params).fetchall()]
    if overdue is not None:
        items = [f for f in items if f["overdue"] == overdue]
    items.sort(key=_sort_key)
    return items[:limit]


def update_followup(
    followup_id: str,
    *,
    status: Optional[str] = None,
    appointment_at: Optional[str] = None,
    note: Optional[str] = None,
) -> Optional[dict]:
    sets, params = ["updated_at = ?"], [now_iso()]
    if appointment_at is not None:
        sets.append("appointment_at = ?")
        params.append(appointment_at)
        if status is None:
            status = "scheduled"
    if status is not None:
        sets.append("status = ?")
        params.append(status)
    if note is not None:
        sets.append("note = ?")
        params.append(note)
    with connect() as conn:
        cur = conn.execute(f"UPDATE followups SET {', '.join(sets)} WHERE followup_id = ?", (*params, followup_id))
        if cur.rowcount == 0:
            return None
    return get_followup(followup_id)


def record_reminder(followup_id: str) -> Optional[dict]:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE followups SET reminders_sent = reminders_sent + 1, last_reminder_at = ?, updated_at = ? "
            "WHERE followup_id = ?",
            (now_iso(), now_iso(), followup_id),
        )
        if cur.rowcount == 0:
            return None
    return get_followup(followup_id)


def resolve_by_new_case(patient_ref: str, new_case_id: str, at: Optional[str] = None) -> int:
    """A patient came back for a new screening: close their open rescreen/retake follow-ups."""
    with connect() as conn:
        cur = conn.execute(
            "UPDATE followups SET status = 'attended', resolved_case_id = ?, updated_at = ? "
            "WHERE patient_ref = ? AND type IN ('rescreen', 'retake') AND status IN ('pending', 'scheduled', 'unconfirmed') "
            "AND case_id != ?",
            (new_case_id, at or now_iso(), patient_ref, new_case_id),
        )
        return cur.rowcount


def replace_case_followup(case_id: str, type_: str, due_date: date) -> Optional[dict]:
    """After a clinician overrides triage: re-plan the case's follow-up if it's still pending."""
    with connect() as conn:
        cur = conn.execute(
            "UPDATE followups SET type = ?, due_date = ?, updated_at = ? WHERE case_id = ? AND status = 'pending'",
            (type_, due_date.isoformat(), now_iso(), case_id),
        )
        changed = cur.rowcount
    return get_case_followup(case_id) if changed else None


def due_date_from(created_at: str, due_days: int) -> date:
    return (datetime.fromisoformat(created_at.replace("Z", "+00:00")) + timedelta(days=due_days)).date()
