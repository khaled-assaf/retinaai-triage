# RetinaAI Triage

Web prototype that screens retinal fundus photos for **diabetic retinopathy (DR)**,
grades them (0-4), shows a Grad-CAM heatmap, and sorts cases into a triage queue
for clinician review.

> ⚠️ **Disclaimer:** research / educational hackathon demo. **Not a medical device and
> not for clinical diagnosis.** Outputs from the mock model are random-but-consistent
> placeholders.

## Team & folders

Each person owns one folder, which keeps merge conflicts to a minimum.

| Role | Owner | Folder |
|---|---|---|
| Backend (FastAPI) | Backend teammate | `backend/` |
| Frontend (React + Vite) | Frontend teammate | `frontend/` |
| AI model (training, inference) | AI teammate | `ai/` + `backend/app/ml/inference.py` |
| Triage rules & demo images | Medical teammate | `backend/app/services/triage.py` (rules at the top) + `backend/samples/` |

```
retinaai-triage/
├── README.md
├── docs/API.md               API contract (source of truth for frontend <-> backend)
├── frontend/                 React app (Vite), proxies /api -> :8000
├── ai/                       training notebooks / scripts
└── backend/
    ├── app/
    │   ├── main.py           app, lifespan (load model once, init DB, seed demo cases), CORS
    │   ├── config.py         settings from env / backend/.env
    │   ├── schemas.py        Pydantic models = API contract
    │   ├── routers/          analyze, cases (queue/review/images), samples, health
    │   ├── services/
    │   │   ├── quality.py    OpenCV image-quality checks (blur, exposure, framing)
    │   │   ├── triage.py     rule-based triage (rules are data at the top)
    │   │   └── pipeline.py   decode -> quality -> predict + gradcam -> triage -> save
    │   ├── ml/inference.py   MODEL INTERFACE: load_model / predict / gradcam (+ mock)
    │   └── storage/db.py     SQLite (stdlib), image files under backend/storage_data/
    ├── samples/              5 synthetic demo images + samples.json
    └── tests/                pytest
```

## Run the backend

Requires Python 3.11+.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # optional, defaults are fine
uvicorn app.main:app --reload --port 8000
```

- Interactive API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/health
- On first start the DB is seeded with 8 demo cases, so the queue isn't empty.
  To reset, stop the server and delete `backend/storage_data/`.

Tests:

```bash
cd backend && pytest
```

Docker:

```bash
cd backend && docker build -t retinaai-backend . && docker run -p 8000:8000 retinaai-backend
```

## Run the frontend

See [`frontend/README.md`](frontend/README.md). In short: Vite dev server on :5173, proxying
`/api` to `http://localhost:8000`.

## Plugging in the real model (AI teammate)

1. Implement the TODOs in [`backend/app/ml/inference.py`](backend/app/ml/inference.py):
   `load_model`, `_preprocess`, `_real_predict` and `_real_gradcam`.
   **Preprocessing must match what the checkpoint was trained with.**
2. `pip install -r requirements-ml.txt`
3. Put weights at `backend/models/model.pth` (gitignored), or set `MODEL_WEIGHTS_PATH`.
4. Set `USE_MOCK_MODEL=false` in `backend/.env` and restart. `/api/health` should
   show `"mock": false`. If loading fails, the server logs the error and falls back
   to the mock model.

## Editing triage rules (medical teammate)

All rules are data at the top of [`backend/app/services/triage.py`](backend/app/services/triage.py):
labels and actions per level, grade → level mapping, and the top-2 ambiguity margin.
The confidence threshold is the `CONFIDENCE_THRESHOLD` env var (default 0.6).
Run `pytest tests/test_triage.py` after changes.

To replace the demo images, drop JPG/PNG files into `backend/samples/` and update
`samples.json`. Use a handful of license-compatible images only, never a dataset.

## Settings (env vars)

| Var | Default | Meaning |
|---|---|---|
| `USE_MOCK_MODEL` | `true` | use the mock model instead of real weights |
| `CONFIDENCE_THRESHOLD` | `0.6` | below this → "Needs clinician review" |
| `MAX_UPLOAD_MB` | `10` | larger uploads → 413 |
| `STORAGE_DIR` | `backend/storage_data` | case images, heatmaps, thumbnails |
| `DB_PATH` | `$STORAGE_DIR/retinaai.db` | SQLite file |
| `MODEL_WEIGHTS_PATH` | `backend/models/model.pth` | checkpoint for the real model |
| `SEED_DEMO_CASES` | `true` | seed demo cases into an empty DB |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | allowed browser origins |

## What is never committed

Dataset images, model weights (`*.pth`, `*.pt`, `*.onnx`, `*.h5`, …), `.env`, the SQLite
DB, and `backend/storage_data/`. See `.gitignore`.
