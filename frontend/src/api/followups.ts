/**
 * Follow-up tracking API — matches the backend contract in backend/app/schemas.py
 * (GET/PATCH /api/followups, POST /api/followups/{id}/remind).
 * Falls back to simulated fixtures (with localStorage overrides) when the
 * endpoint is unavailable, so the UI keeps working in offline development.
 */

import type { TriageLevel } from "../types";

export type FollowupStatus = "pending" | "scheduled" | "attended" | "missed" | "cancelled";
export type FollowupType = "referral" | "rescreen" | "retake" | "clinician_review";

export interface Followup {
  followup_id: string;
  case_id: string;
  patient_ref: string | null;
  patient_name: string | null;
  country: string | null;
  language: string;
  triage_level: TriageLevel | null;
  type: FollowupType;
  status: FollowupStatus;
  due_date: string; // YYYY-MM-DD
  days_until_due: number; // negative = days overdue
  overdue: boolean;
  appointment_at: string | null; // ISO-8601 datetime
  reminders_sent: number;
  last_reminder_at: string | null;
  note: string | null;
  resolved_case_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface FollowupsResult {
  items: Followup[];
  /** true when served from fixtures instead of the real API */
  simulated: boolean;
}

export interface FollowupPatch {
  status?: FollowupStatus;
  /** setting this without status implies "scheduled" on the backend */
  appointment_at?: string | null;
  note?: string | null;
}

const LS_OVERRIDES = "retinaai-followup-overrides";
const DAY = 24 * 60 * 60 * 1000;

const relDate = (days: number) => new Date(Date.now() + days * DAY).toISOString().slice(0, 10);
const relIso = (days: number) => new Date(Date.now() + days * DAY).toISOString();

/** Simulated cohort — dates relative to "today" so the demo always looks live. */
function seedFollowups(): Followup[] {
  type Row = [
    string, // patient name
    string, // patient ref
    string, // country
    string, // case
    FollowupType,
    FollowupStatus,
    number, // due in days (negative = overdue)
    number | null, // appointment in days
    string | null, // note
  ];
  const rows: Row[] = [
    ["Lena Hoffmann", "DEMO-007", "Germany", "c_0007", "referral", "scheduled", 12, 6, "Ophthalmology, Charité Berlin"],
    ["Jonas Bauer", "DEMO-001", "Germany", "c_0001", "referral", "pending", 10, null, null],
    ["Anna Gruber", "DEMO-004", "France", "c_0004", "referral", "missed", -2, -2, "Patient did not attend — call scheduled"],
    ["Marc Dupont", "DEMO-008", "France", "c_0008", "rescreen", "scheduled", 11, 4, null],
    ["Elena Ionescu", "DEMO-002", "Romania", "c_0002", "referral", "pending", -6, null, "Overdue — outreach team notified"],
    ["Petru Marin", "DEMO-005", "Romania", "c_0005", "referral", "attended", 0, -20, "Seen at Spitalul Universitar"],
    ["Sofia García", "DEMO-009", "Spain", "c_0009", "retake", "scheduled", 13, 9, null],
    ["Diego López", "DEMO-003", "Spain", "c_0003", "referral", "missed", -3, -1, "Rescheduling in progress"],
    ["Giulia Rossi", "DEMO-010", "Italy", "c_0010", "clinician_review", "scheduled", 8, 2, "Flagged for second opinion"],
    ["Luca Bianchi", "DEMO-011", "Italy", "c_0011", "rescreen", "attended", -15, -25, null],
  ];
  return rows.map(([name, ref, country, caseId, type, status, due, appt, note], i) => ({
    followup_id: `f_${String(i + 1).padStart(4, "0")}`,
    case_id: caseId,
    patient_ref: ref,
    patient_name: name,
    country,
    language: "en",
    triage_level: null,
    type,
    status,
    due_date: relDate(due),
    days_until_due: due,
    overdue: due < 0 && (status === "pending" || status === "missed"),
    appointment_at: appt === null ? null : relIso(appt),
    reminders_sent: status === "missed" ? 1 : 0,
    last_reminder_at: status === "missed" ? relIso(-1) : null,
    note,
    resolved_case_id: status === "attended" ? caseId : null,
    created_at: relIso(-30),
    updated_at: relIso(-1),
  }));
}

function loadOverrides(): Record<string, Partial<Followup>> {
  try {
    return JSON.parse(localStorage.getItem(LS_OVERRIDES) ?? "{}");
  } catch {
    return {};
  }
}

function saveOverrides(o: Record<string, Partial<Followup>>) {
  localStorage.setItem(LS_OVERRIDES, JSON.stringify(o));
}

function fixturesWithOverrides(): Followup[] {
  const overrides = loadOverrides();
  return seedFollowups().map((f) => ({ ...f, ...overrides[f.followup_id] }));
}

export async function getFollowups(): Promise<FollowupsResult> {
  try {
    const res = await fetch("/api/followups");
    if (!res.ok) throw new Error(String(res.status));
    return { items: (await res.json()) as Followup[], simulated: false };
  } catch {
    return { items: fixturesWithOverrides(), simulated: true };
  }
}

export async function updateFollowup(id: string, patch: FollowupPatch): Promise<Followup | null> {
  try {
    const res = await fetch(`/api/followups/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!res.ok) throw new Error(String(res.status));
    return (await res.json()) as Followup;
  } catch {
    const overrides = loadOverrides();
    overrides[id] = { ...(overrides[id] ?? {}), ...patch };
    saveOverrides(overrides);
    return fixturesWithOverrides().find((f) => f.followup_id === id) ?? null;
  }
}

/** POST /api/followups/{id}/remind — sends an SMS reminder. */
export async function remindFollowup(id: string): Promise<Followup | null> {
  try {
    const res = await fetch(`/api/followups/${encodeURIComponent(id)}/remind`, {
      method: "POST",
    });
    if (!res.ok) throw new Error(String(res.status));
    const body = (await res.json()) as { followup: Followup };
    return body.followup;
  } catch {
    const overrides = loadOverrides();
    const current = fixturesWithOverrides().find((f) => f.followup_id === id);
    if (!current) return null;
    const updated: Partial<Followup> = {
      reminders_sent: current.reminders_sent + 1,
      last_reminder_at: new Date().toISOString(),
    };
    overrides[id] = { ...(overrides[id] ?? {}), ...updated };
    saveOverrides(overrides);
    return { ...current, ...updated };
  }
}

/** Reset localStorage overrides (used by the "reset demo" button). */
export function resetFollowupOverrides() {
  localStorage.removeItem(LS_OVERRIDES);
}
