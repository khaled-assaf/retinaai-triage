"""Pydantic models for the API contract (see docs/API.md). Change both together."""
from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field

Grade = Annotated[int, Field(ge=0, le=4)]
TriageLevel = Literal["urgent", "review", "referable", "retake", "routine"]
ReviewStatus = Literal["pending", "reviewed"]

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


class Review(BaseModel):
    status: ReviewStatus
    clinician_grade: Optional[Grade] = None
    note: Optional[str] = None


class Case(BaseModel):
    case_id: str
    created_at: str
    patient_ref: Optional[str] = None
    quality: Quality
    prediction: Optional[Prediction] = None
    heatmap_url: Optional[str] = None
    image_url: str
    triage: Triage
    review: Review
    model_version: str
    processing_ms: int
    disclaimer: str = DISCLAIMER


class CaseSummary(BaseModel):
    """Lightweight row for the queue. No image data, only URLs."""

    case_id: str
    created_at: str
    patient_ref: Optional[str] = None
    triage_level: TriageLevel
    triage_label: str
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
