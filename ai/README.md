# AI model

Training happens in the AI teammate's own repo (Kaggle). This folder holds the handoff:

| File | What it is |
|---|---|
| `BACKEND_HANDOFF.md` | Model card: architecture, preprocessing, metrics, limitations, Kaggle check cells |
| `inference.py` | Her inference code (`load_model` / `predict` / `gradcam`) |
| `predict.py` | A file from her training repo, for reference only. It imports `src/retinaai/...`, which isn't in this repo, so it can't run here |

**Integration:** `inference.py` is copied unchanged into
[`backend/app/ml/real_model.py`](../backend/app/ml/real_model.py), below a short header.
The test `test_backend_copy_matches_ai_teammates_file` fails if the two drift apart. If you change
preprocessing or loading, update both files, or just the backend one and copy it back.

**Weights are never committed.** `model_inference.pt` (~16 MB) comes via Drive or a GitHub Release
and goes in `backend/models/`. `*.pt`, `*.pth`, `*.onnx`, `*.h5`, `*.ckpt`, `*.safetensors` and
`data/` are gitignored.

**Status:**
- [x] `model_inference.pt` received and integrated (sha256 `ce771f11684c3d58…`, lives in `backend/models/`)
- [x] Kaggle checks K1/K2/K3 done; CPU speed measured by backend (85–179 ms per request)
- [x] Safety thresholds T = 0.15 / U = 0.25 (C10) implemented in `backend/app/services/triage.py`, **pending medical approval**
- [x] 5 demo images received (`demo_images.zip`, gitignored); `backend/scripts/setup_real_samples.py` installs them locally
- [ ] APTOS competition rules: check before showing the images publicly (G17)
- [ ] Cosmetic: on APTOS photos cut off at top/bottom, the Grad-CAM overlay tints the black padding bands blue

**Update (2026-11-21):** robustness tested on poor-quality photos; no model change. Results are in `docs/CLINICAL_SAFETY.md` ("Robustness to poor-quality photos").
