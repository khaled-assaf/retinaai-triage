import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { Quality } from "../../types";

function chipCls(ok: boolean) {
  return ok
    ? "bg-triage-routine/10 text-triage-routine ring-triage-routine/25"
    : "bg-triage-review/10 text-triage-review ring-triage-review/25";
}

const EXPOSURE_LABEL: Record<Quality["checks"]["exposure"], string> = {
  ok: "Exposure OK",
  underexposed: "Underexposed",
  overexposed: "Overexposed",
};

const FRAMING_LABEL: Record<Quality["checks"]["framing"], string> = {
  ok: "Framing OK",
  too_small: "Retina too small",
  not_found: "Retina not found",
};

/** Image-quality summary: verdict + blur/exposure/framing checks. */
export function QualityPanel({ quality }: { quality: Quality }) {
  const sharp = quality.checks.blur >= 0.5;
  return (
    <div className="rounded-3xl bg-white/75 p-6 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm">
      <div className="flex items-center gap-2">
        {quality.passed ? (
          <CheckCircle2 className="size-4 text-triage-routine" />
        ) : (
          <AlertTriangle className="size-4 text-triage-review" />
        )}
        <p className="text-xs font-semibold tracking-widest text-slate-400 uppercase">
          Image quality
        </p>
        <span className="ml-auto text-xs font-semibold tabular-nums text-slate-500">
          {(quality.score * 100).toFixed(0)}/100
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ${chipCls(sharp)}`}>
          Blur {quality.checks.blur.toFixed(2)}
        </span>
        <span
          className={`rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ${chipCls(quality.checks.exposure === "ok")}`}
        >
          {EXPOSURE_LABEL[quality.checks.exposure]}
        </span>
        <span
          className={`rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ${chipCls(quality.checks.framing === "ok")}`}
        >
          {FRAMING_LABEL[quality.checks.framing]}
        </span>
      </div>

      {!quality.passed && (
        <p className="mt-3 text-xs leading-relaxed text-slate-500">{quality.reason}</p>
      )}
    </div>
  );
}
