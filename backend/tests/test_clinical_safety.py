"""Clinical safety rules from the medical teammate (2026-11-21) and the 7 required
European Retina Passport test cases. Report decisions are checked in English AND
Romanian and must be identical (only the wording may differ)."""
import copy

import pytest

from app.reports.content import build_report, round_to_100
from app.reports.i18n import T
from app.reports.pdf import build_passport_pdf
from app.services.triage import triage_case, triage_from_clinician

LANGS = ["en", "ro"]


def make_case(*, grade=0, probs=None, quality_passed=True, symptoms=None, eye="unknown", review=None,
              case_id="c_9001", created_at="2026-11-21T10:00:00Z", model="effb0-v0.1-baseline"):
    if probs is None:
        probs = [0.02] * 5
        probs[grade] = 0.92
    pred = {"grade": grade, "label": "x", "confidence": max(probs), "probabilities": probs} if quality_passed else None
    triage = triage_case(quality_passed, pred, 0.6, symptoms=symptoms)
    review = review or {"status": "pending", "clinician_grade": None, "note": None, "reviewed_at": None}
    from app.services.triage import clinical_status

    return {
        "case_id": case_id, "created_at": created_at, "patient_ref": "TEST-1",
        "quality": {"passed": quality_passed, "score": 0.9 if quality_passed else 0.0,
                    "reason": "OK" if quality_passed else "Image is blurry",
                    "checks": {"blur": 0.9 if quality_passed else 0.0, "exposure": "ok", "framing": "ok"}},
        "prediction": pred, "heatmap_url": "/x" if quality_passed else None, "image_url": "/y",
        "eye": eye, "symptoms": {"collected": symptoms is not None, "reported": symptoms or []},
        "triage": triage, "review": review,
        "clinical_status": clinical_status(triage["level"], review, grade if quality_passed else None),
        "model_version": model, "processing_ms": 10, "report_url": "/r", "followup": None,
    }


def reports(case, history=(), **kw):
    out = {lang: build_report(case=case, patient=None, history=list(history), lang=lang,
                              confidence_threshold=0.6, now="2026-11-21T12:00:00Z", **kw) for lang in LANGS}
    assert out["en"]["codes"] == out["ro"]["codes"], "EN and RO must use identical clinical logic"
    return out


# ------------------------------------------------------------------ the 7 required cases
def test_1_grade0_pending_review_is_provisional_not_clearance():
    r = reports(make_case(grade=0))
    c = r["en"]["codes"]
    assert c["clinical_status"] == "pending_review" and c["provisional"] and c["workflow"] == "provisional"
    assert r["en"]["text"]["clinical_status_detail"] == T["en"]["provisional"]
    assert r["ro"]["text"]["clinical_status_detail"] == T["ro"]["provisional"]
    statement = r["en"]["text"]["result_statement"]
    assert statement.startswith("No signs of diabetic retinopathy detected by this screening model")
    assert "No referral needed" not in str(r["en"]["text"])  # never a definitive clearance
    assert c["limits_note"] and c["emergency_warning"]


def test_2_grade0_after_grade1_shows_careful_comparison():
    history = [{"case_id": "c_0001", "created_at": "2025-10-26T10:00:00Z", "grade": 1, "eye": "right",
                "triage_level": "routine", "action_code": "routine"}]
    r = reports(make_case(grade=0, eye="right"), history)
    assert r["en"]["codes"]["history_status"] == "different"
    txt = r["en"]["text"]
    assert txt["history_status"] == "Difference from previous assessment — verification suggested."
    assert "does not by itself indicate improvement" in txt["history_note"]
    assert r["en"]["codes"]["level"] == "routine"  # disagreement alone never escalates
    # Same history, eye not recorded -> comparison explicitly limited
    r2 = reports(make_case(grade=0, eye="unknown"), history)
    assert r2["en"]["codes"]["history_status"] == "limited"


def test_3_grade2_referral_subject_to_confirmation():
    r = reports(make_case(grade=2))
    assert r["en"]["codes"]["action_code"] == "referable"
    assert r["en"]["text"]["triage_label"] == "Non-urgent ophthalmology referral"
    assert "subject to clinical confirmation" in r["en"]["text"]["result_statement"]
    assert r["ro"]["text"]["triage_label"] == "Trimitere neurgentă către medicul oftalmolog"


@pytest.mark.parametrize("kind", ["low_confidence", "poor_quality"])
def test_4_low_confidence_or_poor_quality_never_clears(kind):
    if kind == "low_confidence":
        case = make_case(grade=0, probs=[0.45, 0.30, 0.15, 0.05, 0.05])
        expect_workflow, expect_result = "human_review", "uncertain"
    else:
        case = make_case(quality_passed=False)
        expect_workflow, expect_result = "retake", "retake"
    r = reports(case)
    c = r["en"]["codes"]
    assert c["workflow"] == expect_workflow and c["result_kind"] == expect_result
    assert not c["routine_suggestion"]
    assert "No signs of diabetic retinopathy" not in r["en"]["text"]["result_statement"]


