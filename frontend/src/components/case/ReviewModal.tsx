import { useState } from "react";
import { Loader2, X } from "lucide-react";
import { reviewCase } from "../../api/cases";
import type { Case, ReviewStatus } from "../../types";
import { useToast } from "../ui/ToastProvider";

interface Props {
  caseData: Case;
  onClose: () => void;
  /** receives the updated case returned by the PATCH */
  onUpdated: (c: Case) => void;
}

export function ReviewModal({ caseData, onClose, onUpdated }: Props) {
  const [status, setStatus] = useState<ReviewStatus>(
    caseData.review.status === "reviewed" ? "reviewed" : "pending",
  );
  const [grade, setGrade] = useState<string>(
    caseData.review.clinician_grade != null ? String(caseData.review.clinician_grade) : "",
  );
  const [note, setNote] = useState(caseData.review.note ?? "");
  const [busy, setBusy] = useState(false);
  const { push } = useToast();

  async function save() {
    setBusy(true);
    try {
      const updated = await reviewCase(caseData.case_id, {
        status,
        clinician_grade: grade === "" ? null : Number(grade),
        note: note.trim() === "" ? null : note.trim(),
      });
      onUpdated(updated);
      push(
        status === "reviewed" ? "Case marked as reviewed" : "Review status reset to pending",
        "success",
      );
      onClose();
    } catch (e) {
      push(e instanceof Error ? e.message : "Review failed", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 p-4 backdrop-blur-sm"
      onClick={busy ? undefined : onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Clinician review"
    >
      <div
        className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Clinician review</h2>
            <p className="mt-0.5 font-mono text-xs text-slate-400">{caseData.case_id}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            aria-label="Close"
            className="grid size-8 place-items-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="mt-5 space-y-4">
          <label className="block">
            <span className="text-xs font-medium text-slate-500">Status</span>
            <div className="mt-1.5 grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1">
              {(["pending", "reviewed"] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStatus(s)}
                  className={`rounded-lg py-1.5 text-xs font-semibold capitalize transition ${
                    status === s ? "bg-white text-slate-900 shadow-xs" : "text-slate-500"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </label>

          <label className="block">
            <span className="text-xs font-medium text-slate-500">
              Your grade (optional — if you disagree with the AI)
            </span>
            <div className="mt-1.5 flex gap-1">
              {["", "0", "1", "2", "3", "4"].map((g) => (
                <button
                  key={g || "none"}
                  type="button"
                  onClick={() => setGrade(g)}
                  className={`h-9 flex-1 rounded-lg text-xs font-semibold transition ${
                    grade === g
                      ? "bg-teal-700 text-white shadow-xs"
                      : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                  }`}
                >
                  {g === "" ? "—" : g}
                </button>
              ))}
            </div>
          </label>

          <label className="block">
            <span className="text-xs font-medium text-slate-500">Note</span>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={2000}
              rows={3}
              placeholder="e.g. Agree with grade 3 — refer this week"
              disabled={busy}
              className="mt-1.5 w-full resize-none rounded-xl border-0 bg-slate-100/80 px-3 py-2 text-sm text-slate-900 ring-1 ring-slate-200 transition placeholder:text-slate-400 focus:ring-2 focus:ring-teal-500 focus:outline-none"
            />
          </label>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-full px-4 py-2 text-xs font-semibold text-slate-500 transition hover:bg-slate-100"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void save()}
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-full bg-teal-700 px-5 py-2 text-xs font-semibold text-white shadow-md shadow-teal-700/15 transition hover:bg-teal-800 disabled:opacity-60"
          >
            {busy && <Loader2 className="size-3.5 animate-spin" />}
            Save review
          </button>
        </div>
      </div>
    </div>
  );
}
