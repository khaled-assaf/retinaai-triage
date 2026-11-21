/**
 * API types — mirror backend/app/schemas.py exactly (snake_case, optional nulls).
 * Source of truth: docs/API.md. Keep in sync when the contract changes.
 */

import type { Followup } from "./api/followups";

export type TriageLevel = "emergency" | "urgent" | "review" | "referable" | "retake" | "routine";
export type ReviewStatus = "pending" | "reviewed";
/** pending_review = the AI suggestion is PROVISIONAL until a clinician reviews it */
export type ClinicalStatus = "pending_review" | "confirmed" | "modified" | "not_required";
export type Eye = "right" | "left" | "unknown";
export type Symptom = "sudden_vision_loss" | "curtain_shadow" | "flashes_floaters" | "other_acute";

/** Urgent symptoms that override the AI result (backend triage.py URGENT_SYMPTOMS). */
export const SYMPTOM_LABELS: Record<Symptom, string> = {
  sudden_vision_loss: "Sudden vision loss",
  curtain_shadow: "New curtain or shadow over vision",
  flashes_floaters: "New flashes or floaters",
  other_acute: "Other serious acute eye symptom",
};

export const EYE_LABELS: Record<Eye, string> = {
  right: "Right eye (OD)",
  left: "Left eye (OS)",
  unknown: "Eye not recorded",
};

export const CLINICAL_STATUS_LABELS: Record<ClinicalStatus, string> = {
  pending_review: "Pending clinician review",
  confirmed: "Clinician confirmed",
  modified: "Clinician modified",
  not_required: "Review not required (image must be retaken)",
};

/** Shown on every result, whatever the AI says (medical teammate requirement). */
export const EMERGENCY_NOTE =
  "Sudden vision loss, new flashes or floaters, or a dark curtain over vision requires urgent eye assessment, regardless of the AI result.";
export const LIMITS_NOTE =
  "This screening does not exclude diabetic macular edema, glaucoma, retinal detachment, or other eye diseases. Additional ophthalmological examination or OCT may be required.";

export const GRADE_LABELS = [
  "No DR",
  "Mild NPDR",
  "Moderate NPDR",
  "Severe NPDR",
  "Proliferative DR",
] as const;

export const DISCLAIMER = "Research prototype. Not for clinical diagnosis.";

export interface QualityChecks {
  /** Sharpness score 0..1, higher is sharper */
  blur: number;
  exposure: "ok" | "underexposed" | "overexposed";
  framing: "ok" | "too_small" | "not_found";
}

export interface Quality {
  passed: boolean;
  score: number; // 0..1
  reason: string; // "OK" or human-readable failure(s)
  checks: QualityChecks;
}

export interface Prediction {
  grade: number; // 0..4
  label: string;
  confidence: number; // 0..1
  probabilities: number[]; // length 5
}

export interface Triage {
  level: TriageLevel;
  label: string;
  action: string;
  /** Why this level was chosen, e.g. "Uncertain: confidence 0.43 is below the 0.60 threshold" */
  reason?: string | null;
  /** "clinician" once a clinician's grade has overridden the AI */
  source?: "ai" | "clinician";
  /** Set when an experimental safety flag sent the case to clinician review (backend triage.py) */
  safety_rule?: "referable" | "urgent" | null;
  /** Outcome code, e.g. "urgent_grade3", "review_priority" */
  action_code?: string;
  /** "priority" = priority clinician review */
  review_priority?: "priority" | null;
  /** Urgent symptoms that triggered "emergency" */
  symptoms?: Symptom[];
  /** The original AI triage, kept after a clinician override */
  ai_triage?: Partial<Triage> | null;
}

export interface Review {
  status: ReviewStatus;
  clinician_grade: number | null;
  note: string | null;
  reviewed_at?: string | null;
}

/** Full case, as returned by POST /api/analyze and GET /api/cases/{id} */
export interface Case {
  case_id: string;
  created_at: string;
  patient_ref: string | null;
  quality: Quality;
  /** null when quality check failed */
  prediction: Prediction | null;
  /** null when quality check failed */
  heatmap_url: string | null;
  image_url: string;
  eye?: Eye;
  /** collected=false: urgent symptoms were not asked */
  symptoms?: { collected: boolean; reported: Symptom[] };
  triage: Triage;
  review: Review;
  clinical_status?: ClinicalStatus;
  model_version: string;
  processing_ms: number;
  /** Server-side European Retina Passport PDF, add ?lang=ro etc. */
  report_url?: string;
  /** The follow-up task this case created (referral, rescreen, retake, clinician review) */
  followup?: Followup | null;
  disclaimer: string;
}

/** POST /api/cases/{id}/share */
export interface ShareLink {
  token: string;
  case_id: string;
  language: string;
  expires_at: string;
  /** Public PDF link (absolute; uses the backend's PUBLIC_BASE_URL) */
  passport_url: string;
}

/** Queue row, as returned by GET /api/queue */
export interface CaseSummary {
  case_id: string;
  created_at: string;
  patient_ref: string | null;
  triage_level: TriageLevel;
  triage_label: string;
  review_priority?: "priority" | null;
  action_code?: string | null;
  eye?: Eye;
  clinical_status?: ClinicalStatus;
  grade: number | null;
  grade_label: string | null;
  confidence: number | null;
  quality_passed: boolean;
  review_status: ReviewStatus;
  thumbnail_url: string;
}

/** Body for PATCH /api/cases/{id} */
export interface ReviewUpdate {
  status: ReviewStatus;
  clinician_grade?: number | null;
  note?: string | null;
}

export interface Sample {
  id: string;
  label: string;
  image_url: string;
  expected_grade: number | null;
  description: string | null;
}

export interface Health {
  status: "ok";
  model_loaded: boolean;
  mock: boolean;
  model_version: string;
}
