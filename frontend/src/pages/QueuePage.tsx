import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, CircleDashed, RefreshCw } from "lucide-react";
import { getQueue } from "../api/cases";
import type { CaseSummary, ReviewStatus, TriageLevel } from "../types";
import { Spinner } from "../components/ui/Spinner";
import { timeAgo } from "../utils/time";

const LEVELS: TriageLevel[] = ["urgent", "review", "referable", "retake", "routine"];

const LEVEL_CHIP: Record<TriageLevel, string> = {
  urgent: "bg-triage-urgent/10 text-triage-urgent ring-triage-urgent/30",
  review: "bg-triage-review/10 text-triage-review ring-triage-review/30",
  referable: "bg-triage-referable/10 text-triage-referable ring-triage-referable/30",
  retake: "bg-triage-retake/10 text-triage-retake ring-triage-retake/30",
  routine: "bg-triage-routine/10 text-triage-routine ring-triage-routine/30",
};

/* Full static class names so Tailwind's scanner sees them */
const LEVEL_TEXT: Record<TriageLevel, string> = {
  urgent: "text-triage-urgent",
  review: "text-triage-review",
  referable: "text-triage-referable",
  retake: "text-triage-retake",
  routine: "text-triage-routine",
};

const LEVEL_DOT: Record<TriageLevel, string> = {
  urgent: "bg-triage-urgent",
  review: "bg-triage-review",
  referable: "bg-triage-referable",
  retake: "bg-triage-retake",
  routine: "bg-triage-routine",
};

type StatusFilter = "all" | ReviewStatus;