def test_5_urgent_symptoms_override_grade0():
    r = reports(make_case(grade=0, symptoms=["sudden_vision_loss"]))
    c = r["en"]["codes"]
    assert c["level"] == "emergency" and c["workflow"] == "urgent_assessment" and c["result_kind"] == "emergency"
    assert c["trustgate"]["symptoms"] == "warning"
    assert "same-day" in r["en"]["text"]["result_statement"]
    # Even a poor-quality image cannot hide reported symptoms.
    assert triage_case(False, None, 0.6, symptoms=["curtain_shadow"])["level"] == "emergency"


def test_6_single_eye_never_claims_both_eyes_cleared():
    r = reports(make_case(grade=0, eye="right"))
    assert r["en"]["codes"]["eye_status"] == "single_eye"
    assert "Single-eye assessment" in r["en"]["text"]["eye_note"]
    # Unknown eye is shown as "Not recorded", never invented.
    r2 = reports(make_case(grade=0, eye="unknown"))
    assert ("Eye", "Not recorded") in r2["en"]["text"]["screening_rows"]
    # Both eyes on the same day -> noted (separate reports)
    other = [{"case_id": "c_9002", "created_at": "2026-11-21T10:05:00Z", "grade": 0, "eye": "left",
              "triage_level": "routine", "action_code": "routine"}]
    r3 = reports(make_case(grade=0, eye="right"), other)
    assert r3["en"]["codes"]["eye_status"] == "both_eyes"


@pytest.mark.parametrize("case_kwargs", [
    {"grade": 0}, {"grade": 2}, {"grade": 4}, {"quality_passed": False},
    {"grade": 0, "symptoms": ["flashes_floaters"]}, {"grade": 1, "probs": [0.02, 0.80, 0.10, 0.05, 0.03]},
])
def test_7_english_and_romanian_identical_logic_and_render(case_kwargs):
    case = make_case(**case_kwargs)
    r = reports(case)  # asserts identical codes
    assert len(r["en"]["text"]["why"]) == len(r["ro"]["text"]["why"])
    assert [row[1] for row in r["en"]["text"]["scores"]] == [row[1] for row in r["ro"]["text"]["scores"]]
    for lang in LANGS:
        pdf = build_passport_pdf(case=case, patient=None, history=[], image_path=None, heatmap_path=None, lang=lang)
        assert pdf.startswith(b"%PDF")


# ------------------------------------------------------------------ other safety requirements
@pytest.mark.parametrize("probs", [
    [0.96, 0.012, 0.012, 0.012, 0.004], [0.955, 0.0113, 0.0127, 0.0196, 0.0014], [0.2] * 5, [0.333, 0.333, 0.334, 0, 0],
])
def test_scores_always_total_100(probs):
    pct = round_to_100(probs)
    assert sum(pct) == 100 and all(p >= 0 for p in pct)


def test_scores_labelled_as_uncalibrated_and_top_score_wording():
    r = reports(make_case(grade=0, probs=[0.96, 0.01, 0.01, 0.015, 0.005]))
    assert r["en"]["text"]["scores_caption"] == "Model output scores (not calibrated clinical probabilities)"
    assert r["en"]["text"]["top_score"] == "AI model score: 96%"
    assert sum(row[1] for row in r["en"]["text"]["scores"]) == 100


def test_trustgate_shows_not_collected_and_not_assessed_honestly():
    r = reports(make_case(quality_passed=False))
    tg = r["en"]["codes"]["trustgate"]
    assert tg == {"quality": "failed", "confidence": "not_assessed", "symptoms": "not_collected", "workflow": "retake"}


def test_mock_heatmap_labelled_simulated():
    r = reports(make_case(grade=2, model="mock-v0"))
    assert r["en"]["codes"]["heatmap"] == "simulated"
    assert r["en"]["text"]["heatmap_caption"] == "Simulated visualization (mock model)"
    assert reports(make_case(grade=2))["en"]["codes"]["heatmap"] == "model"


def test_clinician_confirmed_and_modified_statuses():
    confirmed = make_case(grade=2, review={"status": "reviewed", "clinician_grade": 2, "note": None,
                                           "reviewed_at": "2026-11-21T11:00:00Z"})
    assert reports(confirmed)["en"]["codes"]["clinical_status"] == "confirmed"
    modified = make_case(grade=2, review={"status": "reviewed", "clinician_grade": 3, "note": "exudates",
                                          "reviewed_at": "2026-11-21T11:00:00Z"})
    r = reports(modified)
    assert r["en"]["codes"]["clinical_status"] == "modified"
    assert "supersedes the AI result (grade 2" in r["en"]["text"]["clinical_status_detail"]


