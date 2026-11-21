import pytest

from app.services.triage import FOLLOW_UP_RULES, TRIAGE_ACTIONS, triage_case, triage_from_clinician

T = 0.6


def pred(grade, probs):
    return {"grade": grade, "probabilities": probs}


def confident(grade, p=0.85):
    probs = [(1 - p) / 4] * 5
    probs[grade] = p
    return pred(grade, probs)


def test_quality_failed_is_retake():
    assert triage_case(False, None, T)["level"] == "retake"
    # Even if a prediction somehow exists, failed quality wins.
    assert triage_case(False, confident(4), T)["level"] == "retake"


@pytest.mark.parametrize("grade,level", [(0, "routine"), (1, "routine"), (2, "referable"), (3, "urgent"), (4, "urgent")])
def test_confident_grade_mapping(grade, level):
    assert triage_case(True, confident(grade), T)["level"] == level


def test_low_confidence_is_review_regardless_of_grade():
    assert triage_case(True, pred(4, [0.1, 0.1, 0.1, 0.15, 0.55]), T)["level"] == "review"
    assert triage_case(True, pred(0, [0.55, 0.15, 0.1, 0.1, 0.1]), T)["level"] == "review"


def test_close_top2_is_review():
    # Confidence 0.62 passes the 0.6 threshold, but the runner-up is within 0.15.
    assert triage_case(True, pred(2, [0.0, 0.0, 0.62, 0.50, 0.0]), T)["level"] == "review"
    # Same confidence with a clear margin (0.62 vs 0.30) -> normal mapping.
    assert triage_case(True, pred(2, [0.0, 0.30, 0.62, 0.08, 0.0]), T)["level"] == "referable"


def test_threshold_is_configurable():
    p = pred(3, [0.0, 0.05, 0.05, 0.7, 0.2])
    assert triage_case(True, p, 0.6)["level"] == "urgent"
    assert triage_case(True, p, 0.8)["level"] == "review"


def test_result_shape():
    r = triage_case(True, confident(3), T)
    assert r["level"] == "urgent" and r["action_code"] == "urgent_grade3"
    assert r["label"] == "High-priority ophthalmology assessment"
    assert triage_case(True, confident(4), T)["label"] == "Urgent ophthalmology referral"
    assert triage_case(True, confident(2), T)["label"] == "Non-urgent ophthalmology referral"
    assert r["source"] == "ai" and "top score" in r["reason"]


def test_review_reason_explains_uncertainty():
    assert "below" in triage_case(True, pred(4, [0.1, 0.1, 0.1, 0.15, 0.55]), T)["reason"]
    assert "apart" in triage_case(True, pred(2, [0.0, 0.0, 0.62, 0.50, 0.0]), T)["reason"]


def test_clinician_override():
    r = triage_from_clinician(2)
    assert r["level"] == "referable" and r["source"] == "clinician"


def test_every_action_has_followup_rule():
    assert set(FOLLOW_UP_RULES) == set(TRIAGE_ACTIONS)


# ---------------------------------------------------------------- safety rules (C10)
def test_safety_referable_catches_confident_mild():
    # AI says grade 1 with 0.80 confidence, but P(grade >= 2) = 0.18 >= 0.15
    r = triage_case(True, pred(1, [0.02, 0.80, 0.10, 0.05, 0.03]), T)
    # Medical decision: a clinician-review FLAG, never an automatic referral.
    assert r["level"] == "review" and r["safety_rule"] == "referable" and r["review_priority"] is None
    assert "18%" in r["reason"]
    # Below T -> stays routine
    r = triage_case(True, pred(1, [0.05, 0.85, 0.06, 0.02, 0.02]), T)
    assert r["level"] == "routine" and r["safety_rule"] is None


def test_safety_referable_like_missed_grade4_in_c10():
    # C10: both missed grade-4 cases had p_ref ~0.177 and were predicted grade 1.
    r = triage_case(True, pred(1, [0.05, 0.773, 0.07, 0.03, 0.077]), T)
    assert r["level"] == "review" and r["safety_rule"] == "referable"


def test_safety_urgent_catches_severe_called_moderate():
    r = triage_case(True, pred(2, [0.0, 0.05, 0.65, 0.25, 0.05]), T)  # P(3+4) = 0.30
    assert r["level"] == "review" and r["review_priority"] == "priority" and r["safety_rule"] == "urgent"
    r = triage_case(True, pred(2, [0.0, 0.10, 0.70, 0.15, 0.05]), T)  # P(3+4) = 0.20
    assert r["level"] == "referable" and r["safety_rule"] is None


def test_review_rule_comes_before_safety_rules():
    # Uncertain AND high p_ref: review wins, so the review rate is unchanged (C10).
    r = triage_case(True, pred(1, [0.05, 0.50, 0.30, 0.10, 0.05]), T)
    assert r["level"] == "review" and r["safety_rule"] is None


def test_safety_rules_can_be_disabled(monkeypatch):
    from app.services import triage as tr

    monkeypatch.setitem(tr.SAFETY_RULES, "referable", {"enabled": False, "min_p": 0.15})
    assert triage_case(True, pred(1, [0.02, 0.80, 0.10, 0.05, 0.03]), T)["level"] == "routine"


def test_routine_rescreen_interval_per_grade(monkeypatch):
    from app.services import triage as tr

    assert tr.follow_up_for("routine", 0) == ("rescreen", 365)
    monkeypatch.setitem(tr.ROUTINE_RESCREEN_DAYS, 1, 180)
    assert tr.follow_up_for("routine", 1) == ("rescreen", 180)
    assert tr.follow_up_for("routine", 0) == ("rescreen", 365)
    assert tr.follow_up_for("urgent", 4) == ("referral", 14)
    assert tr.follow_up_for("retake", None) == ("retake", 7)
