import type { Case, Sample } from "../types";
import { api } from "./client";

/** GET /api/samples — demo images for the sample tray */
export function getSamples(): Promise<Sample[]> {
  return api<Sample[]>("/api/samples");
}

/** POST /api/samples/{id}/analyze — run the pipeline on a demo image (one click) */
export function analyzeSample(id: string, patientRef?: string): Promise<Case> {
  const q = patientRef ? `?patient_ref=${encodeURIComponent(patientRef)}` : "";
  return api<Case>(`/api/samples/${encodeURIComponent(id)}/analyze${q}`, { method: "POST" });
}
