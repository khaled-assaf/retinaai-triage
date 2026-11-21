"""Patients and their screening history (simulated data in the demo)."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..reports.i18n import LANGUAGES
from ..schemas import Patient, PatientCreate, PatientDetail, PatientIn, PatientSummary
from ..storage import db, followups, patients

router = APIRouter(tags=["patients"])


def _check_language(lang: Optional[str]) -> None:
    if lang is not None and lang not in LANGUAGES:
        raise HTTPException(400, f"Unsupported language '{lang}'. Use one of: {', '.join(LANGUAGES)}")


@router.get("/patients", response_model=list[PatientSummary])
def list_patients(
    country: Optional[str] = Query(None, description="ISO country code, e.g. RO"),
    q: Optional[str] = Query(None, description="Search patient ID or name"),
):
    return patients.list_patients(country, q)


@router.post("/patients", response_model=Patient, status_code=201)
def create_patient(body: PatientCreate):
    if patients.get_patient(body.patient_ref):
        raise HTTPException(409, "Patient already exists")
    _check_language(body.language)
    data = body.model_dump(exclude={"patient_ref"})
    if data.get("country"):
        data["country"] = data["country"].upper()
    return patients.upsert_patient(body.patient_ref, **data)


@router.get("/patients/{patient_ref}", response_model=PatientDetail)
def get_patient(patient_ref: str):
    """Patient + all their screenings (newest first) + all their follow-ups: the longitudinal record."""
    patient = patients.get_patient(patient_ref)
    if not patient:
        raise HTTPException(404, "Patient not found")
    return {
        "patient": patient,
        "cases": db.list_patient_cases(patient_ref),
        "followups": followups.list_followups(patient_ref=patient_ref),
    }


@router.patch("/patients/{patient_ref}", response_model=Patient)
def update_patient(patient_ref: str, body: PatientIn):
    if not patients.get_patient(patient_ref):
        raise HTTPException(404, "Patient not found")
    _check_language(body.language)
    data = body.model_dump(exclude_none=True)
    if data.get("country"):
        data["country"] = data["country"].upper()
    return patients.upsert_patient(patient_ref, **data)
