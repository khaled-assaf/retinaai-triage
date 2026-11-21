import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ClipboardCheck, FileCheck2 } from "lucide-react";
import { getCase } from "../api/cases";
import type { Case } from "../types";
import { GradeScale } from "../components/case/GradeScale";
import { HeatmapViewer } from "../components/case/HeatmapViewer";
import { ProbabilitiesBars } from "../components/case/ProbabilitiesBars";
import { QualityPanel } from "../components/case/QualityPanel";
import { RetakeCard } from "../components/case/RetakeCard";
import { ReviewModal } from "../components/case/ReviewModal";
import { TriageBadge } from "../components/case/TriageBadge";
import { PassportPanel } from "../components/passport/PassportPanel";
import { Spinner } from "../components/ui/Spinner";

export default function CaseResultPage() {
  const { id } = useParams<{ id: string }>();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showReview, setShowReview] = useState(false);
  const [showPassport, setShowPassport] = useState(false);

  useEffect(() => {
    if (!id) return;
    setCaseData(null);
    setError(null);
    getCase(id)
      .then(setCaseData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load case"));
  }, [id]);

  if (error) {
    return (
      <section className="mx-auto max-w-2xl">
        <div className="rounded-2xl bg-red-50/80 p-6 text-center ring-1 ring-red-200">
          <p className="text-sm font-medium text-red-700">{error}</p>
          <Link
            to="/queue"
            className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-red-700 underline underline-offset-2"
          >
            <ArrowLeft className="size-3.5" /> Back to the queue
          </Link>
        </div>
      </section>
    );
  }

  if (!caseData) {
    return (
      <section className="mx-auto mt-16 max-w-2xl">
        <Spinner label="Loading case…" />
      </section>
    );
  }

  const { quality, prediction, triage, review } = caseData;

  return (
    <section className="mx-auto max-w-6xl">
      {/* Header */}
      <div className="flex items-start gap-3">
        <Link
          to="/queue"
          aria-label="Back to the triage queue"
          className="mt-1 grid size-9 shrink-0 place-items-center rounded-full bg-white/75 text-slate-500 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm transition hover:text-slate-900"
        >
          <ArrowLeft className="size-4" />
        </Link>
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Case <span className="font-mono text-lg text-slate-500">{caseData.case_id}</span>
            {review.status === "reviewed" && (
              <span className="ml-3 inline-flex items-center gap-1 rounded-full bg-triage-routine/10 px-2.5 py-0.5 align-middle text-[11px] font-semibold text-triage-routine ring-1 ring-triage-routine/25">
                <ClipboardCheck className="size-3" /> reviewed
              </span>
            )}
          </h1>
          <p className="mt-0.5 truncate text-xs text-slate-500">
            {caseData.patient_ref ? `${caseData.patient_ref} · ` : ""}
            {new Date(caseData.created_at).toLocaleString()} · {caseData.model_version} ·{" "}
            {caseData.processing_ms} ms
          </p>
        </div>
        <div className="mt-0.5 flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => setShowPassport(true)}
            className="inline-flex items-center gap-2 rounded-full bg-white/75 px-4 py-2 text-xs font-semibold text-slate-600 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm transition hover:text-teal-800 hover:ring-teal-300"
          >
            <FileCheck2 className="size-3.5" />
            Passport
          </button>
          <button
            type="button"
            onClick={() => setShowReview(true)}
            className="inline-flex items-center gap-2 rounded-full bg-teal-700 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-teal-700/15 transition hover:bg-teal-800"
          >
            <ClipboardCheck className="size-3.5" />
            Review
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="mt-6 grid items-start gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <HeatmapViewer imageUrl={caseData.image_url} heatmapUrl={caseData.heatmap_url} />
          <div className="mt-4 lg:col-span-7">
            <QualityPanel quality={quality} />
          </div>
        </div>

        <div className="space-y-4 lg:col-span-5">
          <TriageBadge triage={triage} />

          {prediction ? (
            <>
              <GradeScale prediction={prediction} />
              <ProbabilitiesBars prediction={prediction} />
            </>
          ) : (
            <RetakeCard quality={quality} />
          )}

          {review.note && (
            <div className="rounded-3xl bg-white/75 p-5 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm">
              <p className="text-[11px] font-semibold tracking-widest text-slate-400 uppercase">
                Clinician note
              </p>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{review.note}</p>
              {review.clinician_grade != null && (
                <p className="mt-1.5 text-xs text-slate-400">
                  Clinician grade: {review.clinician_grade}
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {showReview && (
        <ReviewModal
          caseData={caseData}
          onClose={() => setShowReview(false)}
          onUpdated={setCaseData}
        />
      )}

      {showPassport && <PassportPanel caseData={caseData} onClose={() => setShowPassport(false)} />}
    </section>
  );
}
