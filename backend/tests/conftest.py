"""Point the app at a throwaway DB/storage dir BEFORE the app is imported."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

_TMP = tempfile.mkdtemp(prefix="retinaai-test-")
os.environ["STORAGE_DIR"] = _TMP
os.environ["DB_PATH"] = str(Path(_TMP) / "test.db")
os.environ["USE_MOCK_MODEL"] = "true"
os.environ["SEED_DEMO_CASES"] = "true"
# Tests must not depend on anyone's local backend/.env (real model, real samples, ...).
os.environ["RETINAAI_IGNORE_DOTENV"] = "1"
os.environ["SAMPLES_DIR"] = str(Path(__file__).resolve().parent.parent / "samples")

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

SAMPLES = BACKEND / "samples"


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:  # runs lifespan: model load, DB init, seeding
        yield c
