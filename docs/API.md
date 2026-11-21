# RetinaAI Nexus API contract

Base URL: `http://localhost:8000`. All endpoints live under `/api`.
Live, interactive docs: **http://localhost:8000/docs** (generated from `backend/app/schemas.py`).
If you change the contract, update this file and `schemas.py` together.

> Research prototype with simulated data. Not for clinical use. Clinical rules and their
> rationale: [`CLINICAL_SAFETY.md`](CLINICAL_SAFETY.md).

**Clinical-safety update (2026-11-21):**
- new level `emergency` (urgent symptoms override the AI);
- safety rules are now clinician-review **flags**, never automatic referrals;
- new case fields: `eye`, `symptoms`, `clinical_status`, `triage.action_code`,
  `triage.review_priority`, `triage.ai_triage`, `review.reviewed_at`;
- new follow-up status `unconfirmed`;
- new endpoint `GET /api/cases/{id}/audit`.

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
| GET | `/api/cases/{id}/report.pdf` | **European Retina Passport** PDF (`?lang=`, `?download=true`) |
| POST | `/api/cases/{id}/share` | Create a public, expiring passport link (`?lang=`) |
| GET | `/api/passport/{token}` | Public passport PDF via share token (includes QR code) |
| GET | `/api/languages` | Supported report languages |
| GET | `/api/patients` | Patients with latest screening + open follow-ups (`?country=`, `?q=`) |
| POST | `/api/patients` | Create a patient |
| GET | `/api/patients/{ref}` | Patient + all screenings + all follow-ups |
| PATCH | `/api/patients/{ref}` | Update patient fields (e.g. preferred language) |
| GET | `/api/followups` | Follow-up worklist, most urgent attention first |
| GET | `/api/followups/{id}` | One follow-up |
| PATCH | `/api/followups/{id}` | Book an appointment / mark attended, missed, cancelled |
| POST | `/api/followups/{id}/remind` | Simulated SMS reminder in the patient's language |
| GET | `/api/dashboard` | Stats for the follow-up / Europe dashboard |

Image URLs in responses are **relative** (`/api/...`). With the Vite proxy you can use them
directly in `<img src>`.

---

### POST /api/analyze

`multipart/form-data`:

| Field | Type | Required |
|---|---|---|
| `image` | file, JPG or PNG, ≤ `MAX_UPLOAD_MB` (10 MB) | yes |
| `patient_ref` | string ≤ 100 chars | no |
| `eye` | `right` \| `left` \| `unknown` (default: not recorded) | no |
| `symptoms` | omit = **not collected**; `none` = asked, none reported; or comma-separated codes `sudden_vision_loss`, `curtain_shadow`, `flashes_floaters`, `other_acute`. **Any code → `emergency`** | no |

`POST /api/samples/{id}/analyze` accepts the same `eye` and `symptoms` as query parameters.

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
  "triage": {
    "level": "urgent",
    "label": "Urgent referral",
    "action": "Refer to ophthalmologist",
    "reason": "AI grade 3 with confidence 0.71",
    "source": "ai"
  },
  "review": { "status": "pending", "clinician_grade": null, "note": null },
  "model_version": "mock-v0",
  "processing_ms": 412,
  "report_url": "/api/cases/c_0042/report.pdf",
  "followup": {
    "followup_id": "f_0042",
    "case_id": "c_0042",
    "patient_ref": "DEMO-007",
    "patient_name": "Elena Popescu",
    "country": "RO",
    "language": "ro",
    "triage_level": "urgent",
    "type": "referral",
    "status": "pending",
    "due_date": "2026-12-05",
    "days_until_due": 14,
    "overdue": false,
    "appointment_at": null,
    "reminders_sent": 0,
    "last_reminder_at": null,
    "note": null,
    "resolved_case_id": null,
    "created_at": "2026-11-21T10:32:22Z",
    "updated_at": "2026-11-21T10:32:22Z"
  },
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
- `triage.reason`: why that level was chosen. For uncertain predictions it says why, e.g.
  `"Uncertain: confidence 0.43 is below the 0.60 threshold"` or
  `"Uncertain: top two grades are only 0.09 apart (minimum 0.15)"`.
- `triage.source`: `"ai"`, or `"clinician"` after a clinician graded the case (see PATCH).
- `triage.safety_rule`: `null`, `"referable"` or `"urgent"` when a safety rule escalated the AI's
  top grade (see the rule order below). `triage.reason` then explains it, e.g.
  `"Safety rule: AI grade 1, but 18% chance of referable disease (grade 2 or worse; threshold 15%)"`.
- `followup`: the task this case created (see **Follow-ups** below).
- `report_url`: the European Retina Passport PDF for this case.

| level | label | when |
|---|---|---|
Rule order (the first match wins). `action_code` identifies the outcome; `level` drives queue
order and colours:

