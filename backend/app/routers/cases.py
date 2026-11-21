from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ..schemas import Case, CaseSummary, ReviewUpdate
from ..storage import db

router = APIRouter(tags=["cases"])


@router.get("/queue", response_model=list[CaseSummary])
def queue(
    status: Optional[Literal["pending", "reviewed"]] = Query(None, description="Filter by review status"),
    limit: int = Query(200, ge=1, le=1000),
):
    """Case summaries sorted by urgency (urgent > review > referable > retake > routine), then newest first."""
    return db.list_queue(review_status=status, limit=limit)


@router.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: str):
    case = db.get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


@router.patch("/cases/{case_id}", response_model=Case)
def review_case(case_id: str, body: ReviewUpdate):
    case = db.update_review(case_id, body.status, body.clinician_grade, body.note)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


def _serve(case_id: str, kind: str) -> FileResponse:
    found = db.get_file(case_id, kind)
    if not found:
        raise HTTPException(404, f"{kind.capitalize()} not found")
    path, mime = found
    return FileResponse(path, media_type=mime, headers={"Cache-Control": "public, max-age=3600"})


@router.get("/cases/{case_id}/image", response_class=FileResponse)
def case_image(case_id: str):
    return _serve(case_id, "image")


@router.get("/cases/{case_id}/heatmap", response_class=FileResponse)
def case_heatmap(case_id: str):
    return _serve(case_id, "heatmap")


@router.get("/cases/{case_id}/thumbnail", response_class=FileResponse)
def case_thumbnail(case_id: str):
    return _serve(case_id, "thumbnail")
