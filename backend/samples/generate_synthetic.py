"""Generate 5 SYNTHETIC placeholder fundus images + samples.json.

These are cartoon drawings, not real retinas. MEDICAL TEAMMATE: replace them with
real, license-compatible images (e.g. a few APTOS 2019 examples) and update
samples.json. Don't commit large datasets; a handful of demo images is fine.

For each image we try RNG seeds until the MOCK model's output fits the label
(e.g. "Severe" gets a confident grade 3-4), so the demo queue shows every triage
level. This only matters while USE_MOCK_MODEL=true.

Run from backend/:   python samples/generate_synthetic.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.ml.inference import _mock_predict  # noqa: E402
from app.services.quality import assess_quality  # noqa: E402
from app.services.triage import triage_case  # noqa: E402

OUT = Path(__file__).resolve().parent
SIZE = 768


def draw_fundus(rng: np.random.Generator, lesions: int) -> np.ndarray:
    """Return an RGB fundus-like image. `lesions` 0..3 controls DR severity."""
    h = w = SIZE
    c = (w // 2, h // 2)
    r = int(SIZE * 0.46)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = np.sqrt((xx - c[0]) ** 2 + (yy - c[1]) ** 2) / r

    # Orange-red background with vignetting and fine texture.
    base = np.array([200, 85, 40], np.float32) * rng.uniform(0.9, 1.1)
    shade = np.clip(1.05 - 0.45 * dist**2, 0, 1)[..., None]
    texture = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 1.2)[..., None]
    img = base * shade + texture * 10

    # Optic disc and macula.
    disc = (int(c[0] + r * rng.uniform(0.35, 0.5)), int(c[1] + r * rng.uniform(-0.1, 0.1)))
    disc_mask = np.exp(-((xx - disc[0]) ** 2 + (yy - disc[1]) ** 2) / (2 * (r * 0.09) ** 2))[..., None]
    img = img * (1 - disc_mask) + np.array([250, 225, 160]) * disc_mask
    mac = (int(c[0] - r * 0.25), c[1])
    mac_mask = np.exp(-((xx - mac[0]) ** 2 + (yy - mac[1]) ** 2) / (2 * (r * 0.12) ** 2))[..., None]
    img = img * (1 - 0.35 * mac_mask)
    img = np.clip(img, 0, 255).astype(np.uint8)

    # Vessels: random walks out of the optic disc.
    for _ in range(10):
        x, y = float(disc[0]), float(disc[1])
        angle = rng.uniform(0, 2 * np.pi)
        width = int(rng.integers(3, 7))
        for _ in range(60):
            angle += rng.normal(0, 0.18)
            nx, ny = x + 9 * np.cos(angle), y + 9 * np.sin(angle)
            cv2.line(img, (int(x), int(y)), (int(nx), int(ny)), (120, 20, 15), width, cv2.LINE_AA)
            x, y = nx, ny
            if rng.random() < 0.04 and width > 2:
                width -= 1

    # DR lesions.
    def spots(n, radius, color):
        for _ in range(n):
            a, d = rng.uniform(0, 2 * np.pi), r * np.sqrt(rng.uniform(0, 0.75))
            p = (int(c[0] + d * np.cos(a)), int(c[1] + d * np.sin(a)))
            cv2.circle(img, p, int(rng.integers(*radius)), color, -1, cv2.LINE_AA)

    if lesions >= 1:
        spots(12 * lesions, (2, 4), (110, 10, 10))          # microaneurysms
    if lesions >= 2:
        spots(8 * lesions, (3, 7), (245, 220, 90))          # hard exudates
        spots(5 * lesions, (6, 12), (120, 15, 10))          # blot haemorrhages
    if lesions >= 3:
        spots(10, (8, 16), (235, 230, 200))                 # cotton-wool spots

    # Black background outside the circle.
    img[dist > 1.0] = 0
    return img


def jpeg_roundtrip(img_rgb: np.ndarray) -> tuple[bytes, np.ndarray]:
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
    assert ok
    data = buf.tobytes()
    decoded = cv2.cvtColor(cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    return data, decoded


SAMPLES = [
    # id, label, lesions, blur, expected_grade, target triage level, description
    ("normal", "Normal", 0, False, 0, "routine", "No visible lesions"),
    ("mild", "Mild NPDR", 1, False, 1, "review", "A few microaneurysms; mock model is unsure -> review"),
    ("moderate", "Moderate NPDR", 2, False, 2, "referable", "Microaneurysms, exudates, haemorrhages"),
    ("severe", "Severe NPDR", 3, False, 3, "urgent", "Extensive haemorrhages and cotton-wool spots"),
    ("blurry", "Blurry (ungradable)", 1, True, None, "retake", "Out of focus; should fail the quality check"),
]


def main() -> None:
    manifest = []
    for sid, label, lesions, blur, expected, target, desc in SAMPLES:
        for seed in range(10_000):
            rng = np.random.default_rng(seed)
            img = draw_fundus(rng, lesions)
            if blur:
                img = cv2.GaussianBlur(img, (0, 0), 7)
            data, decoded = jpeg_roundtrip(img)
            q = assess_quality(decoded)
            pred = _mock_predict(decoded) if q["passed"] else None
            level = triage_case(q["passed"], pred)["level"]
            if level != target:
                continue
            if pred and target != "review" and pred["grade"] != expected and not (expected == 3 and pred["grade"] == 4):
                continue
            if pred and target == "review" and pred["grade"] != expected:
                continue
            break
        else:
            raise SystemExit(f"no seed found for {sid}")
        fname = f"{sid}.jpg"
        (OUT / fname).write_bytes(data)
        print(f"{fname:13s} seed={seed:<4d} quality={q['checks']} level={level} pred={pred}")
        manifest.append({
            "id": sid,
            "label": f"{label} (synthetic)",
            "file": fname,
            "expected_grade": expected,
            "description": f"SYNTHETIC placeholder. {desc}.",
        })
    (OUT / "samples.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("wrote samples.json")


if __name__ == "__main__":
    main()
