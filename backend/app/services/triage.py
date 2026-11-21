"""Rule-based triage + follow-up rules (research prototype, NOT clinically validated).

Clinical decisions by the medical teammate (2026-11-21), based on ADA Standards of Care
2026, AAO DR Preferred Practice Pattern, ICO Guidelines and the NHS Diabetic Eye
Screening pathway. See docs/CLINICAL_SAFETY.md.

MEDICAL TEAMMATE: the rules live in the data tables directly below. The logic in
`triage_case` should not need to change. Translations of labels/actions for the
PDF live in app/reports/i18n.py (keyed by the same action codes): update both.
Run `pytest tests/test_triage.py` after editing.

Rule order (first match wins):
  0. urgent eye symptoms reported                       -> emergency  (overrides EVERYTHING,
                                                           incl. a poor image and grade 0)
  1. image quality failed                               -> retake
  2. confidence < threshold, or top-2 too close         -> review
  3. SAFETY FLAG: grade 0-1 but P(grade >= 2) >= T      -> review            (clinician review)
  4. SAFETY FLAG: grade 2   but P(grade >= 3) >= U      -> review, priority  (priority review)
  5. otherwise map the predicted grade                  -> routine / referable / urgent
A clinician's grade (PATCH /cases/{id}) supersedes the AI (rule 5 only), except that
reported urgent symptoms keep the case at "emergency".
"""
from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------- rules as data
# Every outcome has an ACTION CODE; `level` decides queue order and colours.
TRIAGE_ACTIONS: dict[str, dict[str, str]] = {
    "emergency": {
        "level": "emergency",
        "label": "Emergency eye assessment",
        "action": "Same-day eye assessment: urgent eye symptoms reported",
    },
    "urgent_grade4": {
        "level": "urgent",
        "label": "Urgent ophthalmology referral",
        "action": "Refer urgently to ophthalmology (proliferative DR suggested by AI)",
    },
    "urgent_grade3": {
        "level": "urgent",
        "label": "High-priority ophthalmology assessment",
        "action": "Refer for high-priority ophthalmology assessment (severe NPDR suggested by AI)",
    },
    "review_priority": {
        "level": "review",
        "label": "Priority clinician review",
        "action": "Clinician to review image promptly: the AI output suggests possible severe disease",
    },
    "review": {
        "level": "review",
        "label": "Needs clinician review",
        "action": "Clinician to review image and AI output before deciding",
    },
    "referable": {
        "level": "referable",
        "label": "Non-urgent ophthalmology referral",
        "action": "Refer to ophthalmology (non-urgent)",
    },
    "retake": {
        "level": "retake",
        "label": "Retake image",
        "action": "Recapture the fundus photo (check focus, lighting and centering)",
    },
    "routine": {
        "level": "routine",
        "label": "Routine screening, rescreen in 12 months",
        "action": "No referral suggested; rescreen in 12 months, subject to clinician confirmation",
    },
}
# Backwards-compatible view: level -> default label/action.
TRIAGE_LEVELS: dict[str, dict[str, str]] = {
    "emergency": TRIAGE_ACTIONS["emergency"],
    "urgent": TRIAGE_ACTIONS["urgent_grade4"],
    "review": TRIAGE_ACTIONS["review"],
    "referable": TRIAGE_ACTIONS["referable"],
    "retake": TRIAGE_ACTIONS["retake"],
    "routine": TRIAGE_ACTIONS["routine"],
}

# DR grade (0-4) -> action code, used when the model is confident (and for clinician grades).
GRADE_TO_ACTION: dict[int, str] = {
    0: "routine",        # No DR: 12 months if image adequate and no other concerns
    1: "routine",        # Mild NPDR: usually 12 months (6-12 by individual risk, clinician decides)
    2: "referable",      # Moderate NPDR: ophthalmology referral
    3: "urgent_grade3",  # Severe NPDR: high-priority ophthalmology assessment
    4: "urgent_grade4",  # PDR: urgent ophthalmology referral
}

