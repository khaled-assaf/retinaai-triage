"""SIMULATED demo data: patients across Europe, screening history, follow-up outcomes.

Runs on startup when the DB is empty (SEED_DEMO_CASES=true). Deterministic (fixed
RNG seed), so every teammate sees the same demo. All people are fictional and the
images are the synthetic samples in backend/samples/. Reset with: delete
backend/storage_data/ and restart.
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .services.pipeline import analyze_image, review_case
from .storage import db, followups, patients

log = logging.getLogger("retinaai.seed")

N_PATIENTS = 30
RNG_SEED = 42

# country -> (report language, fictional first names, fictional last names)
COUNTRIES = {
    "RO": ("ro", ["Andrei", "Elena", "Mihai", "Ioana", "Radu", "Maria"], ["Popescu", "Ionescu", "Dumitru", "Stan", "Marin"]),
    "DE": ("de", ["Lukas", "Anna", "Jonas", "Sophie", "Felix"], ["Müller", "Schmidt", "Weber", "Becker", "Wagner"]),
    "AT": ("de", ["Florian", "Lena", "Tobias"], ["Gruber", "Huber", "Steiner"]),
    "FR": ("fr", ["Louis", "Chloé", "Hugo", "Léa", "Théo"], ["Martin", "Bernard", "Dubois", "Lefèvre"]),
    "BE": ("fr", ["Lucas", "Emma", "Noah"], ["Peeters", "Janssens", "Lambert"]),
    "ES": ("es", ["Pablo", "Lucía", "Javier", "Carmen"], ["García", "Fernández", "López", "Martínez"]),
    "IT": ("it", ["Marco", "Giulia", "Luca", "Francesca"], ["Rossi", "Russo", "Ferrari", "Esposito"]),
    "IE": ("en", ["Seán", "Aoife", "Ciarán"], ["Murphy", "Kelly", "Byrne"]),
    "NL": ("en", ["Daan", "Sanne", "Bram"], ["de Jong", "Jansen", "Visser"]),
    "PL": ("en", ["Jakub", "Zofia", "Piotr"], ["Nowak", "Kowalski", "Wiśniewski"]),
    "PT": ("en", ["João", "Beatriz", "Tiago"], ["Silva", "Santos", "Ferreira"]),
    "SE": ("en", ["Erik", "Astrid", "Oskar"], ["Andersson", "Johansson", "Lindberg"]),
}
COUNTRY_WEIGHTS = {"RO": 6, "DE": 4, "FR": 3, "ES": 3, "IT": 3, "AT": 2, "BE": 2, "IE": 2, "NL": 2, "PL": 1, "PT": 1, "SE": 1}
PHONE_PREFIX = {"RO": "+40", "DE": "+49", "AT": "+43", "FR": "+33", "BE": "+32", "ES": "+34", "IT": "+39",
                "IE": "+353", "NL": "+31", "PL": "+48", "PT": "+351", "SE": "+46"}

# sample id -> weight for historical screenings (roughly a screening population)
SAMPLE_WEIGHTS = {"normal": 45, "moderate": 18, "mild": 12, "severe": 13, "blurry": 12}
# The most recent visits of the first patients: guarantees every triage level is in today's queue.
RECENT_FIXED = ["severe", "mild", "moderate", "blurry", "normal", "severe", "moderate", "mild"]


def _ascii(s: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().replace(" ", "")


def seed(model, settings, sample_files: dict[str, Path]) -> int:
    rng = random.Random(RNG_SEED)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    samples_ids = [s for s in SAMPLE_WEIGHTS if s in sample_files]
    if not samples_ids:
        log.warning("No sample images found; skipping demo seed")
        return 0
    weights = [SAMPLE_WEIGHTS[s] for s in samples_ids]
    sample_bytes = {s: sample_files[s].read_bytes() for s in samples_ids}

    countries = list(COUNTRY_WEIGHTS)
    created = 0
    counters: dict[str, int] = {}
    for i in range(N_PATIENTS):
        cc = rng.choices(countries, weights=[COUNTRY_WEIGHTS[c] for c in countries])[0]
        lang, firsts, lasts = COUNTRIES[cc]
        counters[cc] = counters.get(cc, 0) + 1
        ref = f"EU-{cc}-{counters[cc]:03d}"
        first, last = rng.choice(firsts), rng.choice(lasts)

        # Screening dates: oldest first, 1-3 visits over the last ~18 months.
        n_visits = rng.choices([1, 2, 3], weights=[4, 4, 2])[0]
        visit = now - timedelta(days=rng.randint(20 + 150 * (n_visits - 1), 560), hours=rng.randint(0, 9))
        visits = []
        for v in range(n_visits):
            visits.append(visit)
            visit = visit + timedelta(days=rng.randint(120, 330))
            if visit > now - timedelta(days=3):
                break
        if i < len(RECENT_FIXED):  # make the latest visit recent and fixed
            visits[-1] = now - timedelta(days=rng.randint(0, 6), hours=rng.randint(1, 8))
            visits = [v for v in visits[:-1] if v < visits[-1] - timedelta(days=60)] + [visits[-1]]

        patients.upsert_patient(
            ref,
            simulated=True,
            created_at=db.iso(visits[0] - timedelta(days=1)),
            full_name=f"{first} {last}",
            birth_year=rng.randint(1944, 1992),
            sex=rng.choice(["F", "M"]),
            country=cc,
            language=lang,
            diabetes_type=rng.choices(["Type 2", "Type 1"], weights=[85, 15])[0],
            phone=f"{PHONE_PREFIX[cc]} 000 {rng.randint(100, 999)} {rng.randint(100, 999)}",
            email=f"{_ascii(first)}.{_ascii(last)}@example.com",
        )
        for j, when in enumerate(visits):
            last_visit = j == len(visits) - 1
            sample = RECENT_FIXED[i] if (last_visit and i < len(RECENT_FIXED)) else rng.choices(samples_ids, weights)[0]
            if sample not in sample_bytes:
                sample = samples_ids[0]
            analyze_image(sample_bytes[sample], ref, model, settings.confidence_threshold, created_at=db.iso(when))
            created += 1

    _simulate_outcomes(rng, now)
    _simulate_reviews(rng)
    return created


def _simulate_outcomes(rng: random.Random, now: datetime) -> None:
    """Give open follow-ups a realistic history: attended, missed, overdue, booked.

    Only a patient's most recent follow-up can stay missed/overdue; earlier ones were
    followed by another visit, so they are almost always attended.
    """
    latest: dict[str, tuple[str, str]] = {}
    for f in followups.list_followups(limit=100_000):
        if f["patient_ref"] and f["created_at"] >= latest.get(f["patient_ref"], ("", ""))[0]:
            latest[f["patient_ref"]] = (f["created_at"], f["followup_id"])
    latest_ids = {fid for _, fid in latest.values()}
    for f in followups.list_followups(open_only=True, limit=100_000):
        due = datetime.fromisoformat(f["due_date"]).replace(tzinfo=timezone.utc, hour=9)
        created = datetime.fromisoformat(f["created_at"].replace("Z", "+00:00"))
        if due < now:
            # Deadline has passed.
            appt = created + (due - created) * rng.uniform(0.4, 0.95)
            appt = appt.replace(hour=rng.choice([9, 10, 11, 14, 15]), minute=0, second=0)
            roll = rng.random() if f["followup_id"] in latest_ids else rng.random() * 0.7
            if roll < 0.6:
                followups.update_followup(f["followup_id"], status="attended", appointment_at=db.iso(appt))
            elif roll < 0.85:
                followups.update_followup(f["followup_id"], status="missed", appointment_at=db.iso(appt),
                                          note="Patient did not attend")
            # else: leave pending -> shows as overdue
        elif f["type"] in ("referral", "clinician_review") and rng.random() < 0.5:
            # Upcoming: some are already booked.
            span = max(1, (due - now).days)
            appt = (now + timedelta(days=rng.randint(1, span))).replace(hour=rng.choice([9, 11, 14]), minute=30, second=0)
            followups.update_followup(f["followup_id"], appointment_at=db.iso(appt))
    # A couple of reminders, so the dashboard shows that feature too.
    for f in followups.list_followups(overdue=True, limit=3):
        followups.record_reminder(f["followup_id"])


def _simulate_reviews(rng: random.Random) -> None:
    """A clinician has already reviewed a few older uncertain cases."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT case_id FROM cases WHERE triage_level = 'review' ORDER BY created_at LIMIT 3"
        ).fetchall()
    for r in rows[:2]:
        grade = rng.choice([1, 2])
        review_case(r["case_id"], "reviewed", grade, "Reviewed image; agree with AI's second choice." if grade == 2
                    else "Mild changes only. Routine rescreen.")
