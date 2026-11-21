import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bell,
  CalendarCheck2,
  CalendarClock,
  CircleCheck,
  RotateCcw,
  Siren,
} from "lucide-react";
import {
  getFollowups,
  remindFollowup,
  resetFollowupOverrides,
  updateFollowup,
  type Followup,
  type FollowupStatus,
  type FollowupType,
} from "../api/followups";
import { Spinner } from "../components/ui/Spinner";
import { useToast } from "../components/ui/ToastProvider";

const DAY = 24 * 60 * 60 * 1000;
const inDays = (n: number) => new Date(Date.now() + n * DAY).toISOString();

const STATUS_PILL: Record<FollowupStatus, string> = {
  pending: "bg-slate-100 text-slate-600 ring-slate-200",
  scheduled: "bg-teal-50 text-teal-700 ring-teal-200",
  attended: "bg-triage-routine/10 text-triage-routine ring-triage-routine/25",
  missed: "bg-triage-urgent/10 text-triage-urgent ring-triage-urgent/30",
  cancelled: "bg-slate-100 text-slate-400 ring-slate-200 line-through",
};

const TYPE_LABEL: Record<FollowupType, string> = {
  referral: "referral",
  rescreen: "rescreen",
  retake: "retake",
  clinician_review: "review",
};

const fmtDate = (d: string | null) =>
  d ? new Date(d).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "—";
const fmtWhen = (d: string | null) =>
  d
    ? new Date(d).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
    : "—";

function ActionButton({
  label,
  onClick,
  busy,
}: {
  label: string;
  onClick: () => void;
  busy: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600 shadow-xs ring-1 ring-slate-200 transition hover:text-teal-800 hover:ring-teal-300 disabled:opacity-50"
    >
      {label}
    </button>
  );
}

