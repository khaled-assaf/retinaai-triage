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
| 2 | **TrustGate**: image quality, AI uncertainty, urgent-symptom screening. When any of these fails, the system asks for human assessment instead of reassuring. See [`docs/CLINICAL_SAFETY.md`](docs/CLINICAL_SAFETY.md) | `services/quality.py`, `services/triage.py`, `reports/content.py` |
| 3 | **European Retina Passport**: one-page PDF report in 6 languages (EN, RO, DE, FR, ES, IT), with a shareable expiring link and a QR code | `reports/` |
| 4 | **Smart triage**: emergency > urgent > review > referable > retake > routine. Experimental safety flags send likely-missed disease to clinician review. A clinician's decision supersedes the AI, and both are kept in an audit log | `services/triage.py` |
| 5 | **Follow-up tracking**: every case gets a referral, rescreen, retake or review task with a due date; tracks overdue items, missed appointments and simulated reminders in the patient's language | `storage/followups.py` |
| + | **Dashboard**: totals, triage mix, attendance rate, per-country and per-month stats | `GET /api/dashboard` |

On first start the backend seeds **30 simulated patients in 12 European countries** with about 50
screenings over the last 18 months and realistic follow-up outcomes (attended, missed, overdue,
booked). This gives the dashboard and queue something to show from the first minute.

## Limitations (state these in every demo)

1. Training data are limited to APTOS; generalizability to other populations and cameras is unknown.
2. No independent external or prospective clinical validation.
3. Image gradability assessment and model confidence are not clinically validated.
4. The system cannot reliably rule out diabetic macular edema or other eye diseases; additional
   examination or OCT may be needed.
5. Moderate/severe classification errors and missed referable cases remain. This is a research
   prototype, not an approved clinical diagnostic system.

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
    │   ├── ml/real_model.py    the AI teammate's EfficientNet-B0 code (unchanged copy)
    │   ├── reports/
    │   │   ├── i18n.py         translations (6 languages)
    │   │   ├── pdf.py          European Retina Passport PDF (ReportLab)
    │   │   └── fonts/          Liberation Sans (OFL) - covers all EU alphabets
    │   └── storage/            SQLite (stdlib): db.py (cases), patients.py, followups.py,
    │                           shares.py, stats.py. Files under backend/storage_data/
    ├── samples/                5 synthetic demo images + samples.json
    ├── scripts/                make_test_checkpoint.py (stand-in weights), setup_real_samples.py (local APTOS demo images)
    └── tests/                  pytest (99 tests; real-model tests skip without torch)
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

## The AI model

The real model is the AI teammate's **EfficientNet-B0** (APTOS 2019, validation QWK 0.893,
referable AUC 0.98). Its model card, metrics and limitations are in
[`ai/BACKEND_HANDOFF.md`](ai/BACKEND_HANDOFF.md). Her inference code is integrated **unchanged** as
[`backend/app/ml/real_model.py`](backend/app/ml/real_model.py); a test keeps it identical to `ai/inference.py`.

**Switch from mock to the real model:**
```bash
cd backend && source .venv/bin/activate
pip install -r requirements-ml.txt --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
cp ~/Downloads/model_inference.pt models/          # weights come via Drive/Release, never git
echo "USE_MOCK_MODEL=false" >> .env
rm -rf storage_data                                # re-grade the demo data with the real model
uvicorn app.main:app --reload --port 8000          # /api/health -> "mock": false
```

If the weights are missing or fail to load, the server logs the error and **falls back to the
mock** (`/api/health` shows `"mock": true`).

**Real demo images (local only).** The 5 APTOS demo images (one per grade) aren't in git,
because the licence for public display isn't confirmed. Build them from the AI teammate's zip:
`python scripts/setup_real_samples.py` creates `backend/samples_real/` (gitignored). Then set
`SAMPLES_DIR=samples_real` in `backend/.env`, delete `storage_data/` and restart.

**No weights yet?** `python scripts/make_test_checkpoint.py` builds a stand-in checkpoint in the same
format with **random** weights (`models/test_random_weights.pt`), so you can test the real-model path.
Point `MODEL_WEIGHTS_PATH` at it. Its predictions are meaningless.

Speed on a laptop CPU: about 30 ms to predict and 55 ms for Grad-CAM per image.

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
| `MODEL_WEIGHTS_PATH` | `backend/models/model_inference.pt` | checkpoint for the real model |
| `MODEL_VERSION` | `effb0-v0.1-baseline` | stored on every case graded by the real model |
| `SEED_DEMO_CASES` | `true` | seed simulated data into an empty DB |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | allowed browser origins |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | base of the public passport links and QR codes |
| `SHARE_DAYS_VALID` | `30` | how long a shared passport link works |

## What is never committed

Dataset images, model weights (`*.pth`, `*.pt`, `*.onnx`, `*.h5`, …), `.env`, the SQLite DB
and `backend/storage_data/`. See `.gitignore`.
