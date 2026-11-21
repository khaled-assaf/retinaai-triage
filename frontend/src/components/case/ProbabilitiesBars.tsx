import type { Prediction } from "../../types";

/** Five horizontal probability bars (grades 0–4). No chart library needed. */
export function ProbabilitiesBars({ prediction }: { prediction: Prediction }) {
  return (
    <div className="rounded-3xl bg-white/75 p-6 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm">
      <p className="text-xs font-semibold tracking-widest text-slate-400 uppercase">
        Grade probabilities
      </p>
      <div className="mt-4 space-y-2.5">
        {prediction.probabilities.map((p, grade) => {
          const pct = Math.round(p * 100);
          const isTop = grade === prediction.grade;
          return (
            <div key={grade} className="flex items-center gap-3">
              <span
                className={`w-28 shrink-0 text-right text-xs ${
                  isTop ? "font-semibold text-slate-800" : "text-slate-400"
                }`}
              >
                {grade} · {["No DR", "Mild", "Moderate", "Severe", "Proliferative"][grade]}
              </span>
              <div className="h-5 flex-1 overflow-hidden rounded-md bg-slate-100">
                <div
                  className={`h-full rounded-md ${
                    isTop ? "bg-teal-600" : "bg-slate-300"
                  } transition-[width] duration-500`}
                  style={{ width: `${Math.max(pct, 2)}%` }}
                />
              </div>
              <span
                className={`w-10 text-right text-xs tabular-nums ${
                  isTop ? "font-semibold text-teal-700" : "text-slate-400"
                }`}
              >
                {pct}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
