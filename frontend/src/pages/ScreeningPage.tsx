import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { analyzeSample, getSamples } from "../api/samples";
import { useToast } from "../components/ui/ToastProvider";
import { Spinner } from "../components/ui/Spinner";
import { UploadCard } from "../components/screening/UploadCard";
import {
  INITIAL_CONTEXT,
  ScreeningContextCard,
  toApiContext,
  type ContextState,
} from "../components/screening/ScreeningContextCard";
import type { Sample } from "../types";

export default function ScreeningPage() {
  const [samples, setSamples] = useState<Sample[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [ctx, setCtx] = useState<ContextState>(INITIAL_CONTEXT);
  const navigate = useNavigate();
  const { push } = useToast();

  async function run(s: Sample) {
    const apiCtx = toApiContext(ctx);
    if (!apiCtx) {
      push("Select at least one urgent symptom, or choose 'None reported' / 'Not asked'", "error");
      return;
    }
    setBusyId(s.id);
    try {
      const c = await analyzeSample(s.id, undefined, apiCtx);
      navigate(`/case/${c.case_id}`);
    } catch (e) {
      push(e instanceof Error ? e.message : "Analysis failed", "error");
    } finally {
      setBusyId(null);
    }
  }

  useEffect(() => {
    getSamples()
      .then(setSamples)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load samples")
      );
  }, []);

  return (
    <section className="mx-auto max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Screening</h1>
        <p className="mt-1 text-sm text-slate-500">
          Upload a retinal fundus image or run a demo sample — the AI grades DR severity 0–4.
        </p>
      </div>
      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      <div className="mt-6">
        <ScreeningContextCard value={ctx} onChange={setCtx} disabled={busyId !== null} />
      </div>

      <div className="mt-4">
        <UploadCard context={() => toApiContext(ctx)} />
      </div>

      {!samples && !error && <p className="mt-4 text-sm text-slate-500">Loading samples...</p>}

      {samples && (
        <>
          <div className="mt-8 flex items-center gap-4" aria-hidden="true">
            <div className="h-px flex-1 bg-slate-200/80" />
            <span className="text-[11px] font-medium text-slate-400">or try a demo image</span>
            <div className="h-px flex-1 bg-slate-200/80" />
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {samples.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => void run(s)}
              disabled={busyId !== null}
              className="group overflow-hidden rounded-2xl bg-white text-left shadow-xs ring-1 ring-slate-200 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-teal-500/10 hover:ring-teal-400 disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:shadow-xs"
            >
              <img
                src={s.image_url}
                alt={s.label}
                className="h-32 w-full object-cover transition-transform duration-300 group-hover:scale-105"
              />
              <div className="p-2.5">
                {busyId === s.id ? (
                  <Spinner label="Analyzing…" />
                ) : (
                  <>
                    <p className="text-xs font-medium text-slate-700">{s.label}</p>
                    {s.expected_grade != null && (
                      <p className="mt-0.5 text-[11px] text-slate-400">
                        expected grade {s.expected_grade}
                      </p>
                    )}
                  </>
                )}
              </div>
            </button>
          ))}
          </div>
        </>
      )}
    </section>
  );
}
