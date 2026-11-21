import { Ambulance, Eye as EyeIcon } from "lucide-react";
import type { ScreeningContext } from "../../api/cases";
import { EYE_LABELS, SYMPTOM_LABELS, type Eye, type Symptom } from "../../types";

export type SymptomMode = "not_asked" | "none" | "present";

export interface ContextState {
  eye: Eye;
  mode: SymptomMode;
  symptoms: Symptom[];
}

export const INITIAL_CONTEXT: ContextState = { eye: "unknown", mode: "not_asked", symptoms: [] };

/** Convert the form state to what the API expects (null = invalid: "present" without a symptom). */
export function toApiContext(c: ContextState): ScreeningContext | null {
  if (c.mode === "present" && c.symptoms.length === 0) return null;
  const symptoms = c.mode === "not_asked" ? undefined : c.mode === "none" ? "none" : c.symptoms.join(",");
  return { eye: c.eye, symptoms };
}

/** Eye laterality + urgent-symptom screening, applied to uploads AND demo samples. */
export function ScreeningContextCard({
  value,
  onChange,
  disabled,
}: {
  value: ContextState;
  onChange: (v: ContextState) => void;
  disabled?: boolean;
}) {
  const btn = (active: boolean) =>
    `rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
      active ? "bg-teal-700 text-white shadow-xs" : "bg-slate-100 text-slate-600 hover:bg-teal-50 hover:text-teal-800"
    }`;
  return (
    <section className="rounded-3xl bg-white/75 p-5 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm">
      <div className="grid gap-5 md:grid-cols-2">
        <div>
          <p className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
            <EyeIcon className="size-3.5 text-teal-700" /> Which eye is this photo?
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {(["right", "left", "unknown"] as Eye[]).map((e) => (
              <button
                key={e}
                type="button"
                disabled={disabled}
                onClick={() => onChange({ ...value, eye: e })}
                className={btn(value.eye === e)}
              >
                {e === "unknown" ? "Not recorded" : EYE_LABELS[e]}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-[11px] text-slate-400">
            One photo = one eye. The report says the screening is incomplete until the fellow eye is assessed.
          </p>
        </div>

        <div>
          <p className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
            <Ambulance className="size-3.5 text-triage-emergency" /> Urgent eye symptoms?
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {(
              [
                ["not_asked", "Not asked"],
                ["none", "None reported"],
                ["present", "Yes"],
              ] as [SymptomMode, string][]
            ).map(([m, label]) => (
              <button
                key={m}
                type="button"
                disabled={disabled}
                onClick={() => onChange({ ...value, mode: m, symptoms: m === "present" ? value.symptoms : [] })}
                className={btn(value.mode === m)}
              >
                {label}
              </button>
            ))}
          </div>
          {value.mode === "present" && (
            <div className="mt-2 space-y-1 rounded-xl bg-red-50/70 p-2.5 ring-1 ring-red-200">
              {(Object.keys(SYMPTOM_LABELS) as Symptom[]).map((s) => (
                <label key={s} className="flex items-center gap-2 text-xs text-red-900">
                  <input
                    type="checkbox"
                    disabled={disabled}
                    checked={value.symptoms.includes(s)}
                    onChange={(ev) =>
                      onChange({
                        ...value,
                        symptoms: ev.target.checked
                          ? [...value.symptoms, s]
                          : value.symptoms.filter((x) => x !== s),
                      })
                    }
                  />
                  {SYMPTOM_LABELS[s]}
                </label>
              ))}
              <p className="pt-1 text-[11px] font-medium text-red-800">
                Any urgent symptom overrides the AI result: emergency eye assessment, same day.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
