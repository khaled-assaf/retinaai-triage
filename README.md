# 🧬 RetinaAI Nexus: from detection to action

An AI-powered retinal screening and patient-care platform for **diabetic retinopathy (DR)**.
Most tools stop at detecting disease. Nexus also connects patients to care: it screens the
image, triages the patient, issues a shareable multilingual **European Retina Passport**, and
tracks the referral until the patient is actually seen.

> ⚠️ **Disclaimer:** research / educational hackathon prototype using **simulated data**.
> **Not a medical device and not for clinical diagnosis.** While `USE_MOCK_MODEL=true`, AI
> outputs are random-but-consistent placeholders.

## Features

| # | Feature | Where |
|---|---|---|
| 1 | **AI screening**: DR grade 0–4 + probabilities + Grad-CAM heatmap | `ml/inference.py` (mock now, real model from the AI teammate) |
| 2 | **Smart quality check**: blur / exposure / framing, plus *uncertain prediction* detection with a human-readable reason | `services/quality.py`, `services/triage.py` |
| 3 | **European Retina Passport**: one-page PDF report in 6 languages (EN, RO, DE, FR, ES, IT), with a shareable expiring link and a QR code | `reports/` |
| 4 | **Smart triage**: urgent > review > referable > retake > routine; a clinician's grade overrides the AI | `services/triage.py` |
| 5 | **Follow-up tracking**: every case gets a referral, rescreen, retake or review task with a due date; tracks overdue items, missed appointments and simulated reminders in the patient's language | `storage/followups.py` |
| + | **Dashboard**: totals, triage mix, attendance rate, per-country and per-month stats | `GET /api/dashboard` |

On first start the backend seeds **30 simulated patients in 12 European countries** with about 50
screenings over the last 18 months and realistic follow-up outcomes (attended, missed, overdue,
booked). This gives the dashboard and queue something to show from the first minute.

## Team & folders

Each person owns one folder, which keeps merge conflicts to a minimum.

| Role | Folder |
|---|---|
| Backend (FastAPI) | `backend/` |
| Frontend (React + Vite) | `frontend/` |
| AI model (training, inference) | `ai/` + `backend/app/ml/inference.py` |
| Medical (triage rules, follow-up deadlines, demo images, translation check) | `backend/app/services/triage.py` (rules at the top), `backend/app/reports/i18n.py`, `backend/samples/` |

```
retinaai-triage/
├── README.md
├── docs/API.md                 API contract (source of truth for frontend <-> backend)
├── frontend/                   React app (Vite), proxies /api -> :8000
├── ai/                         training notebooks / scripts
└── backend/
    ├── app/
    │   ├── main.py             app, lifespan (load model once, init DB, seed simulated data), CORS
    │   ├── config.py           settings from env / backend/.env
    │   ├── schemas.py          Pydantic models = API contract
    │   ├── seed.py             simulated European patients, history and follow-up outcomes
    │   ├── routers/            analyze, cases, reports (passport), patients, followups,
    │   │                       dashboard, samples, health
    │   ├── services/
    │   │   ├── quality.py      OpenCV image-quality checks
    │   │   ├── triage.py       triage + follow-up rules (data at the top)
    │   │   └── pipeline.py     decode -> quality -> predict + gradcam -> triage -> save -> follow-up
    │   ├── ml/inference.py     MODEL INTERFACE: load_model / predict / gradcam (+ mock)
    │   ├── reports/
    │   │   ├── i18n.py         translations (6 languages)
    │   │   ├── pdf.py          European Retina Passport PDF (ReportLab)
    │   │   └── fonts/          Liberation Sans (OFL) - covers all EU alphabets
    │   └── storage/            SQLite (stdlib): db.py (cases), patients.py, followups.py,
    │                           shares.py, stats.py. Files under backend/storage_data/
    ├── samples/                5 synthetic demo images + samples.json
    └── tests/                  pytest (58 tests)
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
- Try it:
  - dashboard: http://localhost:8000/api/dashboard
  - a passport PDF: http://localhost:8000/api/cases/c_0001/report.pdf?lang=ro
- **Reset the demo data** (also needed after pulling schema changes): stop the server,
  delete `backend/storage_data/`, then start it again.

Tests: `cd backend && pytest`. Docker: `cd backend && docker build -t retinaai-backend . && docker run -p 8000:8000 retinaai-backend`.

## Run the frontend

See [`frontend/README.md`](frontend/README.md). Vite dev server on :5173, proxying `/api` to `http://localhost:8000`.

## Plugging in the real model (AI teammate)

1. Implement the TODOs in [`backend/app/ml/inference.py`](backend/app/ml/inference.py)
   (`load_model`, `_preprocess`, `_real_predict` and `_real_gradcam`). **Preprocessing must
   match what the checkpoint was trained with.**
2. `pip install -r requirements-ml.txt`
3. Put the weights at `backend/models/model.pth` (gitignored), or set `MODEL_WEIGHTS_PATH`.
4. Set `USE_MOCK_MODEL=false` in `backend/.env` and restart. `/api/health` should show
   `"mock": false`.

## Medical teammate

- **Triage, follow-up types and deadlines:** data at the top of
  [`backend/app/services/triage.py`](backend/app/services/triage.py). The deadlines are
  placeholders loosely based on the NHS DESP pathway, so please verify them.
- **Translations:** [`backend/app/reports/i18n.py`](backend/app/reports/i18n.py). They were
  drafted with AI help and need a native-speaker check before any demo to outsiders.
- **Demo images:** `backend/samples/` + `samples.json`. Use a handful of license-OK images,
  never a dataset.

## Settings (env vars)

| Var | Default | Meaning |
|---|---|---|
| `USE_MOCK_MODEL` | `true` | use the mock model instead of real weights |
| `CONFIDENCE_THRESHOLD` | `0.6` | below this → "Needs clinician review" |
| `MAX_UPLOAD_MB` | `10` | larger uploads → 413 |
| `STORAGE_DIR` | `backend/storage_data` | case images, heatmaps, thumbnails |
| `DB_PATH` | `$STORAGE_DIR/retinaai.db` | SQLite file |
| `MODEL_WEIGHTS_PATH` | `backend/models/model.pth` | checkpoint for the real model |
| `SEED_DEMO_CASES` | `true` | seed simulated data into an empty DB |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | allowed browser origins |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | base of the public passport links and QR codes |
| `SHARE_DAYS_VALID` | `30` | how long a shared passport link works |

## What is never committed

Dataset images, model weights (`*.pth`, `*.pt`, `*.onnx`, `*.h5`, …), `.env`, the SQLite DB
and `backend/storage_data/`. See `.gitignore`.
