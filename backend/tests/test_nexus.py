"""Patients, follow-up tracking, European Retina Passport, dashboard."""
from datetime import datetime, timedelta, timezone

import pytest

from app.reports.i18n import LANGUAGES, T
from app.storage import followups as fu_store
from conftest import SAMPLES


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ patients
def test_seeded_patients_are_simulated_europeans(client):
    patients = client.get("/api/patients").json()
    assert len(patients) >= 30
    assert all(p["simulated"] for p in patients if p["patient_ref"].startswith("EU-"))
    assert len({p["country"] for p in patients if p["country"]}) >= 6
    assert {p["language"] for p in patients} <= set(LANGUAGES)


def test_create_get_update_patient(client):
    body = {"patient_ref": "NEW-001", "full_name": "Test Person", "country": "ro", "language": "ro", "birth_year": 1970}
    r = client.post("/api/patients", json=body)
    assert r.status_code == 201 and r.json()["country"] == "RO" and r.json()["simulated"] is False
    assert client.post("/api/patients", json=body).status_code == 409
    assert client.patch("/api/patients/NEW-001", json={"language": "xx"}).status_code == 400
    assert client.patch("/api/patients/NEW-001", json={"language": "de"}).json()["language"] == "de"
    detail = client.get("/api/patients/NEW-001").json()
    assert detail["patient"]["full_name"] == "Test Person" and detail["cases"] == []
    assert client.get("/api/patients/NOPE").status_code == 404


def test_upload_creates_patient_and_followup(client):
    data = (SAMPLES / "normal.jpg").read_bytes()
    case = client.post("/api/analyze", files={"image": ("e.jpg", data, "image/jpeg")}, data={"patient_ref": "WALKIN-1"}).json()
    assert case["triage"]["level"] == "routine"
    assert case["followup"]["type"] == "rescreen" and case["followup"]["status"] == "pending"
    assert case["followup"]["days_until_due"] >= 364
    assert client.get("/api/patients/WALKIN-1").status_code == 200


def test_new_screening_closes_previous_rescreen(client):
    first = client.post("/api/samples/normal/analyze?patient_ref=LOOP-1").json()
    second = client.post("/api/samples/moderate/analyze?patient_ref=LOOP-1").json()
    old = client.get(f"/api/followups/{first['followup']['followup_id']}").json()
    assert old["status"] == "attended" and old["resolved_case_id"] == second["case_id"]
    assert second["followup"]["type"] == "referral"
    history = client.get("/api/patients/LOOP-1").json()["cases"]
    assert [c["case_id"] for c in history] == [second["case_id"], first["case_id"]]


# ------------------------------------------------------------------ follow-ups
def test_followups_sorted_by_attention(client):
    items = client.get("/api/followups").json()
    assert items
    def bucket(f):
        return 0 if f["status"] == "missed" else 1 if f["overdue"] else 2 if f["status"] in ("pending", "scheduled") else 3
    buckets = [bucket(f) for f in items]
    assert buckets == sorted(buckets)
    assert any(f["status"] == "missed" for f in items)  # simulated data has missed appointments
    assert any(f["status"] == "attended" for f in items)
    for f in client.get("/api/followups?overdue=true").json():
        assert f["status"] == "pending" and f["days_until_due"] < 0


def test_schedule_then_attendance_unconfirmed(client):
    fid = client.post("/api/samples/severe/analyze?patient_ref=MISS-1").json()["followup"]["followup_id"]
    past = iso(datetime.now(timezone.utc) - timedelta(days=3))
    r = client.patch(f"/api/followups/{fid}", json={"appointment_at": past})
    assert r.json()["status"] == "scheduled"  # appointment_at implies scheduled
    # Listing sweeps appointments >24h in the past to "unconfirmed" (never "missed" automatically).
    listed = {f["followup_id"]: f for f in client.get("/api/followups?patient_ref=MISS-1").json()}
    assert listed[fid]["status"] == "unconfirmed"
    # Staff confirm the patient did not attend.
    assert client.patch(f"/api/followups/{fid}", json={"status": "missed"}).json()["status"] == "missed"
    # The coordinator reschedules, the patient attends.
    future = iso(datetime.now(timezone.utc) + timedelta(days=2))
    assert client.patch(f"/api/followups/{fid}", json={"appointment_at": future}).json()["status"] == "scheduled"
    assert client.patch(f"/api/followups/{fid}", json={"status": "attended"}).json()["status"] == "attended"
    assert client.patch(f"/api/followups/{fid}", json={"appointment_at": "not a date"}).status_code == 400
    assert client.patch("/api/followups/f_9999", json={"status": "attended"}).status_code == 404


def test_sweep_respects_grace_period(client):
    fid = client.post("/api/samples/severe/analyze?patient_ref=GRACE-1").json()["followup"]["followup_id"]
    recent = iso(datetime.now(timezone.utc) - timedelta(hours=2))
    client.patch(f"/api/followups/{fid}", json={"appointment_at": recent})
    fu_store.sweep_missed()
    assert client.get(f"/api/followups/{fid}").json()["status"] == "scheduled"


