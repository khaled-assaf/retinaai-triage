from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ..config import get_settings
from ..schemas import Case
from ..services.pipeline import InvalidImageError, analyze_image

router = APIRouter(tags=["analyze"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "application/octet-stream", ""}


def read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    data = upload.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"Image too large. Maximum size is {get_settings().max_upload_mb:g} MB.")
    if not data:
        raise HTTPException(400, "Empty file.")
    return data


def parse_symptoms(raw: Optional[str]) -> Optional[list[str]]:
    """Form/query value -> None (not collected) | [] (asked, none) | [codes]."""
    if raw is None:
        return None
    raw = raw.strip()
    if raw.lower() in ("", "none"):
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def run_pipeline(request: Request, data: bytes, patient_ref: Optional[str],
                 eye: str = "unknown", symptoms: Optional[str] = None) -> dict:
    settings = get_settings()
    try:
        return analyze_image(data, patient_ref, request.app.state.model, settings.confidence_threshold,
                             eye=eye, symptoms=parse_symptoms(symptoms))
    except InvalidImageError as e:
        raise HTTPException(400, str(e))


EYE_HELP = "right | left | unknown (default: not recorded)"
SYMPTOMS_HELP = ("Urgent eye symptoms. Omit = not collected; 'none' = asked, none reported; or "
                 "comma-separated codes: sudden_vision_loss, curtain_shadow, flashes_floaters, other_acute. "
                 "Any code overrides the AI result (emergency eye assessment).")


# Plain `def` on purpose: inference is CPU-bound, so FastAPI runs this in a
# threadpool instead of blocking the event loop.
@router.post("/analyze", response_model=Case)
def analyze(
    request: Request,
    image: UploadFile = File(..., description="Fundus photo, JPG or PNG"),
    patient_ref: Optional[str] = Form(None, max_length=100),
    eye: str = Form("unknown", description=EYE_HELP),
    symptoms: Optional[str] = Form(None, description=SYMPTOMS_HELP),
):
    if (image.content_type or "") not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, "Unsupported file type. Upload a JPG or PNG image.")
    data = read_limited(image, get_settings().max_upload_bytes)
    return run_pipeline(request, data, patient_ref, eye, symptoms)
