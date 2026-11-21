"""Rule-based triage.

MEDICAL TEAMMATE: the rules live in the data tables directly below. Edit labels,
actions, the grade->level mapping, and the ambiguity margin here; the logic in
`triage_case` should not need to change. The confidence threshold comes from the
CONFIDENCE_THRESHOLD env var (default 0.6). Run `pytest tests/test_triage.py`
after editing.

Rule order (first match wins):
  1. image quality failed                          -> retake
  2. confidence < threshold, or top-2 too close    -> review (regardless of grade)
  3. otherwise map the predicted grade             -> routine / referable / urgent
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
# ------------------------------------------------------------------------------


def _result(level: str) -> dict[str, str]:
    return {"level": level, **TRIAGE_LEVELS[level]}


def triage_case(
    quality_passed: bool,
    prediction: Optional[dict],
    confidence_threshold: float = 0.6,
) -> dict[str, str]:
    """Return {"level", "label", "action"} for one case.

    `prediction` is {"grade": int, "probabilities": [5 floats], ...} or None.
    """
    if not quality_passed or prediction is None:
        return _result("retake")

    probs = sorted(prediction["probabilities"], reverse=True)
    confidence = probs[0]
    margin = probs[0] - probs[1]
    if confidence < confidence_threshold or margin < TOP2_MIN_MARGIN:
        return _result("review")

    return _result(GRADE_TO_LEVEL[int(prediction["grade"])])
