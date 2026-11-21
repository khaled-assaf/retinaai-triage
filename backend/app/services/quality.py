"""Deterministic image-quality checks for fundus photos (OpenCV, no ML).

Every image is first resized to a fixed width so the scores are comparable across
camera resolutions. Three checks:
  - blur:     variance of the Laplacian inside the retina, mapped to a 0..1 score
  - exposure: mean brightness inside the retina mask
  - framing:  is there a roughly circular fundus region covering enough of the frame?
"""
from __future__ import annotations

import math

import cv2
import numpy as np

# ------------------------------------------------------------------ thresholds
# TODO(team): tune all of these on real APTOS 2019 images (gradable vs ungradable).
# The current values were set on our synthetic placeholder samples.
RESIZE_WIDTH = 512

# Pixels brighter than this (grayscale) count as retina, darker = black background.
MASK_THRESHOLD = 15

# Blur: Laplacian variance mapped on a log scale between these two values.
BLUR_VAR_LOW = 2.0       # at or below -> score 0.0
BLUR_VAR_HIGH = 150.0    # at or above -> score 1.0
MIN_BLUR_SCORE = 0.35    # below -> "blurry"

# Exposure: mean grayscale brightness (0-255) inside the retina mask.
MIN_BRIGHTNESS = 30
MAX_BRIGHTNESS = 200

# Framing.
MIN_RETINA_COVERAGE = 0.25  # retina area / image area
MIN_CIRCLE_FILL = 0.65      # retina area / area of its min enclosing circle
                            # (APTOS crops cut the top/bottom of the circle; ~0.8 is normal)

# Penalty applied to the overall score for each failed exposure/framing check.
FAILED_CHECK_PENALTY = 0.5
# ------------------------------------------------------------------------------

_REASONS = {
    "blur": "Image is blurry",
    "underexposed": "Image is too dark (underexposed)",
    "overexposed": "Image is too bright (overexposed)",
    "too_small": "Retina covers too little of the frame",
    "not_found": "No circular retina region found",
}


def _resize(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    if w == RESIZE_WIDTH:
        return img
    new_h = max(1, round(h * RESIZE_WIDTH / w))
    interp = cv2.INTER_AREA if w > RESIZE_WIDTH else cv2.INTER_LINEAR
    return cv2.resize(img, (RESIZE_WIDTH, new_h), interpolation=interp)


def retina_mask(gray: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Return (mask, coverage, circle_fill) for the largest bright region."""
    _, mask = cv2.threshold(gray, MASK_THRESHOLD, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    clean = np.zeros_like(mask)
    if not contours:
        return clean, 0.0, 0.0
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    cv2.drawContours(clean, [largest], -1, 255, thickness=cv2.FILLED)
    (_, _), radius = cv2.minEnclosingCircle(largest)
    circle_area = math.pi * radius * radius
    coverage = area / float(gray.shape[0] * gray.shape[1])
    circle_fill = area / circle_area if circle_area > 0 else 0.0
    return clean, coverage, circle_fill


def blur_score(gray: np.ndarray, mask: np.ndarray) -> float:
    """0..1 sharpness from the Laplacian variance inside the (eroded) retina mask.

    The mask is eroded so the strong retina/background boundary doesn't make a
    blurry image look sharp.
    """
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    inner = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)))
    values = lap[inner > 0] if np.count_nonzero(inner) > 100 else lap.ravel()
    var = float(values.var())
    lo, hi = math.log(BLUR_VAR_LOW), math.log(BLUR_VAR_HIGH)
    score = (math.log(max(var, 1e-6)) - lo) / (hi - lo)
    return float(min(1.0, max(0.0, score)))


def assess_quality(img_rgb: np.ndarray) -> dict:
    """Run all checks. Returns a dict matching schemas.Quality."""
    img = _resize(img_rgb)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    mask, coverage, circle_fill = retina_mask(gray)

    if coverage == 0.0 or circle_fill < MIN_CIRCLE_FILL:
        framing = "not_found"
    elif coverage < MIN_RETINA_COVERAGE:
        framing = "too_small"
    else:
        framing = "ok"

    region = gray[mask > 0] if np.count_nonzero(mask) else gray.ravel()
    brightness = float(region.mean())
    if brightness < MIN_BRIGHTNESS:
        exposure = "underexposed"
    elif brightness > MAX_BRIGHTNESS:
        exposure = "overexposed"
    else:
        exposure = "ok"

    blur = round(blur_score(gray, mask), 3)

    failures = []
    if blur < MIN_BLUR_SCORE:
        failures.append(_REASONS["blur"])
    if exposure != "ok":
        failures.append(_REASONS[exposure])
    if framing != "ok":
        failures.append(_REASONS[framing])

    score = blur
    for check in (exposure, framing):
        if check != "ok":
            score *= FAILED_CHECK_PENALTY

    return {
        "passed": not failures,
        "score": round(score, 3),
        "reason": "OK" if not failures else "; ".join(failures),
        "checks": {"blur": blur, "exposure": exposure, "framing": framing},
    }
