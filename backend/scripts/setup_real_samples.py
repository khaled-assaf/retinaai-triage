"""Build backend/samples_real/ (LOCAL ONLY, gitignored) from the AI teammate's demo_images.zip.

The 5 images are APTOS 2019 validation images, one per grade, hand-picked as correct and
confident (ai/BACKEND_HANDOFF.md, G18 / C10 Q4). The licence for PUBLIC display is not yet
confirmed (G17), so they must never be committed while the repo is public.

    cd backend
    python scripts/setup_real_samples.py                 # default: ../ai/demo_images.zip
    # then in backend/.env:  SAMPLES_DIR=samples_real   (and USE_MOCK_MODEL=false)
    # delete storage_data/ and restart so the demo data is rebuilt from these images
"""
from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

import cv2

BACKEND = Path(__file__).resolve().parent.parent
OUT = BACKEND / "samples_real"
CREDIT = "APTOS 2019 Blindness Detection (Aravind Eye Hospital), validation image"

# APTOS id -> (sample id, label, grade, note)
IMAGES = {
    "13c191b59ed0": ("normal", "No DR", 0, "no visible diabetic retinopathy"),
    "3ee17aa12e46": ("mild", "Mild NPDR", 1, "mild non-proliferative DR"),
    "bfd5c0e55420": ("moderate", "Moderate NPDR", 2, "moderate non-proliferative DR"),
    "dbfd238b3468": ("severe", "Severe NPDR", 3, "severe non-proliferative DR"),
    "27e2be850a99": ("proliferative", "Proliferative DR", 4, "proliferative DR"),
}


def main(zip_path: Path) -> None:
    OUT.mkdir(exist_ok=True)
    manifest = []
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        for aptos_id, (sid, label, grade, note) in IMAGES.items():
            member = f"{aptos_id}.png"
            if member not in names:
                raise SystemExit(f"{member} not found in {zip_path}")
            # Extract only the expected files, by name, never trusting paths in the archive.
            with z.open(member) as src, open(OUT / f"{sid}.png", "wb") as dst:
                shutil.copyfileobj(src, dst)
            manifest.append({
                "id": sid,
                "label": f"{label} (APTOS)",
                "file": f"{sid}.png",
                "expected_grade": grade,
                "description": f"{CREDIT} {aptos_id}: {note}. Hand-picked correct example, not a measure of accuracy.",
            })

    # An ungradable example, made by blurring the grade-0 image: exercises the "retake" path.
    img = cv2.imread(str(OUT / "normal.png"))
    cv2.imwrite(str(OUT / "blurry.jpg"), cv2.GaussianBlur(img, (0, 0), 12), [cv2.IMWRITE_JPEG_QUALITY, 90])
    manifest.append({
        "id": "blurry",
        "label": "Blurry (ungradable)",
        "file": "blurry.jpg",
        "expected_grade": None,
        "description": "Artificially blurred copy of the grade-0 APTOS image; should fail the quality check.",
    })
    (OUT / "samples.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {len(manifest)} samples to {OUT} (gitignored)")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else BACKEND.parent / "ai" / "demo_images.zip")
