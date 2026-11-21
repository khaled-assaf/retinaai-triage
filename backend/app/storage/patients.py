"""Patient records. In the demo they are SIMULATED (simulated=1)."""
from __future__ import annotations

import sqlite3
from typing import Optional

from .db import connect, now_iso

FIELDS = ("full_name", "birth_year", "sex", "country", "language", "diabetes_type", "phone", "email")


def _to_patient(row: sqlite3.Row) -> dict:
    d = {k: row[k] for k in ("patient_ref", *FIELDS, "created_at")}
    d["simulated"] = bool(row["simulated"])
    return d


def get_patient(patient_ref: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM patients WHERE patient_ref = ?", (patient_ref,)).fetchone()
    return _to_patient(row) if row else None


def upsert_patient(patient_ref: str, simulated: bool = False, created_at: Optional[str] = None, **fields) -> dict:
    """Create the patient, or update the given (non-None) fields if it exists."""
    fields = {k: v for k, v in fields.items() if k in FIELDS and v is not None}
    with connect() as conn:
        exists = conn.execute("SELECT 1 FROM patients WHERE patient_ref = ?", (patient_ref,)).fetchone()
        if exists:
            if fields:
                sets = ", ".join(f"{k} = ?" for k in fields)
                conn.execute(f"UPDATE patients SET {sets} WHERE patient_ref = ?", (*fields.values(), patient_ref))
        else:
            fields.setdefault("language", "en")
            cols = ["patient_ref", "simulated", "created_at", *fields]
            conn.execute(
                f"INSERT INTO patients ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                (patient_ref, int(simulated), created_at or now_iso(), *fields.values()),
            )
    patient = get_patient(patient_ref)
    assert patient is not None
    return patient


def ensure_patient(patient_ref: Optional[str]) -> None:
    """Make sure an uploaded case's patient_ref exists as a (minimal) patient."""
    if patient_ref and not get_patient(patient_ref):
        upsert_patient(patient_ref)


def list_patients(country: Optional[str] = None, q: Optional[str] = None) -> list[dict]:
    """Patients with their latest screening and open follow-up count."""
    sql = """
        SELECT p.*,
               (SELECT COUNT(*) FROM cases c WHERE c.patient_ref = p.patient_ref) AS screenings,
               (SELECT c.case_id FROM cases c WHERE c.patient_ref = p.patient_ref
                  ORDER BY c.created_at DESC, c.id DESC LIMIT 1) AS last_case_id,
               (SELECT c.created_at FROM cases c WHERE c.patient_ref = p.patient_ref
                  ORDER BY c.created_at DESC, c.id DESC LIMIT 1) AS last_screened_at,
               (SELECT c.triage_level FROM cases c WHERE c.patient_ref = p.patient_ref
                  ORDER BY c.created_at DESC, c.id DESC LIMIT 1) AS last_triage_level,
               (SELECT COUNT(*) FROM followups f WHERE f.patient_ref = p.patient_ref
                  AND f.status IN ('pending', 'scheduled', 'unconfirmed', 'missed')) AS open_followups
        FROM patients p WHERE 1 = 1"""
    params: list = []
    if country:
        sql += " AND p.country = ?"
        params.append(country.upper())
    if q:
        sql += " AND (p.patient_ref LIKE ? OR p.full_name LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY last_screened_at DESC NULLS LAST, p.patient_ref"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        d = _to_patient(r)
        d.update(
            screenings=r["screenings"],
            last_case_id=r["last_case_id"],
            last_screened_at=r["last_screened_at"],
            last_triage_level=r["last_triage_level"],
            open_followups=r["open_followups"],
        )
        out.append(d)
    return out
