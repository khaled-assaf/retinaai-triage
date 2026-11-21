import type { Case, CaseSummary, Eye, ReviewUpdate } from "../types";
import { api } from "./client";

/** Screening context sent with every analysis. symptoms: undefined = not asked,
 *  "none" = asked and none reported, or comma-separated symptom codes. */
export interface ScreeningContext {
  eye: Eye;
  symptoms?: string;
}

/** POST /api/analyze — multipart upload, returns the full case */
export function analyze(file: File, patientRef?: string, ctx?: ScreeningContext): Promise<Case> {
  const fd = new FormData();
  fd.append("image", file);
  if (patientRef) fd.append("patient_ref", patientRef);
  if (ctx) fd.append("eye", ctx.eye);
  if (ctx?.symptoms) fd.append("symptoms", ctx.symptoms);
  return api<Case>("/api/analyze", { method: "POST", body: fd });
}

/** GET /api/queue — sorted by urgency, newest first */
export function getQueue(
  params: { status?: "pending" | "reviewed"; limit?: number } = {},
): Promise<CaseSummary[]> {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.limit != null) q.set("limit", String(params.limit));
  const qs = q.toString();
  return api<CaseSummary[]>(`/api/queue${qs ? `?${qs}` : ""}`);
}

/** GET /api/cases/{id} */
export function getCase(id: string): Promise<Case> {
  return api<Case>(`/api/cases/${encodeURIComponent(id)}`);
}

/** PATCH /api/cases/{id} — clinician review */
export function reviewCase(id: string, update: ReviewUpdate): Promise<Case> {
  return api<Case>(`/api/cases/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
}