# Urgent symptoms that override the AI result (codes are translated in i18n.py).
URGENT_SYMPTOMS: dict[str, str] = {
    "sudden_vision_loss": "Sudden vision loss",
    "curtain_shadow": "New curtain or shadow over vision",
    "flashes_floaters": "New flashes or floaters",
    "other_acute": "Other serious acute eye symptom",
}

# If (top-1 probability - top-2 probability) < this, the model is torn between two grades.
TOP2_MIN_MARGIN = 0.15

# Safety FLAGS (rules 3 and 4): approved by the medical teammate as CLINICIAN-REVIEW
# flags, never as automatic referrals. EXPERIMENTAL thresholds from the AI teammate's
# validation analysis (ai/BACKEND_HANDOFF.md C10); must be calibrated and validated
# before any clinical use.
SAFETY_RULES: dict[str, dict] = {
    "referable": {"enabled": True, "min_p": 0.15},  # P(grade 2+3+4) when the AI says grade 0-1
    "urgent":    {"enabled": True, "min_p": 0.25},  # P(grade 3+4) when the AI says grade 2
}

# Queue sort order: most urgent first (priority reviews sort before normal reviews).
URGENCY_ORDER: list[str] = ["emergency", "urgent", "review", "referable", "retake", "routine"]

# Follow-up per action code: type, and due within N days.
# NHS pathway (medical teammate): R3A referral issued within 2 weeks (consultation within
# 6 weeks); R2/M1 referral issued within 3 weeks (consultation within 13 weeks).
# Our AI grades 0-4 are NOT equivalent to NHS R grades: these are prototype targets.
# Clinician review (48 h) and retake (7 days) are internal operational targets only.
FOLLOW_UP_RULES: dict[str, dict] = {
    "emergency":       {"type": "emergency_assessment", "due_days": 0},   # same day
    "urgent_grade4":   {"type": "referral",             "due_days": 14},
    "urgent_grade3":   {"type": "referral",             "due_days": 14},
    "review_priority": {"type": "clinician_review",     "due_days": 1},   # escalate sooner
    "review":          {"type": "clinician_review",     "due_days": 2},
    "referable":       {"type": "referral",             "due_days": 21},
    "retake":          {"type": "retake",               "due_days": 7},
    "routine":         {"type": "rescreen",             "due_days": 365},
}

# Rescreen interval (days) for ROUTINE cases, per grade. Grade 1: "usually 12 months;
# consider 6-12 months depending on individual risk and clinician assessment".
ROUTINE_RESCREEN_DAYS: dict[int, int] = {0: 365, 1: 365}

# Levels whose AI suggestion stays PROVISIONAL until a clinician reviews it.
# A failed image needs a recapture, not a review.
REVIEW_REQUIRED_LEVELS = {"emergency", "urgent", "review", "referable", "routine"}
# ------------------------------------------------------------------------------


def _result(action_code: str, reason: str, source: str = "ai",
            safety_rule: Optional[str] = None, symptoms: Optional[list[str]] = None) -> dict:
    a = TRIAGE_ACTIONS[action_code]
    return {
        "level": a["level"],
        "label": a["label"],
        "action": a["action"],
        "action_code": action_code,
        "reason": reason,
        "source": source,
        "safety_rule": safety_rule,
        "review_priority": "priority" if action_code == "review_priority" else None,
        "symptoms": symptoms or [],
    }


def _emergency(symptoms: list[str], prefix: str = "") -> dict:
    names = ", ".join(URGENT_SYMPTOMS.get(s, s) for s in symptoms)
    return _result("emergency", f"{prefix}Urgent eye symptoms reported: {names}. "
                   "Symptoms override the AI result.", symptoms=symptoms)


