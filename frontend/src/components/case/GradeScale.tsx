import type { Prediction } from "../../types";
import { roundTo100 } from "../../utils/scores";

/* Full static class names so Tailwind sees them */
const SEGMENT = [
  "bg-triage-routine", // 0 No DR — green
  "bg-lime-500", // 1 Mild
  "bg-amber-400", // 2 Moderate
  "bg-orange-500", // 3 Severe
  "bg-triage-urgent", // 4 Proliferative — red
];

const NAMES = ["No DR", "Mild", "Moderate", "Severe", "Proliferative"];

/** The 0–4 DR severity strip with the predicted grade highlighted. */
export function GradeScale({ prediction }: { prediction: Prediction }) {
  return (
    <div className="rounded-3xl bg-white/75 p-6 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm">
      <div className="flex items-baseline justify-between">
        <p className="text-3xl font-semibold tracking-tight text-slate-900">
          AI grade {prediction.grade}
        </p>
        <p className="text-xs font-medium text-slate-400" title="Not a calibrated probability or diagnostic accuracy">
          AI model score: {Math.max(...roundTo100(prediction.probabilities))}%
        </p>
      </div>
      <p className="mt-0.5 text-sm text-slate-500">{prediction.label}</p>

      <div className="mt-4 flex gap-1">
        {SEGMENT.map((color, i) => (
          <div key={i} className="flex-1">
            <div
              className={`h-2 rounded-full transition-all ${
                i === prediction.grade ? color : `${color} opacity-25`
              }`}
            />
            <p
              className={`mt-1.5 text-center text-[10px] leading-tight ${
                i === prediction.grade ? "font-semibold text-slate-700" : "text-slate-400"
              }`}
            >
              {i}
            </p>
          </div>
        ))}
      </div>
      <p className="mt-1 text-center text-[10px] text-slate-400">
        Severity scale · {NAMES[prediction.grade]}
      </p>
    </div>
  );
}
