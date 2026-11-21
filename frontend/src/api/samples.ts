import type { Case, Sample } from "../types";
import type { ScreeningContext } from "./cases";
import { api } from "./client";

/** GET /api/samples — demo images for the sample tray */
export function getSamples(): Promise<Sample[]> {
  return api<Sample[]>("/api/samples");
}

/** POST /api/samples/{id}/analyze — run the pipeline on a demo image (one click) */
export function analyzeSample(id: string, patientRef?: string, ctx?: ScreeningContext): Promise<Case> {
  const q = new URLSearchParams();
  if (patientRef) q.set("patient_ref", patientRef);
  if (ctx) q.set("eye", ctx.eye);
  if (ctx?.symptoms) q.set("symptoms", ctx.symptoms);
  const qs = q.toString();
  return api<Case>(`/api/samples/${encodeURIComponent(id)}/analyze${qs ? `?${qs}` : ""}`, { method: "POST" });
}