def triage_case(
    quality_passed: bool,
    prediction: Optional[dict],
    confidence_threshold: float = 0.6,
    symptoms: Optional[list[str]] = None,
) -> dict:
    """Triage for one case: {"level", "label", "action", "action_code", "reason", "source",
    "safety_rule", "review_priority", "symptoms"}.

    `prediction` is {"grade": int, "probabilities": [5 floats], ...} or None.
    `symptoms` is a list of URGENT_SYMPTOMS codes reported by the patient (or None).
    """
    if symptoms:
        return _emergency(symptoms)
    if not quality_passed or prediction is None:
        return _result("retake", "Image quality check failed")

    probs = sorted(prediction["probabilities"], reverse=True)
    confidence = probs[0]
    margin = probs[0] - probs[1]
    if confidence < confidence_threshold:
        return _result(
            "review",
            f"Uncertain: AI top score {confidence:.2f} is below the experimental {confidence_threshold:.2f} threshold",
        )
    if margin < TOP2_MIN_MARGIN:
        return _result(
            "review",
            f"Uncertain: top two AI scores are only {margin:.2f} apart (minimum {TOP2_MIN_MARGIN:.2f})",
        )

    grade = int(prediction["grade"])
    p = prediction["probabilities"]
    p_ref, p_urgent = float(sum(p[2:])), float(sum(p[3:]))
    rule = SAFETY_RULES["referable"]
    if rule["enabled"] and grade <= 1 and p_ref >= rule["min_p"]:
        return _result(
            "review",
            f"Safety flag: AI grade {grade}, but {p_ref:.0%} of the model score is on grade 2 or worse "
            f"(experimental threshold {rule['min_p']:.0%}); clinician review required",
            safety_rule="referable",
        )
    rule = SAFETY_RULES["urgent"]
    if rule["enabled"] and grade == 2 and p_urgent >= rule["min_p"]:
        return _result(
            "review_priority",
            f"Safety flag: AI grade 2, but {p_urgent:.0%} of the model score is on grade 3 or worse "
            f"(experimental threshold {rule['min_p']:.0%}); priority clinician review",
            safety_rule="urgent",
        )
    return _result(GRADE_TO_ACTION[grade], f"AI grade {grade} with top score {confidence:.2f}")


def triage_from_clinician(grade: int, symptoms: Optional[list[str]] = None) -> dict:
    """Triage decided by a clinician's grade (supersedes the AI). Reported urgent
    symptoms still require an emergency assessment."""
    grade = int(grade)
    if symptoms:
        r = _emergency(symptoms, prefix=f"Clinician graded {grade}. ")
        r["source"] = "clinician"
        return r
    return _result(GRADE_TO_ACTION[grade], f"Clinician graded {grade}", source="clinician")


def follow_up_for(action_code_or_level: str, grade: Optional[int]) -> tuple[str, int]:
    """(follow-up type, due in days) for an action code (or a plain level) and its grade."""
    code = action_code_or_level
    if code not in FOLLOW_UP_RULES:  # a plain level, e.g. from older data
        code = {"urgent": "urgent_grade4"}.get(code, code)
    rule = FOLLOW_UP_RULES[code]
    days = rule["due_days"]
    if code == "routine" and grade is not None:
        days = ROUTINE_RESCREEN_DAYS.get(int(grade), days)
    return rule["type"], days


def clinical_status(level: str, review: dict, ai_grade: Optional[int]) -> str:
    """pending_review | confirmed | modified | not_required (see REVIEW_REQUIRED_LEVELS).

    confirmed = reviewed without a different grade; modified = clinician grade differs from
    the AI grade (or the AI gave no grade)."""
    if review.get("status") != "reviewed":
        return "pending_review" if level in REVIEW_REQUIRED_LEVELS else "not_required"
    cg = review.get("clinician_grade")
    if cg is None:
        return "confirmed"
    return "confirmed" if ai_grade is not None and int(cg) == int(ai_grade) else "modified"
