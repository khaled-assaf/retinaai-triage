from fastapi import APIRouter

from ..schemas import Dashboard
from ..storage import stats

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=Dashboard)
def dashboard():
    """Numbers for the follow-up dashboard: totals, triage mix, follow-up statuses,
    attendance rate, per-country breakdown and screenings per month."""
    return stats.dashboard()
