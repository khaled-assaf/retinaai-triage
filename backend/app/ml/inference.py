"""Model interface. THE AI TEAMMATE IMPLEMENTS THE REAL VERSION HERE.

The backend only ever calls these three functions:

    load_model(weights_path)      -> model             (called ONCE at startup)
    predict(model, img_rgb)       -> {"grade": int, "probabilities": [5 floats]}
    gradcam(model, img_rgb)       -> bytes             (PNG heatmap overlay)

`img_rgb` is a uint8 numpy array of shape (H, W, 3) in RGB order, full resolution,
exactly as decoded from the upload. It has already passed the quality check.

While USE_MOCK_MODEL=true (the default), `load_mock_model()` is used instead of
`load_model()`, and predict/gradcam dispatch to the mock implementation. That lets
the frontend build against realistic data before the real model exists.

To plug in the real model:
  1. pip install -r requirements-ml.txt
  2. Implement the three TODO sections below (load_model, _real_predict, _real_gradcam).
  3. Put the checkpoint at backend/models/model.pth (gitignored), or set MODEL_WEIGHTS_PATH.
  4. Set USE_MOCK_MODEL=false in backend/.env and restart. GET /api/health should
     show "mock": false and your model_version.
  5. Run `pytest` - the API tests only check the shape of the output.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import cv2
import numpy as np

GRADE_LABELS = [
    "No DR",
    "Mild NPDR",
    "Moderate NPDR",
    "Severe NPDR",
    "Proliferative DR",
]

# TODO(AI): bump this whenever you ship a new checkpoint so cases record which model graded them.
REAL_MODEL_VERSION = "real-v0"
MOCK_MODEL_VERSION = "mock-v0"


# =============================================================== real model (TODO)
def load_model(weights_path: str | Path) -> Any:
    """Load the trained model once. Return whatever object predict()/gradcam() need.

    TODO(AI): implement. Sketch:

        import torch, timm
        model = timm.create_model("efficientnet_b0", pretrained=False, num_classes=5)
        state = torch.load(weights_path, map_location="cpu")
        model.load_state_dict(state)
        model.eval()
        torch.set_num_threads(4)            # CPU inference
        return model

    Notes:
      - Requests run in a threadpool and share this single model object. Keep
        predict()/gradcam() free of global mutable state (eval mode + no_grad is fine).
      - Raise a clear exception if the file is missing; startup will log it and
        fall back to the mock model so the demo keeps working.
    """
    weights_path = Path(weights_path)
    if not weights_path.is_file():
        raise FileNotFoundError(f"Model weights not found at {weights_path}")
    raise NotImplementedError("Real model loading not implemented yet (see TODOs in ml/inference.py)")


def _preprocess(img_rgb: np.ndarray) -> Any:
    """TODO(AI): convert img_rgb -> model input tensor.

    !!! Preprocessing here MUST match what the checkpoint was trained with !!!
    Same crop of the black border, same resize (e.g. 224 or 384), same color
    normalisation (e.g. Ben Graham's Gaussian-subtract trick, or ImageNet
    mean/std), same channel order (RGB). A mismatch silently ruins accuracy.
    Ideally import the exact transform from the training code in ai/.
    """
    raise NotImplementedError


def _real_predict(model: Any, img_rgb: np.ndarray) -> dict:
    """TODO(AI): run the model and return {"grade": int, "probabilities": [5 floats]}.

        x = _preprocess(img_rgb)                     # (1, 3, H, W)
        with torch.no_grad():
            probs = torch.softmax(model(x), dim=1)[0].tolist()
        return {"grade": int(np.argmax(probs)), "probabilities": probs}

    If you trained a regression model (common for APTOS / QWK), convert the score
    into 5 pseudo-probabilities so triage still works, and tell the backend owner.
    """
    raise NotImplementedError


def _real_gradcam(model: Any, img_rgb: np.ndarray) -> bytes:
    """TODO(AI): Grad-CAM for the predicted class, returned as PNG bytes of the
    heatmap blended over the (resized) original image.

    With the `grad-cam` package:
        from pytorch_grad_cam import GradCAM
        from pytorch_grad_cam.utils.image import show_cam_on_image
        cam = GradCAM(model=model, target_layers=[model.conv_head])  # pick last conv layer
        mask = cam(input_tensor=_preprocess(img_rgb))[0]
        overlay = show_cam_on_image(resized_rgb_float01, mask, use_rgb=True)
        return _encode_png_rgb(overlay)
    """
    raise NotImplementedError


# ======================================================================= mock model
class MockModel:
    """Stand-in used when USE_MOCK_MODEL=true. Deterministic per image."""

    version = MOCK_MODEL_VERSION


def load_mock_model() -> MockModel:
    return MockModel()


def is_mock(model: Any) -> bool:
    return isinstance(model, MockModel)


def model_version(model: Any) -> str:
    if model is None:
        return "none"
    return MOCK_MODEL_VERSION if is_mock(model) else REAL_MODEL_VERSION


def image_seed(img_rgb: np.ndarray) -> int:
    """Stable seed from a coarse, quantised thumbnail of the image.

    Coarse on purpose: tiny JPEG decoder differences between machines must not
    change the mock output.
    """
    thumb = cv2.resize(img_rgb, (32, 32), interpolation=cv2.INTER_AREA)
    digest = hashlib.sha256((thumb // 16).astype(np.uint8).tobytes()).digest()
    return int.from_bytes(digest[:8], "big")


# Roughly the APTOS 2019 class balance, so the mock queue looks realistic.
_MOCK_GRADE_PRIOR = [0.45, 0.12, 0.25, 0.08, 0.10]


def _mock_predict(img_rgb: np.ndarray) -> dict:
    rng = np.random.default_rng(image_seed(img_rgb))
    grade = int(rng.choice(5, p=_MOCK_GRADE_PRIOR))
    peak = float(rng.uniform(0.40, 0.93))
    # Spread the rest over other grades, favouring neighbouring grades (ordinal).
    distance = np.abs(np.arange(5) - grade)
    weights = rng.dirichlet(np.ones(5)) / (1.0 + 2.0 * distance)
    weights[grade] = 0.0
    rest = (1.0 - peak) * weights / weights.sum()
    probs = rest
    probs[grade] = peak
    probs = np.round(probs, 4)
    probs[grade] += round(1.0 - float(probs.sum()), 4)  # make it sum to exactly 1
    return {"grade": grade, "probabilities": [float(p) for p in probs]}


def _encode_png_rgb(img_rgb: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return buf.tobytes()


def _mock_gradcam(img_rgb: np.ndarray, max_width: int = 512) -> bytes:
    """Fake heatmap: one or two Gaussian blobs inside the retina, JET-coloured."""
    h, w = img_rgb.shape[:2]
    if w > max_width:
        img_rgb = cv2.resize(img_rgb, (max_width, round(h * max_width / w)), interpolation=cv2.INTER_AREA)
        h, w = img_rgb.shape[:2]
    rng = np.random.default_rng(image_seed(img_rgb) ^ 0x5EED)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    heat = np.zeros((h, w), np.float32)
    r = min(h, w) / 2
    for i in range(int(rng.integers(1, 3))):
        cx = w / 2 + rng.uniform(-0.35, 0.35) * r
        cy = h / 2 + rng.uniform(-0.35, 0.35) * r
        sigma = rng.uniform(0.12, 0.22) * r
        heat += (1.0 if i == 0 else 0.6) * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma**2))
    heat /= heat.max()
    color = cv2.cvtColor(cv2.applyColorMap((heat * 255).astype(np.uint8), cv2.COLORMAP_JET), cv2.COLOR_BGR2RGB)
    retina = (cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY) > 15).astype(np.float32)
    alpha = ((0.15 + 0.45 * heat) * retina)[..., None]  # don't tint the black border
    overlay = (img_rgb.astype(np.float32) * (1 - alpha) + color.astype(np.float32) * alpha).astype(np.uint8)
    return _encode_png_rgb(overlay)


# ================================================================ public dispatchers
def predict(model: Any, img_rgb: np.ndarray) -> dict:
    """Return {"grade": int 0-4, "probabilities": [5 floats summing to ~1]}."""
    return _mock_predict(img_rgb) if is_mock(model) else _real_predict(model, img_rgb)


def gradcam(model: Any, img_rgb: np.ndarray) -> bytes:
    """Return PNG bytes of the explanation heatmap blended over the image."""
    return _mock_gradcam(img_rgb) if is_mock(model) else _real_gradcam(model, img_rgb)
