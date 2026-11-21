# Clinical safety design: TrustGate

RetinaAI Nexus is a **research prototype with simulated patients**. It is **not** clinically
validated, CE-marked or autonomous, and not for clinical use.

Decisions below come from the team's medical member (review of 2026-11-21) and are
implemented in code. The guideline sources he cited are listed at the end; the team has not
independently re-checked them.

## TrustGate: the core idea

When the AI is uncertain, the image is inadequate, or urgent symptoms are present, the system
**prevents false reassurance** and asks for the right human assessment.

| Check | Where | Values shown |
|---|---|---|
| Image quality | `services/quality.py` | Passed / Failed |
| Prediction confidence | `services/triage.py` + experimental thresholds | Acceptable for demo / Review flagged / Not assessed |
| Urgent symptom screening | asked at screening time | No warning reported / Warning reported / **Not collected** |
| Final workflow status | `reports/content.py` | Provisional / Human review / Retake / Urgent assessment / Clinician reviewed |

## Triage rules (`backend/app/services/triage.py`)

The first matching rule wins:

| # | Condition | Outcome | Follow-up due |
|---|---|---|---|
| 0 | **Urgent symptoms reported** (sudden vision loss, new curtain/shadow, new flashes/floaters, other acute) | **Emergency eye assessment**: overrides everything, even grade 0 or a poor image | same day |
| 1 | Image quality failed | Retake image | 7 days (internal target) |
| 2 | AI top score < 0.60, or top-2 scores within 0.15 | Needs clinician review | 48 h (internal target) |
| 3 | Grade 0–1 but ≥ 15% of score on grade ≥ 2 | **Clinician review** (experimental safety flag) | 48 h |
| 4 | Grade 2 but ≥ 25% of score on grade ≥ 3 | **Priority clinician review** (experimental safety flag) | 24 h |
| 5 | Grade 0 / 1 | Routine screening, rescreen in 12 months (provisional) | 365 days |
| 5 | Grade 2 | Non-urgent ophthalmology referral | referral issued within 3 weeks |
| 5 | Grade 3 | High-priority ophthalmology assessment | referral issued within 2 weeks |
| 5 | Grade 4 | Urgent ophthalmology referral | referral issued within 2 weeks |

- **Safety flags never create referrals on their own.** Per the medical review they are
  review flags, because the thresholds are experimental and uncalibrated.
- **Deadlines:**
  - NHS pathway: R3A referral within 2 weeks with consultation within 6 weeks; R2/M1 referral
    within 3 weeks with consultation within 13 weeks.
  - Our grades 0–4 are **not** NHS R grades; these are prototype targets.
  - The 48 h review and 7-day retake targets are internal operational targets, not guideline
    deadlines.
- **Grade 1:** usually 12 months; 6–12 months by individual risk and clinician assessment
  (`ROUTINE_RESCREEN_DAYS`).
- **Not handled by the AI:** suspected diabetic macular edema, pregnancy and other special
  circumstances need separate clinical consideration.

## Human oversight

- Every AI suggestion is **provisional** ("Pending clinician review") until a clinician reviews
  it. A failed image needs recapture instead of review ("Review not required by configured
  workflow").
- **Clinician decision supersedes the AI.** The clinical status becomes Confirmed (same grade)
  or Modified (different grade).
- **Nothing about the original AI result is lost:**
  - the AI prediction is never changed;
  - the original AI triage is kept in `triage.ai_triage`;
  - each review is written to the audit log (`GET /api/cases/{id}/audit`) with the old and new
    triage, the clinician's grade, the reason (the note) and a timestamp.
- **Reported urgent symptoms keep a case at "emergency"**, even after a clinician grades the image.

## Follow-up

- A booked appointment with no attendance confirmation 24 h later becomes
  **"Attendance unconfirmed"**, never "Missed" automatically. Staff then confirm attended or missed.
- **Reminders are simulated** (nothing is sent). They are written in the patient's preferred
  language. A real deployment must respect privacy, communication preferences and authorization.

## European Retina Passport (PDF)

- **Sections A–F:**
  - A · Patient & screening
  - B · Screening result: AI-suggested triage, and the clinical status kept separate from it
  - C · Retinal imaging
  - D · Model output
  - E · TrustGate & next steps, with "Why was this action suggested?"
  - F · Screening history
- **Footer (traceability):** case ID, model, generation timestamp and clinician review status.
- **Wording:**
  - "Provisional AI recommendation — pending clinician review" until a clinician reviews the case;
  - grade 0 reads "No signs of diabetic retinopathy detected by this screening model in the
    assessed image";
  - every report states that DME, glaucoma, retinal detachment and other diseases are not excluded;
  - every report carries the emergency warning.
- **Scores:** displayed so they total exactly 100% (largest-remainder rounding, display only),
  labelled "Model output scores (not calibrated clinical probabilities)", with the top one shown
  as "AI model score: N%".
- **Heatmap:**
  - labelled "AI attention map" with a note that it is not a validated lesion-localization map;
  - labelled "Simulated visualization" when produced by the mock model.
- **Eye and history:**
  - the eye is shown, or "Not recorded";
  - one image = one eye, so the report says the screening is incomplete until the fellow eye is
    assessed;
  - a history difference is shown as "verification suggested" and only compared for the same
    known eye; it never triggers escalation by itself.
- **Shared links** (expiring token, QR code) give a **pseudonymised copy**: name and year of birth hidden.
- **Languages:** EN and RO use the medical teammate's terminology; DE/FR/ES/IT are drafts. All
  decisions are computed once (`reports/content.py`) and only the wording differs. Tests check
  that EN and RO produce identical decisions.

## Known limitations (state these in the demo)

1. Training data are limited to APTOS; generalizability to other populations and cameras is unknown.
2. No independent external or prospective clinical validation.
3. Image gradability assessment and model confidence are not clinically validated.
4. The system cannot reliably rule out diabetic macular edema or other eye diseases; additional
   examination or OCT may be needed.
5. Moderate/severe classification errors and missed referable cases remain. On the validation set,
   **7 referable cases** were still classed routine and **11 severe cases** were not escalated to
   urgent or review. This is a research prototype, not an approved clinical diagnostic system.

Before any clinical use, the model and thresholds would need:
- calibration;
- sensitivity for referable DR (grade ≥ 2) and severe DR (grade ≥ 3), with false-negative rates;
- external validation;
- an assessment of clinician review capacity (~18% of images on the validation set).

## References cited by the medical teammate

- ADA Standards of Care in Diabetes 2026, Section 12 (Retinopathy): https://diabetesjournals.org/care/article-lookup/doi/10.2337/dc26-S012
- AAO Diabetic Retinopathy Preferred Practice Pattern: https://www.aao.org/Assets/1a9b5c9b-5287-4c20-9f1e-e15d8db146f3/638899222720700000/diabetic-retinopathy-ppp-8-4-25-pdf
- ICO Guidelines for Diabetic Eye Care
- NHS Diabetic Eye Screening care pathway: https://www.gov.uk/government/publications/diabetic-eye-screening-care-pathway/diabetic-eye-screening-des-care-pathway