def test_clinician_cannot_silently_drop_emergency_symptoms():
    assert triage_from_clinician(0, symptoms=["sudden_vision_loss"])["level"] == "emergency"
    assert triage_from_clinician(0)["level"] == "routine"


def test_shared_copy_hides_personal_details():
    case = make_case(grade=0)
    patient = {"full_name": "Maria Test", "birth_year": 1960, "diabetes_type": "Type 2", "simulated": True}
    r = build_report(case=case, patient=patient, history=[], lang="en", confidence_threshold=0.6, public=True)
    rows = dict(r["text"]["patient_rows"])
    assert rows["Name"] == rows["Year of birth"] == "Hidden in shared copy"
    assert "Maria Test" not in str(r["text"])


# ------------------------------------------------------------------ API-level
def test_api_emergency_and_validation(client):
    r = client.post("/api/samples/normal/analyze?patient_ref=SYM-1&eye=left&symptoms=curtain_shadow")
    case = r.json()
    assert case["triage"]["level"] == "emergency" and case["eye"] == "left"
    assert case["followup"]["type"] == "emergency_assessment" and case["followup"]["days_until_due"] == 0
    assert client.get("/api/queue").json()[0]["triage_level"] == "emergency"  # top of the queue
    assert client.post("/api/samples/normal/analyze?symptoms=headache").status_code == 400
    assert client.post("/api/samples/normal/analyze?eye=both").status_code == 400
    none = client.post("/api/samples/normal/analyze?symptoms=none").json()
    assert none["symptoms"] == {"collected": True, "reported": []} and none["triage"]["level"] == "routine"


def test_api_override_preserves_ai_result_in_audit_log(client):
    case = client.post("/api/samples/moderate/analyze?patient_ref=AUD-1").json()
    ai_triage = copy.deepcopy(case["triage"])
    after = client.patch(f"/api/cases/{case['case_id']}",
                         json={"status": "reviewed", "clinician_grade": 3, "note": "IRMA seen"}).json()
    assert after["clinical_status"] == "modified"
    assert after["prediction"] == case["prediction"]  # AI prediction untouched
    assert after["triage"]["source"] == "clinician" and after["triage"]["action_code"] == "urgent_grade3"
    assert after["triage"]["ai_triage"]["action_code"] == ai_triage["action_code"]
    audit = client.get(f"/api/cases/{case['case_id']}/audit").json()
    assert [e["event"] for e in audit] == ["case_created", "clinician_review"]
    review = audit[1]["details"]
    assert review["reason"] == "IRMA seen" and review["ai_grade"] == 2 and review["clinician_grade"] == 3
    assert review["triage_after"]["action_code"] == "urgent_grade3"
    assert client.get("/api/cases/c_9999/audit").status_code == 404


def test_api_shared_passport_is_one_page_pdf(client):
    cid = client.post("/api/samples/normal/analyze?patient_ref=EU-RO-001&eye=right").json()["case_id"]
    token = client.post(f"/api/cases/{cid}/share?lang=ro").json()["token"]
    pdf = client.get(f"/api/passport/{token}").content
    assert pdf.startswith(b"%PDF") and pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") <= 2


def test_history_uses_case_order_within_the_same_second():
    history = [
        {"case_id": "c_0005", "created_at": "2025-01-01T10:00:00Z", "grade": 0, "eye": "right",
         "triage_level": "routine", "action_code": "routine"},
        {"case_id": "c_9000", "created_at": "2026-11-21T10:00:00Z", "grade": 1, "eye": "right",
         "triage_level": "routine", "action_code": "routine"},
    ]
    r = reports(make_case(grade=0, eye="right", case_id="c_9001", created_at="2026-11-21T10:00:00Z"), history)
    assert r["en"]["codes"]["history_status"] == "different"  # compared with c_9000 (grade 1), not c_0005
    assert r["en"]["text"]["history_compare"][0][1].startswith("1 ")


def test_clinician_decision_caption():
    reviewed = make_case(grade=2, review={"status": "reviewed", "clinician_grade": 3, "note": None,
                                          "reviewed_at": "2026-11-21T11:00:00Z"})
    reviewed["triage"] = triage_from_clinician(3)
    r = reports(reviewed)
    assert r["en"]["text"]["triage_label_caption"] == "Clinician decision"
    assert r["ro"]["text"]["triage_label_caption"] == "Decizia medicului"
    assert reports(make_case(grade=2))["en"]["text"]["triage_label_caption"] == "AI-suggested triage"