| # | level | action_code | label | when | follow-up |
|---|---|---|---|---|---|
| 0 | `emergency` | `emergency` | Emergency eye assessment | urgent symptoms reported (**overrides everything**) | `emergency_assessment`, same day |
| 1 | `retake` | `retake` | Retake image | quality failed | `retake`, 7 d |
| 2 | `review` | `review` | Needs clinician review | top score < 0.6 **or** top-2 within 0.15 | `clinician_review`, 2 d |
| 3 | `review` | `review` | Needs clinician review | **safety flag:** grade 0-1 but score on grade ≥ 2 ≥ 15% | `clinician_review`, 2 d |
| 4 | `review` | `review_priority` | Priority clinician review | **safety flag:** grade 2 but score on grade ≥ 3 ≥ 25% | `clinician_review`, 1 d |
| 5 | `routine` | `routine` | Routine screening, rescreen in 12 months | grade 0-1 | `rescreen`, 365 d |
| 5 | `referable` | `referable` | Non-urgent ophthalmology referral | grade 2 | `referral`, 21 d |
| 5 | `urgent` | `urgent_grade3` | High-priority ophthalmology assessment | grade 3 | `referral`, 14 d |
| 5 | `urgent` | `urgent_grade4` | Urgent ophthalmology referral | grade 4 | `referral`, 14 d |

The safety thresholds are experimental, not clinically validated referral criteria. Queue order:
`emergency > urgent > review (priority first) > referable > retake > routine`.

Other new fields:
- `clinical_status`:
  - `pending_review`: the AI suggestion is **provisional**;
  - `confirmed`: a clinician reviewed it, same grade;
  - `modified`: the clinician's grade differs;
  - `not_required`: image retake, no review needed.
- `eye`: `right` | `left` | `unknown`.
- `symptoms`: `{"collected": bool, "reported": [codes]}`.
- `triage.review_priority`: `"priority"` or null.
- `triage.symptoms`: the symptom codes that triggered `emergency`.
- `triage.ai_triage`: the original AI triage, kept after a clinician override.

Every case automatically gets a follow-up (placeholder deadlines, to be confirmed by the medical teammate):

| level | follow-up `type` | due in |
|---|---|---|
| `urgent` | `referral` | 14 days |
| `review` | `clinician_review` | 2 days |
| `referable` | `referral` | 90 days |
| `retake` | `retake` | 7 days |
| `routine` | `rescreen` | 365 days |

When a patient gets a new screening, their open `rescreen` / `retake` follow-ups are closed
automatically (`status: "attended"`, `resolved_case_id` = the new case).

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

The clinician's decision supersedes the AI. The AI `prediction` is never changed, and each review
is written to the audit log.

Side effects when `status` is `"reviewed"`:
- the case's open `clinician_review` follow-up is marked `attended`;
- if `clinician_grade` is set:
  - triage is recomputed from that grade (`triage.source = "clinician"`, so the case moves in the
    queue);
  - the original AI triage is kept in `triage.ai_triage`;
  - the matching follow-up is planned (e.g. grade 3 → high-priority `referral` due in 14 days);
  - reported urgent symptoms keep the case at `emergency`.

### GET /api/cases/{id}/audit

```json
[
  {"at": "2026-11-21T10:00:00Z", "actor": "ai", "event": "case_created",
   "details": {"model_version": "effb0-v0.1-baseline", "prediction": {"grade": 2, "...": "..."}, "triage": {"...": "..."}}},
  {"at": "2026-11-21T11:00:00Z", "actor": "clinician", "event": "clinician_review",
   "details": {"clinician_grade": 3, "ai_grade": 2, "reason": "IRMA seen",
               "triage_before": {"level": "referable", "action_code": "referable", "source": "ai"},
               "triage_after": {"level": "urgent", "action_code": "urgent_grade3", "source": "clinician"}}}
]
```

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

---

## European Retina Passport

Languages (`GET /api/languages`): `en` English, `ro` Română, `de` Deutsch, `fr` Français,
`es` Español, `it` Italiano. An unknown `lang` falls back to `en`. Without `lang`, the
patient's preferred language is used.

### GET /api/cases/{id}/report.pdf

One-page A4 PDF containing:
- patient details, screening details and image quality;
- a colour-coded triage box with the recommended action and an uncertainty note;
- the fundus photo next to the AI heatmap;
- probability bars per grade;
- follow-up, clinician review and screening history;
- a "SIMULATED DATA" banner and the disclaimer.

Opens inline in the browser; add `?download=true` to download.

```html
<a href="/api/cases/c_0042/report.pdf?lang=ro" target="_blank">Passport (RO)</a>
<iframe src="/api/cases/c_0042/report.pdf" style="width:100%;height:80vh"></iframe>
```

### POST /api/cases/{id}/share?lang=de

Creates a public link that needs no login and expires after `SHARE_DAYS_VALID` days (30 by default). The PDF served there
carries a QR code pointing back to the link.

```json
{
  "token": "dPOIECxNy_bEknDiY4whcQ",
  "case_id": "c_0042",
  "language": "de",
  "expires_at": "2026-12-21T11:15:12Z",
  "passport_url": "http://localhost:8000/api/passport/dPOIECxNy_bEknDiY4whcQ"
}
```

