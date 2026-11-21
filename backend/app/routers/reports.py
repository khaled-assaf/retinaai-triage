"""European Retina Passport: multilingual PDF reports + shareable links."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response

from ..config import get_settings
from ..reports.i18n import LANGUAGES, normalize_lang
from ..reports.pdf import build_passport_pdf
from ..schemas import Language, ShareLink
from ..services import pipeline
from ..storage import db, patients, shares

router = APIRouter(tags=["passport"])

LangQuery = Query(None, description="Report language (en, ro, de, fr, es, it). Default: the patient's preferred language")


def _render(case_id: str, lang: Optional[str], share: Optional[dict] = None) -> tuple[bytes, str]:
    case = pipeline.full_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    patient = patients.get_patient(case["patient_ref"]) if case.get("patient_ref") else None
    language = normalize_lang(lang or (patient or {}).get("language"))
    history = db.list_patient_cases(case["patient_ref"]) if case.get("patient_ref") else []
    image = db.get_file(case_id, "image")
    heatmap = db.get_file(case_id, "heatmap")
    share_url = None
    if share:
        share_url = f"{get_settings().public_base_url}/api/passport/{share['token']}"
    pdf = build_passport_pdf(
        case=case,
        patient=patient,
        history=history,
        image_path=image[0] if image else None,
        heatmap_path=heatmap[0] if heatmap else None,
        lang=language,
        share_url=share_url,
        share_expires_at=share["expires_at"] if share else None,
    )
    return pdf, language


def _pdf_response(pdf: bytes, filename: str, download: bool) -> Response:
    disposition = "attachment" if download else "inline"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'{disposition}; filename="{filename}"'})


@router.get("/languages", response_model=list[Language])
def languages():
    return [{"code": c, "name": n} for c, n in LANGUAGES.items()]


@router.get("/cases/{case_id}/report.pdf", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})
def case_report(case_id: str, lang: Optional[str] = LangQuery, download: bool = False):
    """The case's European Retina Passport as PDF (opens inline; `?download=true` to save)."""
    pdf, language = _render(case_id, lang)
    return _pdf_response(pdf, f"retina-passport-{case_id}-{language}.pdf", download)


@router.post("/cases/{case_id}/share", response_model=ShareLink)
def share_case(case_id: str, lang: Optional[str] = LangQuery):
    """Create a public, expiring link to this case's passport (for the patient or another clinic)."""
    case = db.get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    patient = patients.get_patient(case["patient_ref"]) if case.get("patient_ref") else None
    language = normalize_lang(lang or (patient or {}).get("language"))
    settings = get_settings()
    share = shares.create_share(case_id, language, settings.share_days_valid)
    return {**share, "passport_url": f"{settings.public_base_url}/api/passport/{share['token']}"}


@router.get("/passport/{token}", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})
def passport_by_token(token: str, lang: Optional[str] = Query(None, description="Override the shared language")):
    """Public passport link (no login): the PDF, including a QR code pointing back to this link."""
    share = shares.get_valid_share(token)
    if not share:
        raise HTTPException(404, "Passport link not found or expired")
    pdf, language = _render(share["case_id"], lang or share["language"], share=share)
    return _pdf_response(pdf, f"retina-passport-{share['case_id']}-{language}.pdf", False)
