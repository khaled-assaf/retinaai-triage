import {
  Ambulance,
  CalendarClock,
  Camera,
  ShieldCheck,
  Siren,
  Stethoscope,
  type LucideIcon,
} from "lucide-react";
import type { Triage, TriageLevel } from "../../types";

const ICONS: Record<TriageLevel, LucideIcon> = {
  emergency: Ambulance,
  urgent: Siren,
  review: Stethoscope,
  referable: CalendarClock,
  retake: Camera,
  routine: ShieldCheck,
};

const CHIP: Record<TriageLevel, string> = {
  emergency: "bg-triage-emergency/10 text-triage-emergency ring-triage-emergency/30",
  urgent: "bg-triage-urgent/10 text-triage-urgent ring-triage-urgent/30",
  review: "bg-triage-review/10 text-triage-review ring-triage-review/30",
  referable: "bg-triage-referable/10 text-triage-referable ring-triage-referable/30",
  retake: "bg-triage-retake/10 text-triage-retake ring-triage-retake/30",
  routine: "bg-triage-routine/10 text-triage-routine ring-triage-routine/30",
};

/* Full static class names so Tailwind's scanner sees them */
const BAR: Record<TriageLevel, string> = {
  emergency: "bg-triage-emergency",
  urgent: "bg-triage-urgent",
  review: "bg-triage-review",
  referable: "bg-triage-referable",
  retake: "bg-triage-retake",
  routine: "bg-triage-routine",
};

export function TriageBadge({ triage }: { triage: Triage }) {
  const Icon = ICONS[triage.level];

  return (
    <div className="relative overflow-hidden rounded-3xl bg-white/75 p-6 pt-5 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm">
      <span
        aria-hidden="true"
        className={`absolute inset-y-0 left-0 w-1.5 ${BAR[triage.level]}`}
      />
      <p className="mb-2 text-[11px] font-semibold tracking-widest text-slate-400 uppercase">
        {triage.source === "clinician" ? "Clinician decision" : "AI-suggested triage"}
      </p>
      <span
        className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ring-1 ${CHIP[triage.level]}`}
      >
        <Icon className="size-3.5" />
        {triage.label}
      </span>
      {triage.review_priority === "priority" && (
        <span className="ml-2 inline-flex items-center rounded-full bg-triage-review/10 px-2.5 py-1 text-[11px] font-semibold text-triage-review ring-1 ring-triage-review/30">
          priority
        </span>
      )}
      {triage.source === "clinician" && (
        <span className="ml-2 inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600 ring-1 ring-slate-200">
          set by clinician
        </span>
      )}
      <p className="mt-3 text-[15px] leading-relaxed font-medium text-slate-800">
        {triage.action}
      </p>
      {triage.reason && (
        <p
          className={`mt-2 rounded-xl px-3 py-2 text-xs leading-relaxed ${
            triage.safety_rule
              ? "bg-amber-50 font-medium text-amber-900 ring-1 ring-amber-200"
              : "bg-slate-50 text-slate-500"
          }`}
        >
          <span className="font-semibold">Why: </span>
          {triage.reason}
        </p>
      )}
    </div>
  );
}
