from fastapi import APIRouter, Request

from ..ml import inference
from ..schemas import Health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
def health(request: Request):
    model = getattr(request.app.state, "model", None)
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "mock": inference.is_mock(model),
        "model_version": inference.model_version(model),
    }
