"""decode -> quality -> (if passed) predict + gradcam -> triage -> save."""
from __future__ import annotations

import time
from typing import Any, Optional

import cv2
import numpy as np

from ..ml import inference
from ..storage import db
from .quality import assess_quality
from .triage import triage_case

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
) -> dict:
    """Run the whole pipeline on raw upload bytes and persist the case."""
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

    return db.create_case(
        patient_ref=patient_ref or None,
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
    )
