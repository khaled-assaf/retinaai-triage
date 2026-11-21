"""Pydantic models for the API contract (see docs/API.md). Change both together."""
from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field

Grade = Annotated[int, Field(ge=0, le=4)]
TriageLevel = Literal["emergency", "urgent", "review", "referable", "retake", "routine"]
ActionCode = Literal["emergency", "urgent_grade4", "urgent_grade3", "review_priority", "review",
                     "referable", "retake", "routine"]
ReviewStatus = Literal["pending", "reviewed"]
ClinicalStatus = Literal["pending_review", "confirmed", "modified", "not_required"]
Eye = Literal["right", "left", "unknown"]
Symptom = Literal["sudden_vision_loss", "curtain_shadow", "flashes_floaters", "other_acute"]
FollowupType = Literal["emergency_assessment", "referral", "rescreen", "retake", "clinician_review"]
FollowupStatus = Literal["pending", "scheduled", "unconfirmed", "attended", "missed", "cancelled"]

DISCLAIMER = "Research prototype. Not for clinical diagnosis."


class QualityChecks(BaseModel):
    blur: float = Field(description="Sharpness score 0..1 (higher is sharper)")
    exposure: Literal["ok", "underexposed", "overexposed"]
    framing: Literal["ok", "too_small", "not_found"]


class Quality(BaseModel):
    passed: bool
    score: float = Field(ge=0, le=1)
    reason: str
    checks: QualityChecks


class Prediction(BaseModel):
    grade: Grade
    label: str
    confidence: float = Field(ge=0, le=1)
    probabilities: list[float] = Field(min_length=5, max_length=5)


class Triage(BaseModel):
    level: TriageLevel
    label: str
    action: str
    action_code: Optional[ActionCode] = Field(None, description="Rule outcome; translations are keyed by it")
    reason: Optional[str] = Field(None, description="Why this level was chosen, e.g. why the AI was uncertain")
    source: Literal["ai", "clinician"] = "ai"
    safety_rule: Optional[Literal["referable", "urgent"]] = Field(
        None, description="Set when an experimental safety flag sent the case to clinician review"
    )
    review_priority: Optional[Literal["priority"]] = Field(None, description="'priority' = priority clinician review")
    symptoms: list[Symptom] = Field(default_factory=list, description="Urgent symptoms that triggered 'emergency'")
    ai_triage: Optional[dict] = Field(None, description="The original AI triage, kept after a clinician override")


class Review(BaseModel):
    status: ReviewStatus
    clinician_grade: Optional[Grade] = None
    note: Optional[str] = None
    reviewed_at: Optional[str] = None


class Symptoms(BaseModel):
    collected: bool = Field(description="false = urgent symptoms were not asked/recorded")
    reported: list[Symptom] = Field(default_factory=list)


class AuditEvent(BaseModel):
    at: str
    actor: Literal["ai", "clinician", "system"]
    event: str
    details: dict


class Followup(BaseModel):
    followup_id: str
    case_id: str
    patient_ref: Optional[str] = None
    patient_name: Optional[str] = None
    country: Optional[str] = None
    language: str = "en"
    triage_level: Optional[TriageLevel] = None
    type: FollowupType
    status: FollowupStatus
    due_date: str = Field(description="YYYY-MM-DD")
    days_until_due: int = Field(description="Negative = days overdue")
    overdue: bool = Field(description="pending and past its due date")
    appointment_at: Optional[str] = None
    reminders_sent: int = 0
    last_reminder_at: Optional[str] = None
    note: Optional[str] = None
    resolved_case_id: Optional[str] = None
    created_at: str
    updated_at: str


class FollowupUpdate(BaseModel):
    status: Optional[FollowupStatus] = None
    appointment_at: Optional[str] = Field(None, description="ISO-8601; setting it without status implies 'scheduled'")
    note: Optional[str] = Field(None, max_length=2000)


class ReminderResult(BaseModel):
    followup: Followup
    channel: Literal["sms"] = "sms"
    language: str
    message: str
    simulated: bool = True


class Case(BaseModel):
    case_id: str
    created_at: str
    patient_ref: Optional[str] = None
    quality: Quality
    prediction: Optional[Prediction] = None
    heatmap_url: Optional[str] = None
    image_url: str
    eye: Eye = "unknown"
    symptoms: Symptoms = Field(default_factory=lambda: Symptoms(collected=False))
    triage: Triage
    review: Review
    clinical_status: ClinicalStatus = Field(
        description="pending_review = AI suggestion is provisional; confirmed / modified by a clinician; "
                    "not_required = no review in the configured workflow (image retake)"
    )
    model_version: str
    processing_ms: int
    report_url: str
    followup: Optional[Followup] = None
    disclaimer: str = DISCLAIMER


class CaseSummary(BaseModel):
    """Lightweight row for the queue. No image data, only URLs."""

    case_id: str
    created_at: str
    patient_ref: Optional[str] = None
    triage_level: TriageLevel
    triage_label: str
    review_priority: Optional[Literal["priority"]] = None
    action_code: Optional[ActionCode] = None
    eye: Eye = "unknown"
    clinical_status: ClinicalStatus = "pending_review"
    grade: Optional[Grade] = None
    grade_label: Optional[str] = None
    confidence: Optional[float] = None
    quality_passed: bool
    review_status: ReviewStatus
    thumbnail_url: str


class ReviewUpdate(BaseModel):
    status: ReviewStatus = "reviewed"
    clinician_grade: Optional[Grade] = None
    note: Optional[str] = Field(default=None, max_length=2000)


class Sample(BaseModel):
    id: str
    label: str
    image_url: str
    expected_grade: Optional[Grade] = None
    description: Optional[str] = None


class Health(BaseModel):
    status: Literal["ok"]
    model_loaded: bool
    mock: bool
    model_version: str


class PatientIn(BaseModel):
    full_name: Optional[str] = Field(None, max_length=200)
    birth_year: Optional[int] = Field(None, ge=1900, le=2100)
    sex: Optional[Literal["F", "M", "X"]] = None
    country: Optional[str] = Field(None, min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    language: Optional[str] = Field(None, description="Preferred report language, see /api/languages")
    diabetes_type: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=200)


class PatientCreate(PatientIn):
    patient_ref: str = Field(min_length=1, max_length=100)


class Patient(PatientIn):
    patient_ref: str
    language: str = "en"
    simulated: bool
    created_at: str


class PatientSummary(Patient):
    screenings: int
    last_case_id: Optional[str] = None
    last_screened_at: Optional[str] = None
    last_triage_level: Optional[TriageLevel] = None
    open_followups: int


class PatientDetail(BaseModel):
    patient: Patient
    cases: list[CaseSummary]
    followups: list[Followup]


class Language(BaseModel):
    code: str
    name: str


class ShareLink(BaseModel):
    token: str
    case_id: str
    language: str
    expires_at: str
    passport_url: str = Field(description="Public PDF link (absolute, uses PUBLIC_BASE_URL)")


class CountryStats(BaseModel):
    country: str
    patients: int
    screenings: int
    referable_or_urgent: int
    missed: int


class MonthStats(BaseModel):
    month: str
    screenings: int
    referrals: int


class Dashboard(BaseModel):
    totals: dict[str, int]
    triage: dict[str, int]
    followups: dict[str, int]
    attendance_rate: Optional[float] = Field(None, description="attended / (attended + missed)")
    by_country: list[CountryStats]
    monthly: list[MonthStats]
