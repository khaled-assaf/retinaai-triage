"""RetinaAI Nexus API. Run from backend/:  uvicorn app.main:app --reload"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import seed
from .config import get_settings
from .ml import inference
from .routers import analyze, cases, dashboard, followups, health, patients, reports, samples
from .storage import db

log = logging.getLogger("retinaai")


def load_model_once(settings):
    if settings.use_mock_model:
        log.info("USE_MOCK_MODEL=true -> using mock model")
        return inference.load_mock_model()
    try:
        model = inference.load_model(settings.model_weights_path)
        log.info("Loaded real model from %s", settings.model_weights_path)
        return model
    except Exceptiondisclaimer:
        log.exception("Failed to load real model; FALLING BACK TO MOCK (see /api/health)")
        return inference.load_mock_model()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.model = load_model_once(settings)
    db.init_db()
    if settings.seed_demo_cases and db.count_cases() == 0:
        files = {s["id"]: settings.samples_dir / s["file"] for s in samples.load_manifest()}
        n = seed.seed(app.state.model, settings, {k: v for k, v in files.items() if v.is_file()})
        log.info("Seeded %d simulated screenings", n)
    yield


settings = get_settings()
app = FastAPI(
    title="RetinaAI Nexus API",
    description=(
        "From detection to action: AI retinal screening, smart quality check, European Retina "
        "Passport (multilingual PDF), smart triage and follow-up tracking. "
        "Research prototype with **simulated data**. **Not for clinical diagnosis.**"
    ),
    version="0.2.0",
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


for r in (analyze.router, cases.router, reports.router, patients.router, followups.router,
          dashboard.router, samples.router, health.router):
    app.include_router(r, prefix="/api")


@app.get("/", include_in_schema=False)
def root():
    return {"name": "RetinaAI Nexus API", "docs": "/docs", "health": "/api/health"}
