"""Runtime settings, read from environment variables (and backend/.env if present).

Keep this dependency-free: a tiny .env parser instead of python-dotenv.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines into os.environ without overriding real env vars."""
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    if not value:
        return default
    p = Path(value)
    return p if p.is_absolute() else (BACKEND_DIR / p)


@dataclass
class Settings:
    use_mock_model: bool
    confidence_threshold: float
    max_upload_mb: float
    storage_dir: Path
    db_path: Path
    model_weights_path: Path
    samples_dir: Path
    seed_demo_cases: bool
    cors_origins: list[str]
    public_base_url: str
    share_days_valid: int

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)


@lru_cache
def get_settings() -> Settings:
    _load_dotenv(BACKEND_DIR / ".env")
    storage_dir = _path("STORAGE_DIR", BACKEND_DIR / "storage_data")
    return Settings(
        use_mock_model=_bool("USE_MOCK_MODEL", True),
        confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.6")),
        max_upload_mb=float(os.getenv("MAX_UPLOAD_MB", "10")),
        storage_dir=storage_dir,
        db_path=_path("DB_PATH", storage_dir / "retinaai.db"),
        model_weights_path=_path("MODEL_WEIGHTS_PATH", BACKEND_DIR / "models" / "model.pth"),
        samples_dir=_path("SAMPLES_DIR", BACKEND_DIR / "samples"),
        seed_demo_cases=_bool("SEED_DEMO_CASES", True),
        cors_origins=[
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
            ).split(",")
            if o.strip()
        ],
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
        share_days_valid=int(os.getenv("SHARE_DAYS_VALID", "30")),
    )
