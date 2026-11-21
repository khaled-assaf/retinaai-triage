import pytest

from app.services.triage import TRIAGE_LEVELS, triage_case

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
    assert r == {"level": "urgent", **TRIAGE_LEVELS["urgent"]}
    assert r["label"] == "Urgent referral"