@pytest.mark.parametrize("lang", ["ro", "de", "fr"])
def test_reminder_in_patient_language(client, lang):
    ref = f"REMIND-{lang}"
    client.post("/api/patients", json={"patient_ref": ref, "full_name": "Ana Test", "language": lang})
    fid = client.post(f"/api/samples/severe/analyze?patient_ref={ref}").json()["followup"]["followup_id"]
    r = client.post(f"/api/followups/{fid}/remind").json()
    assert r["language"] == lang and r["simulated"] is True
    assert "Ana Test" in r["message"]
    assert T[lang]["followup_types"]["referral"] in r["message"]
    assert r["followup"]["reminders_sent"] == 1
    client.patch(f"/api/followups/{fid}", json={"status": "attended"})
    assert client.post(f"/api/followups/{fid}/remind").status_code == 400


def test_clinician_review_closes_review_and_plans_referral(client):
    # "mild" sample -> uncertain AI -> review + clinician_review follow-up
    case = client.post("/api/samples/mild/analyze?patient_ref=REV-1").json()
    assert case["triage"]["level"] == "review" and case["followup"]["type"] == "clinician_review"
    old_fid = case["followup"]["followup_id"]
    after = client.patch(f"/api/cases/{case['case_id']}", json={"status": "reviewed", "clinician_grade": 2}).json()
    assert after["triage"]["level"] == "referable" and after["triage"]["source"] == "clinician"
    assert after["followup"]["type"] == "referral" and after["followup"]["followup_id"] != old_fid
    assert client.get(f"/api/followups/{old_fid}").json()["status"] == "attended"
    # The queue now ranks it by the clinician's decision.
    row = next(c for c in client.get("/api/queue").json() if c["case_id"] == case["case_id"])
    assert row["triage_level"] == "referable"


# ------------------------------------------------------------------ passport
def test_languages(client):
    langs = client.get("/api/languages").json()
    assert {l["code"] for l in langs} == set(LANGUAGES) and len(langs) >= 6


def test_translations_complete():
    keys = set(T["en"])
    for lang in LANGUAGES:
        assert set(T[lang]) == keys, f"{lang} missing {keys - set(T[lang])}"
        assert len(T[lang]["grades"]) == 5
        assert set(T[lang]["actions"]) == set(T["en"]["actions"])
        for nested in ("clinical_statuses", "workflow", "symptoms", "followup_types", "followup_statuses", "eyes"):
            assert set(T[lang][nested]) == set(T["en"][nested]), (lang, nested)


@pytest.mark.parametrize("lang", list(LANGUAGES))
def test_report_pdf_every_language(client, lang):
    cid = client.post("/api/samples/severe/analyze?patient_ref=PDF-1").json()["case_id"]
    r = client.get(f"/api/cases/{cid}/report.pdf?lang={lang}")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF") and len(r.content) < 400_000
    assert f"-{lang}.pdf" in r.headers["content-disposition"]


def test_report_for_failed_quality_and_unknown_lang(client):
    cid = client.post("/api/samples/blurry/analyze").json()["case_id"]
    r = client.get(f"/api/cases/{cid}/report.pdf?lang=zz&download=true")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert r.headers["content-disposition"].startswith("attachment") and "-en.pdf" in r.headers["content-disposition"]
    assert client.get("/api/cases/c_9999/report.pdf").status_code == 404


def test_report_defaults_to_patient_language(client):
    client.post("/api/patients", json={"patient_ref": "LANG-IT", "language": "it"})
    cid = client.post("/api/samples/normal/analyze?patient_ref=LANG-IT").json()["case_id"]
    assert "-it.pdf" in client.get(f"/api/cases/{cid}/report.pdf").headers["content-disposition"]


def test_share_link(client):
    cid = client.post("/api/samples/moderate/analyze").json()["case_id"]
    share = client.post(f"/api/cases/{cid}/share?lang=es").json()
    assert share["language"] == "es" and share["passport_url"].endswith(f"/api/passport/{share['token']}")
    r = client.get(f"/api/passport/{share['token']}")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert client.get("/api/passport/not-a-token").status_code == 404
    assert client.post("/api/cases/c_9999/share").status_code == 404


# ------------------------------------------------------------------ dashboard
def test_dashboard(client):
    d = client.get("/api/dashboard").json()
    assert d["totals"]["patients"] >= 30 and d["totals"]["screenings"] >= 30
    assert set(d["triage"]) == {"emergency", "urgent", "review", "referable", "retake", "routine"}
    assert {"pending", "scheduled", "unconfirmed", "attended", "missed", "cancelled", "overdue"} <= set(d["followups"])
    assert 0 < d["attendance_rate"] <= 1
    assert len(d["by_country"]) >= 6 and all(len(c["country"]) == 2 for c in d["by_country"])
    months = [m["month"] for m in d["monthly"]]
    assert months == sorted(months) and len(months) >= 6


@pytest.mark.parametrize("rule,probs", [("referable", [0.02, 0.80, 0.10, 0.05, 0.03]),
                                         ("urgent", [0.0, 0.05, 0.65, 0.25, 0.05])])
def test_passport_pdf_for_safety_escalation(client, rule, probs):
    from app.reports.pdf import build_passport_pdf
    from app.services.triage import triage_case

    case = client.post("/api/samples/normal/analyze?patient_ref=SAFE-1").json()
    grade = probs.index(max(probs))
    case["prediction"] = {"grade": grade, "label": "x", "confidence": max(probs), "probabilities": probs}
    case["triage"] = triage_case(True, case["prediction"], 0.6)
    assert case["triage"]["safety_rule"] == rule
    for lang in LANGUAGES:
        pdf = build_passport_pdf(case=case, patient=None, history=[], image_path=None,
                                 heatmap_path=None, lang=lang)
        assert pdf.startswith(b"%PDF")