`GET /api/passport/{token}` returns the PDF (`?lang=` overrides the language), or `404` if the
token is unknown or expired.

---

## Patients

All demo patients are **simulated** (`"simulated": true`). Uploading with a new `patient_ref`
creates a minimal patient automatically.

### GET /api/patients?country=RO&q=pop

```json
[
  {
    "patient_ref": "EU-RO-001",
    "full_name": "Elena Popescu",
    "birth_year": 1961,
    "sex": "F",
    "country": "RO",
    "language": "ro",
    "diabetes_type": "Type 2",
    "phone": "+40 000 123 456",
    "email": "elena.popescu@example.com",
    "simulated": true,
    "created_at": "2025-06-02T09:00:00Z",
    "screenings": 2,
    "last_case_id": "c_0031",
    "last_screened_at": "2026-11-19T09:15:10Z",
    "last_triage_level": "referable",
    "open_followups": 1
  }
]
```

### POST /api/patients

```json
{ "patient_ref": "RO-123", "full_name": "Ana Ionescu", "birth_year": 1970, "sex": "F",
  "country": "RO", "language": "ro", "diabetes_type": "Type 2" }
```

`201` → patient. `409` if it already exists; `400` for an unsupported language.

### GET /api/patients/{ref}

`{"patient": {...}, "cases": [CaseSummary, ... newest first], "followups": [Followup, ...]}`.
This is the longitudinal view: every screening and every referral of one patient.

### PATCH /api/patients/{ref}

Any subset of the POST fields (except `patient_ref`).

---

## Follow-ups

Status lifecycle:

```
pending ──book appointment──▶ scheduled ──▶ attended
   │                              │
   │                              └─ appointment passed by >24h, not confirmed ─▶ unconfirmed ─▶ attended | missed (staff)
   └──────────── any open status ─▶ cancelled
```

A passed appointment is **never** marked `missed` automatically.

`overdue` (computed) = `status == "pending"` and past `due_date`. `days_until_due` is negative
when overdue.

### GET /api/followups

Query params:
- `status`
- `type` (`referral`, `rescreen`, `retake` or `clinician_review`)
- `patient_ref`
- `overdue=true|false`
- `open=true` (pending, scheduled or missed)
- `limit`

Sorted by what needs attention first: **missed → overdue → upcoming by due date → closed**.
Each item has the shape of `case.followup` above, including `patient_name`, `country` and `language`
for the worklist.

### PATCH /api/followups/{id}

```json
{ "appointment_at": "2026-12-01T09:30:00Z" }          // books it -> "scheduled"
{ "status": "attended" }                               // or "missed", "cancelled", "pending"
{ "note": "Called patient, will come next week" }
```

`400` if `appointment_at` is not ISO-8601, `404` if unknown.

### POST /api/followups/{id}/remind

**Simulated**: nothing is actually sent. The response contains the SMS text in the patient's language
and increments `reminders_sent`. Returns `400` if the follow-up is already attended or cancelled.

```json
{
  "followup": { "followup_id": "f_0017", "reminders_sent": 1, "...": "..." },
  "channel": "sms",
  "language": "ro",
  "message": "Bună ziua, Mihai Stan. Vă reamintim de la serviciul de screening oftalmologic: Trimitere la specialist, termen 05.12.2026. Vă rugăm să ne contactați pentru a programa sau confirma consultația.",
  "simulated": true
}
```

---

## Dashboard

### GET /api/dashboard

```json
{
  "totals": { "patients": 30, "screenings": 50, "pending_review": 5, "open_referrals": 9 },
  "triage": { "urgent": 5, "review": 5, "referable": 15, "retake": 4, "routine": 21 },
  "followups": { "pending": 17, "scheduled": 2, "attended": 28, "missed": 4, "cancelled": 0, "overdue": 1 },
  "attendance_rate": 0.875,
  "by_country": [
    { "country": "DE", "patients": 4, "screenings": 8, "referable_or_urgent": 3, "missed": 2 }
  ],
  "monthly": [
    { "month": "2026-10", "screenings": 4, "referrals": 2 }
  ]
}
```

`attendance_rate` = attended / (attended + missed), or `null` if there's no data yet.
`by_country` uses ISO country codes, which you can feed to a map of Europe.

---

## Errors

Every error has the same body: `{"detail": "<human-readable string>"}`.

| Code | When |
|---|---|
| 400 | unsupported file type (not JPG/PNG), empty file, or image can't be decoded; bad language; bad `appointment_at`; reminding a closed follow-up |
| 404 | unknown case / sample / patient / follow-up / passport token, or heatmap of a case that failed quality |
| 409 | patient already exists |
| 413 | upload larger than `MAX_UPLOAD_MB` |
| 422 | missing/invalid fields (e.g. no `image`, `clinician_grade` = 7) |
| 500 | unexpected server error |
