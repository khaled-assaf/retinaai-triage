# RetinaAI Triage API contract

Base URL: `http://localhost:8000`. All endpoints live under `/api`.
Live, interactive docs: **http://localhost:8000/docs** (generated from `backend/app/schemas.py`).
If you change the contract, update this file and `schemas.py` together.

> Research prototype. Not for clinical diagnosis.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/analyze` | Upload a fundus image, get a full case |
| GET | `/api/queue` | Case summaries sorted by urgency |
| GET | `/api/cases/{id}` | Full case |
| PATCH | `/api/cases/{id}` | Clinician review |
| GET | `/api/cases/{id}/image` | Original image (jpg/png) |
| GET | `/api/cases/{id}/heatmap` | Grad-CAM overlay (png). 404 if quality failed |
| GET | `/api/cases/{id}/thumbnail` | 256px-wide thumbnail (jpg) |
| GET | `/api/samples` | Demo images for the sample tray |
| GET | `/api/samples/{id}/image` | Demo image file |
| POST | `/api/samples/{id}/analyze` | Run the pipeline on a demo image (one click) |
| GET | `/api/health` | Server/model status |

Image URLs in responses are **relative** (`/api/...`). With the Vite proxy you can use them
directly in `<img src>`.

---

### POST /api/analyze

`multipart/form-data`:

| Field | Type | Required |
|---|---|---|
| `image` | file, JPG or PNG, ≤ `MAX_UPLOAD_MB` (10 MB) | yes |
| `patient_ref` | string ≤ 100 chars | no |

```bash
curl -F image=@eye.jpg -F patient_ref=DEMO-007 http://localhost:8000/api/analyze
```

```js
const fd = new FormData();
fd.append("image", file);
fd.append("patient_ref", "DEMO-007");
const res = await fetch("/api/analyze", { method: "POST", body: fd });
if (!res.ok) throw new Error((await res.json()).detail);
const caseData = await res.json();
```

Response `200`: the **full case** object.

```json
{
  "case_id": "c_0042",
  "created_at": "2026-11-21T10:32:22Z",
  "patient_ref": "DEMO-007",
  "quality": {
    "passed": true,
    "score": 0.82,
    "reason": "OK",
    "checks": { "blur": 0.82, "exposure": "ok", "framing": "ok" }
  },
  "prediction": {
    "grade": 3,
    "label": "Severe NPDR",
    "confidence": 0.71,
    "probabilities": [0.02, 0.05, 0.17, 0.71, 0.05]
  },
  "heatmap_url": "/api/cases/c_0042/heatmap",
  "image_url": "/api/cases/c_0042/image",
  "triage": { "level": "urgent", "label": "Urgent referral", "action": "Refer to ophthalmologist" },
  "review": { "status": "pending", "clinician_grade": null, "note": null },
  "model_version": "mock-v0",
  "processing_ms": 412,
  "disclaimer": "Research prototype. Not for clinical diagnosis."
}
```

**When quality fails**, `prediction` and `heatmap_url` are `null` and the triage level is `retake`:

```json
{
  "case_id": "c_0043",
  "quality": {
    "passed": false,
    "score": 0.0,
    "reason": "Image is blurry",
    "checks": { "blur": 0.0, "exposure": "ok", "framing": "ok" }
  },
  "prediction": null,
  "heatmap_url": null,
  "image_url": "/api/cases/c_0043/image",
  "triage": { "level": "retake", "label": "Retake image", "action": "Recapture the fundus photo (check focus, lighting and centering)" },
  "...": "other fields as above"
}
```

Field values:

- `quality.checks.blur`: 0..1, higher is sharper.
- `quality.checks.exposure`: `"ok"`, `"underexposed"` or `"overexposed"`.
- `quality.checks.framing`: `"ok"`, `"too_small"` (retina covers too little of the frame) or
  `"not_found"` (no circular retina region).
- `quality.reason`: `"OK"` or a human-readable message, with several joined by `"; "`.
- `prediction.grade` / `label`: `0 No DR`, `1 Mild NPDR`, `2 Moderate NPDR`, `3 Severe NPDR`,
  `4 Proliferative DR`.
- `prediction.confidence`: the probability of the predicted grade.
- `triage.level`: `urgent` | `review` | `referable` | `retake` | `routine`.

| level | label | when |
|---|---|---|
| `retake` | Retake image | quality failed |
| `review` | Needs clinician review | confidence < 0.6 **or** top-2 probabilities within 0.15 (any grade) |
| `routine` | Routine screening, rescreen in 12 months | grade 0-1 |
| `referable` | Schedule specialist appointment | grade 2 |
| `urgent` | Urgent referral | grade 3-4 |

---

### GET /api/queue

Case summaries sorted by urgency (`urgent > review > referable > retake > routine`), then
newest first. No image data: only `thumbnail_url`. Response is a JSON **array**.

Optional query params: `status=pending|reviewed`, `limit` (default 200).

```json
[
  {
    "case_id": "c_0009",
    "created_at": "2026-11-21T10:32:22Z",
    "patient_ref": "DEMO-007",
    "triage_level": "urgent",
    "triage_label": "Urgent referral",
    "grade": 3,
    "grade_label": "Severe NPDR",
    "confidence": 0.6793,
    "quality_passed": true,
    "review_status": "pending",
    "thumbnail_url": "/api/cases/c_0009/thumbnail"
  },
  {
    "case_id": "c_0004",
    "created_at": "2026-11-21T10:30:01Z",
    "patient_ref": "DEMO-004",
    "triage_level": "retake",
    "triage_label": "Retake image",
    "grade": null,
    "grade_label": null,
    "confidence": null,
    "quality_passed": false,
    "review_status": "pending",
    "thumbnail_url": "/api/cases/c_0004/thumbnail"
  }
]
```

### GET /api/cases/{id}

Full case (same shape as `/analyze`). `404 {"detail": "Case not found"}`.

### PATCH /api/cases/{id}

```json
{ "status": "reviewed", "clinician_grade": 3, "note": "Agree, refer this week" }
```

- `status`: `"reviewed"` (or `"pending"` to undo)
- `clinician_grade`: `0`-`4` or `null`
- `note`: string (≤ 2000 chars) or `null`

Returns the updated full case. An out-of-range grade returns `422`.

### GET /api/samples

```json
[
  {
    "id": "severe",
    "label": "Severe NPDR (synthetic)",
    "image_url": "/api/samples/severe/image",
    "expected_grade": 3,
    "description": "SYNTHETIC placeholder. Extensive haemorrhages and cotton-wool spots."
  }
]
```

Current ids: `normal`, `mild`, `moderate`, `severe`, `blurry` (the medical teammate may change them).

### POST /api/samples/{id}/analyze

Runs the full pipeline on a demo image and returns a new full case. Optional query param
`?patient_ref=...` (default `SAMPLE-<id>`).

```bash
curl -X POST http://localhost:8000/api/samples/severe/analyze
```

### GET /api/health

```json
{ "status": "ok", "model_loaded": true, "mock": true, "model_version": "mock-v0" }
```

## Errors

Every error has the same body: `{"detail": "<human-readable string>"}`.

| Code | When |
|---|---|
| 400 | unsupported file type (not JPG/PNG), empty file, or image can't be decoded |
| 404 | unknown case / sample, or heatmap of a case that failed quality |
| 413 | upload larger than `MAX_UPLOAD_MB` |
| 422 | missing/invalid fields (e.g. no `image`, `clinician_grade` = 7) |
| 500 | unexpected server error |
