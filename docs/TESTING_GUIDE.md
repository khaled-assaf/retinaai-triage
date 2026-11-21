# RetinaAI Nexus — Testing guide

Research prototype with simulated patients. Not for clinical use.

## 1. Setup (once)
```bash
git pull
# Backend (Python 3.11+)
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000          # keep running
# Frontend (new terminal)
cd frontend && npm install && npm run dev  # open http://localhost:5173
```
Default mode = **mock model + synthetic images** (no PyTorch needed). The green "API" dot in the
navbar means the backend is reachable. API docs: http://localhost:8000/docs
To reset demo data: stop the backend, delete `backend/storage_data/`, start again.

## 2. Test scenarios (mock mode, expected results)

| # | Do this | Expected |
|---|---|---|
| 1 | Screening → click **No DR** sample | AI grade 0 · "Routine screening…" · Clinical status **Pending clinician review** (provisional) · follow-up rescreen in 12 months |
| 2 | Click **Mild** sample | "Needs clinician review" · Why: AI uncertain |
| 3 | Click **Moderate** sample | "Non-urgent ophthalmology referral" · follow-up referral (21 days) |
| 4 | Click **Severe** sample | "High-priority ophthalmology assessment" · referral (14 days) |
| 5 | Click **Blurry** sample | "Retake image", no grade, no heatmap · status "Review not required" |
| 6 | Set *Urgent eye symptoms → Yes*, tick one, click **No DR** | **Emergency eye assessment**, same day, red symptom banner, top of the queue |
| 7 | Set *Yes* but tick nothing, click a sample | Error message, nothing analysed |
| 8 | Choose **Right eye**, run a sample | Case header shows "Right eye (OD)" |
| 9 | Upload your own JPG/PNG (drag & drop) | Result page; a non-eye or very dark photo → Retake; a `.txt` → error message |
| 10 | Case page → **Review** → enter a different grade + note | Triage shows "Clinician decision / set by clinician", status **Clinician modified**, case moves in the queue |
| 11 | http://localhost:8000/api/cases/{id}/audit | Two events: `case_created` (AI) and `clinician_review` (with reason) |
| 12 | Triage Queue | Order: emergency → urgent → review (priority first) → referable → retake → routine; filters work |
| 13 | Follow-ups → **Schedule +7d**, then **Attended** | Status changes; toast confirms |
| 14 | Follow-ups → **Remind** on a Romanian patient | Toast shows the SMS text in Romanian (simulated, nothing sent) |
| 15 | In `/docs`: PATCH `/api/followups/{id}` with `appointment_at` 3 days in the past, reload Follow-ups | Status **attendance unconfirmed** (never auto-"missed"); then mark Attended/Missed |
| 16 | Case → **Passport** → pick English, **Open passport PDF**; repeat in Română | One A4 page: banner, sections A–F, TrustGate, "Provisional…", scores total 100%, emergency warning, footer with case ID/model/time |
| 17 | Passport → **Share link** → open the link | PDF with QR code; **name and year of birth hidden** |
| 18 | Stop the backend, reload the site | Clear "cannot reach the server" errors (follow-ups may show a "simulated" banner) |

## 3. Automated checks
```bash
cd backend && pytest          # expect all tests to pass (real-model tests skip without torch)
cd frontend && npm run build  # expect a successful build
```

## 4. Real model (only the person with the weights)
```bash
cd backend && pip install -r requirements-ml.txt --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
cp model_inference.pt models/            # weights are shared privately, never in git
echo "USE_MOCK_MODEL=false" >> .env
rm -rf storage_data && uvicorn app.main:app --port 8000
```
`/api/health` must show `"mock": false`. Heatmaps are then real (not "Simulated visualization").
APTOS demo images are local only (`python scripts/setup_real_samples.py`, then `SAMPLES_DIR=samples_real` in `.env`) — never commit them or share them publicly.

## 5. Reporting a bug
Send: scenario #, what you did, what you expected, what happened, screenshot, case ID
(e.g. `c_0042`), and whether `/api/health` showed `mock: true` or `false`.
