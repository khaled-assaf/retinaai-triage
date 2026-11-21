"""Real-model plumbing, tested with a RANDOM-weight stand-in checkpoint in the exact
format of the AI teammate's model_inference.pt. Checks the integration, not accuracy.
Skipped automatically when torch/timm aren't installed (requirements-ml.txt)."""
import sys

import cv2
import numpy as np
import pytest

pytest.importorskip("torch")
pytest.importorskip("timm")

from app.ml import inference  # noqa: E402
from conftest import BACKEND, SAMPLES  # noqa: E402

sys.path.insert(0, str(BACKEND / "scripts"))
from make_test_checkpoint import build  # noqa: E402


@pytest.fixture(scope="module")
def model(tmp_path_factory):
    path = build(tmp_path_factory.mktemp("ckpt") / "stand_in.pt")
    return inference.load_model(path)


def rgb(name):
    return cv2.cvtColor(cv2.imread(str(SAMPLES / name)), cv2.COLOR_BGR2RGB)


def test_loads_as_real_model(model):
    assert not inference.is_mock(model)
    assert inference.model_version(model) == inference.DEFAULT_REAL_MODEL_VERSION
    # Training resized original -> 512 -> 384 with Ben Graham enhancement (BACKEND_HANDOFF B4).
    assert model.resize_chain == (512, 384) and model.enhancement == "ben"


def test_preprocessing_shapes(model):
    square = model.square(rgb("normal.jpg"))
    assert square.shape == (384, 384, 3) and square.dtype == np.uint8
    assert tuple(model.tensor(square).shape) == (1, 3, 384, 384)
    # Non-square, odd-sized input works too.
    assert model.square(cv2.resize(rgb("normal.jpg"), (1100, 700))).shape == (384, 384, 3)


def test_predict_contract(model):
    out = inference.predict(model, rgb("severe.jpg"))
    assert set(out) == {"grade", "probabilities"}
    assert isinstance(out["grade"], int) and 0 <= out["grade"] <= 4
    assert len(out["probabilities"]) == 5 and abs(sum(out["probabilities"]) - 1) < 1e-5
    assert out["grade"] == int(np.argmax(out["probabilities"]))


def test_gradcam_png(model):
    png = inference.gradcam(model, rgb("moderate.jpg"))
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    assert img is not None and img.shape[1] <= 512


def test_full_pipeline_with_real_model(client, model):
    from app.services.pipeline import analyze_image

    case = analyze_image((SAMPLES / "moderate.jpg").read_bytes(), "REAL-1", model, 0.6)
    assert case["model_version"] == inference.DEFAULT_REAL_MODEL_VERSION
    assert case["prediction"] is not None and case["heatmap_url"]
    assert client.get(case["heatmap_url"]).status_code == 200
    # Blurry images never reach the model.
    blurry = analyze_image((SAMPLES / "blurry.jpg").read_bytes(), "REAL-1", model, 0.6)
    assert blurry["prediction"] is None and blurry["triage"]["level"] == "retake"


def test_missing_weights_fall_back_to_mock(tmp_path):
    from app.main import load_model_once

    with pytest.raises(FileNotFoundError):
        inference.load_model(tmp_path / "nope.pt")

    class S:
        use_mock_model = False
        model_weights_path = tmp_path / "nope.pt"

    assert inference.is_mock(load_model_once(S()))


def test_backend_copy_matches_ai_teammates_file():
    """backend/app/ml/real_model.py must stay identical to ai/inference.py (below its header)."""
    theirs = BACKEND.parent / "ai" / "inference.py"
    if not theirs.is_file():
        pytest.skip("ai/inference.py not present")
    ours = (BACKEND / "app" / "ml" / "real_model.py").read_text().splitlines(keepends=True)[10:]
    assert "".join(ours) == theirs.read_text(), "real_model.py and ai/inference.py differ: sync them"
