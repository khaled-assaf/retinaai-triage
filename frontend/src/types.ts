/**
 * API types — mirror backend/app/schemas.py exactly (snake_case, optional nulls).
 * Source of truth: docs/API.md. Keep in sync when the contract changes.
 */

export type TriageLevel = "urgent" | "review" | "referable" | "retake" | "routine";
export type ReviewStatus = "pending" | "reviewed";

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
}

export interface Review {
  status: ReviewStatus;
  clinician_grade: number | null;
  note: string | null;
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
  triage: Triage;
  review: Review;
  model_version: string;
  processing_ms: number;
  disclaimer: string;
}

/** Queue row, as returned by GET /api/queue */
export interface CaseSummary {
  case_id: string;
  created_at: string;
  patient_ref: string | null;
  triage_level: TriageLevel;
  triage_label: string;
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
