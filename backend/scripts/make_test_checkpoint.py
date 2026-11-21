"""Build a STAND-IN checkpoint in the exact format of the AI teammate's model_inference.pt,
but with RANDOM (untrained) weights. Its predictions are meaningless.

Use it to test the real-model plumbing (loading, preprocessing, predict, Grad-CAM,
CPU speed, the API) before the trained weights arrive:

    cd backend
    python scripts/make_test_checkpoint.py                 # -> models/test_random_weights.pt
    USE_MOCK_MODEL=false MODEL_WEIGHTS_PATH=models/test_random_weights.pt \\
        MODEL_VERSION=test-random-weights STORAGE_DIR=/tmp/nexus-test \\
        uvicorn app.main:app --port 8000

Format (ai/BACKEND_HANDOFF.md, section A2): {"format_version": 1, "model": state_dict with
"backbone.*" + "heads.dr.weight/bias", "config": {...}, "heads": {"dr": 5}, "epoch", "metrics"}.
"""
from __future__ import annotations

import sys
from pathlib import Path

import timm
import torch

BACKEND = Path(__file__).resolve().parent.parent
OUT = BACKEND / "models" / "test_random_weights.pt"


def build(out: Path = OUT, seed: int = 0) -> Path:
    torch.manual_seed(seed)
    backbone = timm.create_model("efficientnet_b0", pretrained=False, num_classes=0)
    head = torch.nn.Linear(backbone.num_features, 5)
    state = {f"backbone.{k}": v for k, v in backbone.state_dict().items()}
    state["heads.dr.weight"] = head.weight.detach().clone()
    state["heads.dr.bias"] = head.bias.detach().clone()
    ckpt = {
        "format_version": 1,
        "model": state,
        "config": {
            # Same values as the real training config (BACKEND_HANDOFF.md B4).
            "backbone": "efficientnet_b0",
            "img_size": 384,
            "cache_size": 512,
            "cache_dir": "cache",
            "preprocess": "ben",
            "STAND_IN_RANDOM_WEIGHTS": True,
        },
        "heads": {"dr": 5},
        "epoch": -1,
        "metrics": {},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(ckpt, out)
    return out


if __name__ == "__main__":
    path = build(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
    print(f"wrote {path} ({path.stat().st_size / 1e6:.1f} MB) - RANDOM weights, for plumbing tests only")
