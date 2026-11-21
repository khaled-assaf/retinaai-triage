"""RetinaAI Triage API. Run from backend/:  uvicorn app.main:app --reload"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import get_settings
from .ml import inference
from .routers import analyze, cases, health, samples
from .services.pipeline import analyze_image
from .storage import db

log = logging.getLogger("retinaai")

# (sample id, patient_ref) pairs used to fill an empty DB so the queue isn't blank.
DEMO_SEED = [
    ("severe", "DEMO-001"),
    ("normal", "DEMO-002"),
    ("moderate", "DEMO-003"),
    ("blurry", "DEMO-004"),
    ("mild", "DEMO-005"),
    ("normal", "DEMO-006"),
    ("severe", "DEMO-007"),
    ("moderate", "DEMO-008"),
]


def load_model_once(settings):
    if settings.use_mock_model:
        log.info("USE_MOCK_MODEL=true -> using mock model")
        return inference.load_mock_model()
    try:
        model = inference.load_model(settings.model_weights_path)
        log.info("Loaded real model from %s", settings.model_weights_path)
        return model
    except Exception:
        log.exception("Failed to load real model; FALLING BACK TO MOCK (see /api/health)")
        return inference.load_mock_model()


def seed_demo_cases(model, settings) -> int:
    manifest = {s["id"]: s for s in samples.load_manifest()}
    created = 0
    for sample_id, patient_ref in DEMO_SEED:
        entry = manifest.get(sample_id)
        path = settings.samples_dir / entry["file"] if entry else None
        if not path or not path.is_file():
            continue
        case = analyze_image(path.read_bytes(), patient_ref, model, settings.confidence_threshold)
        created += 1
        if patient_ref == "DEMO-006":  # show one already-reviewed case
            db.update_review(case["case_id"], "reviewed", 0, "Agree with AI. Rescreen in 12 months.")
    return created


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.model = load_model_once(settings)
    db.init_db()
    if settings.seed_demo_cases and db.count_cases() == 0:
        n = seed_demo_cases(app.state.model, settings)
        log.info("Seeded %d demo cases", n)
    yield


settings = get_settings()
app = FastAPI(
    title="RetinaAI Triage API",
    description="Research prototype for diabetic retinopathy screening. **Not for clinical diagnosis.**",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Consistent {"detail": "<string>"} error bodies.
@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    return JSONResponse({"detail": str(exc.detail)}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    parts = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x not in ("body", "query", "path"))
        parts.append(f"{loc}: {err.get('msg')}" if loc else err.get("msg", "Invalid request"))
    return JSONResponse({"detail": "; ".join(parts) or "Invalid request"}, status_code=422)


@app.exception_handler(Exception)
async def unhandled_error(_: Request, exc: Exception):
    log.exception("Unhandled error", exc_info=exc)
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


for r in (analyze.router, cases.router, samples.router, health.router):
    app.include_router(r, prefix="/api")


@app.get("/", include_in_schema=False)
def root():
    return {"name": "RetinaAI Triage API", "docs": "/docs", "health": "/api/health"}
