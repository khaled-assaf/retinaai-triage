"""Follow-up tracking: referrals, rescreens, missed appointments, reminders."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..reports.i18n import normalize_lang, reminder_text
from ..schemas import Followup, FollowupStatus, FollowupType, FollowupUpdate, ReminderResult
from ..storage import followups

router = APIRouter(tags=["follow-up"])


@router.get("/followups", response_model=list[Followup])
def list_followups(
    status: Optional[FollowupStatus] = None,
    type: Optional[FollowupType] = None,
    patient_ref: Optional[str] = None,
    overdue: Optional[bool] = Query(None, description="true = only pending items past their due date"),
    open: bool = Query(False, description="true = only pending, scheduled or missed"),
    limit: int = Query(500, ge=1, le=2000),
):
    """Sorted by what needs attention: missed, then overdue, then upcoming by due date, then closed.
    Scheduled appointments more than 24h in the past are automatically marked missed."""
    return followups.list_followups(status, type, patient_ref, overdue, open, limit)


@router.get("/followups/{followup_id}", response_model=Followup)
def get_followup(followup_id: str):
    f = followups.get_followup(followup_id)
    if not f:
        raise HTTPException(404, "Follow-up not found")
    return f


@router.patch("/followups/{followup_id}", response_model=Followup)
def update_followup(followup_id: str, body: FollowupUpdate):
    """Book an appointment (`appointment_at`), or mark attended / missed / cancelled."""
    if body.appointment_at:
        try:
            datetime.fromisoformat(body.appointment_at.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(400, "appointment_at must be an ISO-8601 date-time")
    f = followups.update_followup(followup_id, status=body.status, appointment_at=body.appointment_at, note=body.note)
    if not f:
        raise HTTPException(404, "Follow-up not found")
    return f


@router.post("/followups/{followup_id}/remind", response_model=ReminderResult)
def remind(followup_id: str):
    """SIMULATED reminder: nothing is sent. Returns the SMS text in the patient's language."""
    f = followups.get_followup(followup_id)
    if not f:
        raise HTTPException(404, "Follow-up not found")
    if f["status"] in ("attended", "cancelled"):
        raise HTTPException(400, f"Follow-up is already {f['status']}")
    f = followups.record_reminder(followup_id)
    lang = normalize_lang(f["language"])
    return {
        "followup": f,
        "language": lang,
        "message": reminder_text(lang, f["patient_name"], f["type"], f["due_date"]),
    }
