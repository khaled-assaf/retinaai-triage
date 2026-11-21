import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from ..config import get_settings
from ..schemas import Case, Sample
from .analyze import run_pipeline

router = APIRouter(tags=["samples"])

_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def load_manifest() -> list[dict]:
    """Read samples/samples.json. Each entry: id, label, file, expected_grade, description."""
    path = get_settings().samples_dir / "samples.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text())


def sample_path(sample_id: str) -> Path:
    for s in load_manifest():
        if s["id"] == sample_id:
            path = get_settings().samples_dir / s["file"]
            if path.is_file():
                return path
    raise HTTPException(404, "Sample not found")


@router.get("/samples", response_model=list[Sample])
def list_samples():
    return [
        {
            "id": s["id"],
            "label": s["label"],
            "image_url": f"/api/samples/{s['id']}/image",
            "expected_grade": s.get("expected_grade"),
            "description": s.get("description"),
        }
        for s in load_manifest()
    ]


@router.get("/samples/{sample_id}/image", response_class=FileResponse)
def sample_image(sample_id: str):
    path = sample_path(sample_id)
    return FileResponse(path, media_type=_MIME.get(path.suffix.lower(), "application/octet-stream"))


@router.post("/samples/{sample_id}/analyze", response_model=Case)
def analyze_sample(
    request: Request,
    sample_id: str,
    patient_ref: Optional[str] = Query(None, max_length=100),
):
    """Run the full pipeline on a demo image (one click from the sample tray)."""
    data = sample_path(sample_id).read_bytes()
    return run_pipeline(request, data, patient_ref or f"SAMPLE-{sample_id}")