export default function FollowupsPage() {
  const [items, setItems] = useState<Followup[] | null>(null);
  const [simulated, setSimulated] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const { push } = useToast();

  const load = useCallback(async () => {
    try {
      const { items, simulated } = await getFollowups();
      setItems(items);
      setSimulated(simulated);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load follow-ups");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function replace(updated: Followup) {
    setItems((cur) => (cur ?? []).map((x) => (x.followup_id === updated.followup_id ? updated : x)));
  }

  async function act(f: Followup, fn: () => Promise<Followup | null>, msg: string) {
    setBusyId(f.followup_id);
    try {
      const updated = await fn();
      if (updated) {
        replace(updated);
        push(msg, "success");
      }
    } catch (e) {
      push(e instanceof Error ? e.message : "Update failed", "error");
    } finally {
      setBusyId(null);
    }
  }

  const stats = useMemo(() => {
    const list = items ?? [];
    return {
      pending: list.filter((f) => f.status === "pending").length,
      upcoming: list.filter(
        (f) => f.status === "scheduled" && f.days_until_due >= 0 && f.days_until_due <= 7,
      ).length,
      overdue: list.filter((f) => f.overdue).length,
      missed: list.filter((f) => f.status === "missed").length,
      attended: list.filter((f) => f.status === "attended").length,
    };
  }, [items]);

  return (
    <section className="mx-auto max-w-6xl">
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Follow-ups</h1>
          <p className="mt-1 text-sm text-slate-500">
            Referrals tracked until the patient is actually seen — no one falls through the cracks.
          </p>
        </div>
        {simulated && (
          <button
            type="button"
            onClick={() => {
              resetFollowupOverrides();
              void load();
            }}
            className="ml-auto flex items-center gap-1.5 rounded-full bg-white/75 px-3 py-1.5 text-xs font-medium text-slate-500 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm transition hover:text-slate-800"
          >
            <RotateCcw className="size-3.5" />
            Reset demo data
          </button>
        )}
      </div>

      {simulated && (
        <div className="mt-4 rounded-xl bg-teal-50/70 p-3 text-xs text-teal-800 ring-1 ring-teal-200/70">
          Simulated follow-up data — the API is unreachable, so status changes persist in your
          browser only.
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-xl bg-red-50/80 p-4 text-sm text-red-700 ring-1 ring-red-200">
          {error}
        </div>
      )}

      {!items && !error && (
        <div className="mt-8">
          <Spinner label="Loading follow-ups…" />
        </div>
      )}

      {items && (
        <>
          {/* KPI strip */}
          <div className="mt-5 grid grid-cols-2 gap-2 md:grid-cols-5">
            {[
              { icon: CalendarClock, label: "awaiting scheduling", value: stats.pending, cls: "text-slate-900" },
              { icon: CalendarCheck2, label: "upcoming 7 days", value: stats.upcoming, cls: "text-teal-700" },
              { icon: Siren, label: "overdue", value: stats.overdue, cls: "text-triage-review" },
              { icon: Siren, label: "missed", value: stats.missed, cls: "text-triage-urgent" },
              { icon: CircleCheck, label: "attended", value: stats.attended, cls: "text-triage-routine" },
            ].map(({ icon: Icon, label, value, cls }) => (
              <div
                key={label}
                className="rounded-2xl bg-white/75 p-3.5 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm"
              >
                <p className={`flex items-center gap-1.5 text-lg font-semibold ${cls}`}>
                  <Icon className="size-4" />
                  {value}
                </p>
                <p className="mt-0.5 text-[11px] text-slate-500">{label}</p>
              </div>
            ))}
          </div>

          {/* Table */}
          <div className="mt-4 overflow-hidden rounded-2xl bg-white/75 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200/80 text-left text-[11px] tracking-wider text-slate-400 uppercase">
                    <th className="px-4 py-3">Patient</th>
                    <th className="px-4 py-3">Case</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">Due</th>
                    <th className="px-4 py-3">Appointment</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((f) => (
                    <tr
                      key={f.followup_id}
                      className={`border-b border-slate-100/80 last:border-0 ${
                        f.status === "missed"
                          ? "bg-red-50/40"
                          : f.overdue
                            ? "bg-amber-50/40"
                            : ""
                      }`}
                    >
                      <td className="px-4 py-2.5">
                        <p className="font-medium text-slate-800">{f.patient_name ?? f.patient_ref ?? "—"}</p>
                        <p className="text-[11px] text-slate-400">
                          {f.patient_ref ?? ""} {f.country ? `· ${f.country}` : ""}
                        </p>
                      </td>
                      <td className="px-4 py-2.5">
                        <Link
                          to={`/case/${f.case_id}`}
                          className="font-mono text-xs text-teal-700 hover:underline"
                        >
                          {f.case_id}
                        </Link>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500 ring-1 ring-slate-200">
                          {TYPE_LABEL[f.type]}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        {f.overdue ? (
                          <span className="font-semibold text-triage-review">
                            {fmtDate(f.due_date)} · {Math.abs(f.days_until_due)}d overdue
                          </span>
                        ) : (
                          <span className="text-slate-600">{fmtDate(f.due_date)}</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-slate-600">{fmtWhen(f.appointment_at)}</td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${STATUS_PILL[f.status]}`}
                        >
                          {f.status}
                        </span>
                        {f.reminders_sent > 0 && (
                          <span className="ml-1.5 inline-flex items-center gap-0.5 text-[10px] text-slate-400">
                            <Bell className="size-3" />
                            {f.reminders_sent}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex flex-wrap justify-end gap-1.5">
                          {(f.status === "pending" || f.status === "missed") && (
                            <ActionButton
                              label="Schedule +7d"
                              busy={busyId === f.followup_id}
                              onClick={() =>
                                void act(
                                  f,
                                  () =>
                                    updateFollowup(f.followup_id, {
                                      status: "scheduled",
                                      appointment_at: inDays(7),
                                    }),
                                  `Appointment scheduled for ${f.patient_name ?? f.patient_ref ?? "patient"}`,
                                )
                              }
                            />
                          )}
                          {f.status === "scheduled" && (
                            <>
                              <ActionButton
                                label="Attended"
                                busy={busyId === f.followup_id}
                                onClick={() =>
                                  void act(
                                    f,
                                    () => updateFollowup(f.followup_id, { status: "attended" }),
                                    "Marked as attended",
                                  )
                                }
                              />
                              <ActionButton
                                label="Missed"
                                busy={busyId === f.followup_id}
                                onClick={() =>
                                  void act(
                                    f,
                                    () => updateFollowup(f.followup_id, { status: "missed" }),
                                    "Marked as missed",
                                  )
                                }
                              />
                            </>
                          )}
                          {f.status !== "attended" && f.status !== "cancelled" && (
                            <ActionButton
                              label="Remind"
                              busy={busyId === f.followup_id}
                              onClick={() =>
                                void act(
                                  f,
                                  () => remindFollowup(f.followup_id),
                                  "SMS reminder sent",
                                )
                              }
                            />
                          )}
                          {f.status === "attended" && (
                            <span className="text-[11px] text-triage-routine">✓ seen</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {items.length === 0 && (
              <p className="p-10 text-center text-sm text-slate-500">
                No follow-up records yet — urgent and referable cases create them.
              </p>
            )}
          </div>
        </>
      )}
    </section>
  );
}