export default function QueuePage() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [levelFilter, setLevelFilter] = useState<TriageLevel | null>(null);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      setCases(await getQueue());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load queue");
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const t = setInterval(() => {
      if (!document.hidden) void load();
    }, 20_000);
    return () => clearInterval(t);
  }, [load]);

  const counts = useMemo(() => {
    const map = new Map<TriageLevel, number>();
    for (const c of cases ?? []) map.set(c.triage_level, (map.get(c.triage_level) ?? 0) + 1);
    return map;
  }, [cases]);

  const reviewedPct = cases?.length
    ? Math.round((cases.filter((c) => c.review_status === "reviewed").length / cases.length) * 100)
    : 0;

  const filtered = useMemo(
    () =>
      (cases ?? []).filter(
        (c) =>
          (statusFilter === "all" || c.review_status === statusFilter) &&
          (levelFilter === null || c.triage_level === levelFilter),
      ),
    [cases, statusFilter, levelFilter],
  );

  return (
    <section className="mx-auto max-w-6xl">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Triage Queue</h1>
          <p className="mt-1 text-sm text-slate-500">
            Sorted by urgency · auto-refreshes every 20 s
          </p>
        </div>

        {/* Status filter */}
        <div className="ml-auto flex items-center gap-1 rounded-full bg-slate-100/90 p-1">
          {(["all", "pending", "reviewed"] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStatusFilter(s)}
              className={`rounded-full px-3.5 py-1.5 text-xs font-semibold capitalize transition ${
                statusFilter === s ? "bg-white text-slate-900 shadow-xs" : "text-slate-500"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => void load()}
          aria-label="Refresh queue"
          className="grid size-9 place-items-center rounded-full bg-white/75 text-slate-500 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm transition hover:text-slate-900"
        >
          <RefreshCw className={`size-4 ${refreshing ? "animate-spin" : ""}`} />
        </button>
      </div>

      {error && (
        <div className="mt-4 rounded-xl bg-red-50/80 p-4 text-sm text-red-700 ring-1 ring-red-200">
          {error}
        </div>
      )}

      {!cases && !error && (
        <div className="mt-8">
          <Spinner label="Loading queue…" />
        </div>
      )}

      {cases && (
        <>
          {/* Stat strip — click a level to filter */}
          <div className="mt-5 grid grid-cols-3 gap-2 md:grid-cols-7">
            <button
              type="button"
              onClick={() => setLevelFilter(null)}
              className={`rounded-2xl bg-white/75 p-3.5 text-left shadow-xs ring-1 backdrop-blur-sm transition ${
                levelFilter === null ? "ring-2 ring-teal-500" : "ring-slate-200/80 hover:ring-teal-300"
              }`}
            >
              <p className="text-lg font-semibold text-slate-900">{cases.length}</p>
              <p className="text-[11px] text-slate-500">all cases</p>
              <p className="mt-1 text-[10px] text-slate-400">{reviewedPct}% reviewed</p>
            </button>
            {LEVELS.map((level) => (
              <button
                key={level}
                type="button"
                onClick={() => setLevelFilter(levelFilter === level ? null : level)}
                className={`rounded-2xl bg-white/75 p-3.5 text-left shadow-xs ring-1 backdrop-blur-sm transition ${
                  levelFilter === level
                    ? "ring-2 ring-teal-500"
                    : "ring-slate-200/80 hover:ring-teal-300"
                }`}
              >
                <p className={`flex items-center gap-1.5 text-lg font-semibold ${LEVEL_TEXT[level]}`}>
                  <span className={`size-1.5 rounded-full ${LEVEL_DOT[level]}`} />
                  {counts.get(level) ?? 0}
                </p>
                <p className="text-[11px] text-slate-500 capitalize">{level}</p>
              </button>
            ))}
          </div>

          {/* Table */}
          <div className="mt-4 overflow-hidden rounded-2xl bg-white/75 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200/80 text-left text-[11px] tracking-wider text-slate-400 uppercase">
                    <th className="px-4 py-3">Case</th>
                    <th className="px-4 py-3">Patient</th>
                    <th className="px-4 py-3">Triage</th>
                    <th className="px-4 py-3">Grade</th>
                    <th className="px-4 py-3">Confidence</th>
                    <th className="px-4 py-3">Quality</th>
                    <th className="px-4 py-3">Review</th>
                    <th className="px-4 py-3">Age</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => (
                    <tr
                      key={c.case_id}
                      className="group border-b border-slate-100/80 last:border-0 hover:bg-teal-50/40"
                    >
                      <td className="px-4 py-2.5">
                        <Link to={`/case/${c.case_id}`} className="flex items-center gap-3">
                          <img
                            src={c.thumbnail_url}
                            alt=""
                            className="size-10 rounded-lg object-cover ring-1 ring-slate-200"
                          />
                          <span className="font-medium text-slate-800 transition group-hover:text-teal-800">
                            {c.case_id}
                          </span>
                        </Link>
                      </td>
                      <td className="px-4 py-2.5 text-slate-600">{c.patient_ref ?? "—"}</td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize ring-1 ${LEVEL_CHIP[c.triage_level]}`}
                        >
                          {c.triage_level}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-slate-600">
                        {c.grade != null ? (
                          <>
                            <span className="font-semibold text-slate-800">{c.grade}</span>
                            <span className="ml-1.5 text-xs text-slate-400">{c.grade_label}</span>
                          </>
                        ) : (
                          <span className="text-xs text-slate-400">— retake</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 tabular-nums text-slate-600">
                        {c.confidence != null ? `${(c.confidence * 100).toFixed(0)}%` : "—"}
                      </td>
                      <td className="px-4 py-2.5">
                        {c.quality_passed ? (
                          <span className="text-triage-routine">✓</span>
                        ) : (
                          <span className="text-triage-review">✗</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        {c.review_status === "reviewed" ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-triage-routine">
                            <CheckCircle2 className="size-3.5" /> reviewed
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400">
                            <CircleDashed className="size-3.5" /> pending
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-slate-400">
                        {timeAgo(c.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {filtered.length === 0 && (
              <p className="p-10 text-center text-sm text-slate-500">
                No cases match the current filters.
              </p>
            )}
          </div>
        </>
      )}
    </section>
  );
}
