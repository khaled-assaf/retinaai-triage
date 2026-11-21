"""decode -> quality -> (if passed) predict + gradcam -> triage -> save."""
from __future__ import annotations

import time
from typing import Any, Optional

import cv2
import numpy as np

from ..ml import inference
from ..storage import db, followups, patients
from .quality import assess_quality
from .triage import FOLLOW_UP_RULES, triage_case, triage_from_clinician

THUMBNAIL_WIDTH = 256

# magic bytes -> (extension, mime type)
_SIGNATURES = {
    b"\xff\xd8\xff": ("jpg", "image/jpeg"),
    b"\x89PNG\r\n\x1a\n": ("png", "image/png"),
}


class InvalidImageError(ValueError):
    """Raised for unsupported or undecodable uploads (-> HTTP 400)."""


def sniff_type(data: bytes) -> tuple[str, str]:
    for magic, info in _SIGNATURES.items():
        if data.startswith(magic):
            return info
    raise InvalidImageError("Unsupported file type. Upload a JPG or PNG image.")


def decode_image(data: bytes) -> np.ndarray:
    """Bytes -> RGB uint8 array (H, W, 3)."""
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        raise InvalidImageError("Could not decode image. The file may be corrupted.")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def make_thumbnail(img_rgb: np.ndarray) -> bytes:
    h, w = img_rgb.shape[:2]
    tw = min(THUMBNAIL_WIDTH, w)
    thumb = cv2.resize(img_rgb, (tw, max(1, round(h * tw / w))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(thumb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise RuntimeError("Thumbnail encoding failed")
    return buf.tobytes()


def _validate_prediction(raw: dict) -> dict:
    """Normalise the model output and add label/confidence."""
    probs = [float(p) for p in raw["probabilities"]]
    if len(probs) != 5:
        raise ValueError(f"predict() must return 5 probabilities, got {len(probs)}")
    grade = int(raw["grade"])
    if not 0 <= grade <= 4:
        raise ValueError(f"predict() returned invalid grade {grade}")
    return {
        "grade": grade,
        "label": inference.GRADE_LABELS[grade],
        "confidence": round(probs[grade], 4),
        "probabilities": [round(p, 4) for p in probs],
    }


def analyze_image(
    data: bytes,
    patient_ref: Optional[str],
    model: Any,
    confidence_threshold: float,
    created_at: Optional[str] = None,
) -> dict:
    """Run the whole pipeline on raw upload bytes and persist the case.

    Also: makes sure the patient exists, plans the case's follow-up from the
    triage level, and closes the patient's earlier open rescreen/retake.
    `created_at` is only for seeding simulated history.
    """
    t0 = time.perf_counter()
    ext, mime = sniff_type(data)
    img_rgb = decode_image(data)

    quality = assess_quality(img_rgb)
    prediction: Optional[dict] = None
    heatmap: Optional[bytes] = None
    if quality["passed"]:
        prediction = _validate_prediction(inference.predict(model, img_rgb))
        heatmap = inference.gradcam(model, img_rgb)

    triage = triage_case(quality["passed"], prediction, confidence_threshold)
    thumbnail = make_thumbnail(img_rgb)
    processing_ms = int((time.perf_counter() - t0) * 1000)

    patient_ref = patient_ref or None
    patients.ensure_patient(patient_ref)
    case = db.create_case(
        patient_ref=patient_ref,
        quality=quality,
        prediction=prediction,
        triage=triage,
        model_version=inference.model_version(model),
        processing_ms=processing_ms,
        image_bytes=data,
        image_ext=ext,
        image_mime=mime,
        thumbnail_jpg=thumbnail,
        heatmap_png=heatmap,
        created_at=created_at,
    )
    if patient_ref:
        followups.resolve_by_new_case(patient_ref, case["case_id"], at=case["created_at"])
    rule = FOLLOW_UP_RULES[triage["level"]]
    followups.create_followup(
        case["case_id"],
        patient_ref,
        rule["type"],
        followups.due_date_from(case["created_at"], rule["due_days"]),
        created_at=case["created_at"],
    )
    return full_case(case["case_id"])


def full_case(case_id: str) -> Optional[dict]:
    """Case + its follow-up, as returned by the API."""
    case = db.get_case(case_id)
    if case is None:
        return None
    case["followup"] = followups.get_case_followup(case_id)
    return case


def review_case(case_id: str, status: str, clinician_grade: Optional[int], note: Optional[str]) -> Optional[dict]:
    """Save a clinician review.

    - Reviewing closes the case's open "clinician_review" follow-up (marked attended).
    - A clinician grade overrides the AI triage (triage.source = "clinician") and plans
      the follow-up that grade calls for (or re-plans a still-pending one).
    """
    case = db.update_review(case_id, status, clinician_grade, note)
    if case is None:
        return None
    if status != "reviewed":
        return full_case(case_id)

    current = followups.get_case_followup(case_id)
    if current and current["type"] == "clinician_review" and current["status"] in followups.OPEN_STATUSES:
        followups.update_followup(current["followup_id"], status="attended", note="Reviewed by clinician")
        current = None  # the review step is done; plan the next one below
    if clinician_grade is not None:
        triage = triage_from_clinician(clinician_grade)
        db.update_triage(case_id, triage)
        rule = FOLLOW_UP_RULES[triage["level"]]
        due = followups.due_date_from(db.now_iso(), rule["due_days"])
        if current is None:
            followups.create_followup(case_id, case["patient_ref"], rule["type"], due)
        elif current["status"] == "pending":
            followups.replace_case_followup(case_id, rule["type"], due)
    return full_case(case_id)
