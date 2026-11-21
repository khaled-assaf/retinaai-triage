"""Aggregates for the follow-up / Europe dashboard."""
from __future__ import annotations

from .db import connect
from .followups import list_followups

TRIAGE_KEYS = ("emergency", "urgent", "review", "referable", "retake", "routine")
STATUS_KEYS = ("pending", "scheduled", "unconfirmed", "attended", "missed", "cancelled")


def dashboard() -> dict:
    items = list_followups(limit=100_000)  # also sweeps missed appointments
    with connect() as conn:
        n_patients = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        n_cases = conn.execute("SELECT COUNT(*) FROM cases WHERE case_id IS NOT NULL").fetchone()[0]
        pending_review = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE triage_level = 'review' AND review_status = 'pending'"
        ).fetchone()[0]
        triage = dict(conn.execute("SELECT triage_level, COUNT(*) FROM cases GROUP BY triage_level").fetchall())
        by_country = conn.execute(
            """
            SELECT p.country AS country,
                   COUNT(DISTINCT p.patient_ref) AS patients,
                   COUNT(c.id) AS screenings,
                   SUM(CASE WHEN c.triage_level IN ('referable', 'urgent') THEN 1 ELSE 0 END) AS referable_or_urgent,
                   (SELECT COUNT(*) FROM followups f JOIN patients p2 ON p2.patient_ref = f.patient_ref
                     WHERE p2.country = p.country AND f.status = 'missed') AS missed
            FROM patients p LEFT JOIN cases c ON c.patient_ref = p.patient_ref
            WHERE p.country IS NOT NULL
            GROUP BY p.country ORDER BY screenings DESC, country
            """
        ).fetchall()
        monthly = conn.execute(
            """
            SELECT substr(created_at, 1, 7) AS month,
                   COUNT(*) AS screenings,
                   SUM(CASE WHEN triage_level IN ('referable', 'urgent') THEN 1 ELSE 0 END) AS referrals
            FROM cases GROUP BY month ORDER BY month
            """
        ).fetchall()

    fu_counts = {k: 0 for k in STATUS_KEYS}
    for f in items:
        fu_counts[f["status"]] = fu_counts.get(f["status"], 0) + 1
    fu_counts["overdue"] = sum(1 for f in items if f["overdue"])
    done = fu_counts["attended"] + fu_counts["missed"]

    return {
        "totals": {
            "patients": n_patients,
            "screenings": n_cases,
            "pending_review": pending_review,
            "open_referrals": sum(
                1 for f in items if f["type"] == "referral" and f["status"] in ("pending", "scheduled", "unconfirmed", "missed")
            ),
        },
        "triage": {k: triage.get(k, 0) for k in TRIAGE_KEYS},
        "followups": fu_counts,
        "attendance_rate": round(fu_counts["attended"] / done, 3) if done else None,
        "by_country": [dict(r) for r in by_country],
        "monthly": [dict(r) for r in monthly],
    }
