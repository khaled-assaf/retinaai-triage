"""Rule-based triage + follow-up rules.

MEDICAL TEAMMATE: the rules live in the data tables directly below. Edit labels,
actions, the grade->level mapping, the ambiguity margin and the follow-up
deadlines here; the logic in `triage_case` should not need to change. The
confidence threshold comes from the CONFIDENCE_THRESHOLD env var (default 0.6).
Translations of labels/actions for the PDF reports live in app/reports/i18n.py,
so update those too if you change the English wording.
Run `pytest tests/test_triage.py` after editing.

Rule order (first match wins):
  1. image quality failed                          -> retake
  2. confidence < threshold, or top-2 too close    -> review (regardless of grade)
  3. otherwise map the predicted grade             -> routine / referable / urgent
A clinician's grade (PATCH /cases/{id}) overrides the AI using rule 3 only.
"""
from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------- rules as data
TRIAGE_LEVELS: dict[str, dict[str, str]] = {
    "urgent": {
        "label": "Urgent referral",
        "action": "Refer to ophthalmologist",
    },
    "review": {
        "label": "Needs clinician review",
        "action": "Clinician to review image and AI output before deciding",
    },
    "referable": {
        "label": "Schedule specialist appointment",
        "action": "Non-urgent referral to ophthalmology",
    },
    "retake": {
        "label": "Retake image",
        "action": "Recapture the fundus photo (check focus, lighting and centering)",
    },
    "routine": {
        "label": "Routine screening, rescreen in 12 months",
        "action": "No referral needed; rescreen in 12 months",
    },
}

# DR grade (0-4) -> triage level, used when the model is confident.
GRADE_TO_LEVEL: dict[int, str] = {
    0: "routine",    # No DR
    1: "routine",    # Mild NPDR
    2: "referable",  # Moderate NPDR
    3: "urgent",     # Severe NPDR
    4: "urgent",     # Proliferative DR
}

# If (top-1 probability - top-2 probability) < this, the model is torn between
# two grades -> send to clinician review.
TOP2_MIN_MARGIN = 0.15

# Queue sort order: most urgent first.
URGENCY_ORDER: list[str] = ["urgent", "review", "referable", "retake", "routine"]

# Follow-up created automatically for every case: what kind, and due within N days.
# PLACEHOLDER deadlines loosely based on the UK NHS DESP pathway
# (urgent R3 within ~2 weeks, R2 within ~13 weeks). Medical teammate: verify.
FOLLOW_UP_RULES: dict[str, dict] = {
    "urgent":    {"type": "referral",         "due_days": 14},
    "review":    {"type": "clinician_review", "due_days": 2},
    "referable": {"type": "referral",         "due_days": 90},
    "retake":    {"type": "retake",           "due_days": 7},
    "routine":   {"type": "rescreen",         "due_days": 365},
}
# ------------------------------------------------------------------------------


def _result(level: str, reason: str, source: str = "ai") -> dict[str, str]:
    return {"level": level, **TRIAGE_LEVELS[level], "reason": reason, "source": source}


def triage_case(
    quality_passed: bool,
    prediction: Optional[dict],
    confidence_threshold: float = 0.6,
) -> dict[str, str]:
    """Return {"level", "label", "action", "reason", "source"} for one case.

    `prediction` is {"grade": int, "probabilities": [5 floats], ...} or None.
    `reason` explains in plain English why this level was chosen.
    """
    if not quality_passed or prediction is None:
        return _result("retake", "Image quality check failed")

    probs = sorted(prediction["probabilities"], reverse=True)
    confidence = probs[0]
    margin = probs[0] - probs[1]
    if confidence < confidence_threshold:
        return _result(
            "review",
            f"Uncertain: confidence {confidence:.2f} is below the {confidence_threshold:.2f} threshold",
        )
    if margin < TOP2_MIN_MARGIN:
        return _result(
            "review",
            f"Uncertain: top two grades are only {margin:.2f} apart (minimum {TOP2_MIN_MARGIN:.2f})",
        )

    grade = int(prediction["grade"])
    return _result(GRADE_TO_LEVEL[grade], f"AI grade {grade} with confidence {confidence:.2f}")


def triage_from_clinician(grade: int) -> dict[str, str]:
    """Triage decided by a clinician's grade (overrides the AI)."""
    return _result(GRADE_TO_LEVEL[int(grade)], f"Clinician graded {int(grade)}", source="clinician")
