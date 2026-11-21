import type { Prediction } from "../../types";
import { roundTo100 } from "../../utils/scores";

/** Five horizontal score bars (grades 0–4). Displayed values always total 100%. */
export function ProbabilitiesBars({ prediction }: { prediction: Prediction }) {
  const pcts = roundTo100(prediction.probabilities);
  return (
    <div className="rounded-3xl bg-white/75 p-6 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm">
      <p className="text-xs font-semibold tracking-widest text-slate-400 uppercase">
        Model output scores
      </p>
      <p className="mt-0.5 text-[11px] text-slate-400">Not calibrated clinical probabilities</p>
      <div className="mt-4 space-y-2.5">
        {pcts.map((pct, grade) => {
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
