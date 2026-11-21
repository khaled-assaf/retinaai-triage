import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { Copy, ExternalLink, Link2, X } from "lucide-react";
import { api } from "../../api/client";
import { roundTo100 } from "../../utils/scores";
import type { Case, ShareLink } from "../../types";
import { PASSPORT_LANGUAGES, PASSPORT_STRINGS, type PassportLang } from "../../i18n/passport";
import { useToast } from "../ui/ToastProvider";

interface Props {
  caseData: Case;
  onClose: () => void;
}

export function PassportPanel({ caseData, onClose }: Props) {
  const [lang, setLang] = useState<PassportLang>("en");
  const [qr, setQr] = useState<string | null>(null);
  const [share, setShare] = useState<ShareLink | null>(null);
  const { push } = useToast();

  /** Official passport, rendered by the backend (6 languages, history, follow-up, safety notes). */
  const serverPdfUrl = `${caseData.report_url ?? `/api/cases/${caseData.case_id}/report.pdf`}?lang=${lang}`;

  async function createShareLink() {
    try {
      const link = await api<ShareLink>(
        `/api/cases/${encodeURIComponent(caseData.case_id)}/share?lang=${lang}`,
        { method: "POST" },
      );
      setShare(link);
      // From now on the QR (preview + browser PDF) points to the public passport link.
      setQr(
        await QRCode.toDataURL(link.passport_url, {
          margin: 1,
          width: 160,
          color: { dark: "#0f172a", light: "#ffffff" },
        }),
      );
      push("Share link created", "success");
    } catch (e) {
      push(e instanceof Error ? e.message : "Could not create the share link", "error");
    }
  }

  useEffect(() => {
    setShare(null);
    QRCode.toDataURL(`${window.location.origin}/case/${caseData.case_id}`, {
      margin: 1,
      width: 160,
      color: { dark: "#0f172a", light: "#ffffff" },
    })
      .then(setQr)
      .catch(() => push("Could not generate the QR code", "error"));
  }, [caseData, push]);

  const t = PASSPORT_STRINGS[lang];
  const { prediction, triage } = caseData;

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-slate-950/40 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="European Retina Passport"
    >
      <div
        className="w-full max-w-xl rounded-3xl bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900">{t.title}</h2>
            <p className="mt-0.5 font-mono text-xs text-slate-400">
              {caseData.case_id} · {t.languageName}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="grid size-8 place-items-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Language picker */}
        <div className="mt-4 flex flex-wrap gap-1.5">
          {PASSPORT_LANGUAGES.map(({ code, label }) => (
            <button
              key={code}
              type="button"
              onClick={() => setLang(code)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                lang === code
                  ? "bg-teal-700 text-white shadow-xs"
                  : "bg-slate-100 text-slate-600 hover:bg-teal-50 hover:text-teal-800"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Live preview card (mirrors the PDF content) */}
        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 pb-3">
            <div>
              <p className="text-[11px] font-semibold tracking-wider text-teal-700 uppercase">
                {t.subtitle}
              </p>
              <p className="mt-0.5 font-mono text-xs text-slate-500">
                {t.reportId}: {caseData.case_id}
              </p>
            </div>
            <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 ring-1 ring-amber-200">
              {triage.label}
            </span>
          </div>

          <div className="mt-4 space-y-3">
            <div>
              <p className="text-[11px] font-medium text-slate-400 uppercase">{t.gradeLabel}</p>
              {prediction ? (
                <p className="mt-0.5 text-sm font-semibold text-slate-900">
                  {prediction.grade} — {t.severityLabels[prediction.grade]}{" "}
                  <span className="font-normal text-slate-400">
                    (AI model score {Math.max(...roundTo100(prediction.probabilities))}%)
                  </span>
                </p>
              ) : (
                <p className="mt-0.5 text-sm font-semibold text-slate-900">{t.qualityFailed}</p>
              )}
            </div>
            <div>
              <p className="text-[11px] font-medium text-slate-400 uppercase">{t.triageSection}</p>
              <p className="mt-0.5 text-sm text-slate-700">{triage.action}</p>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between border-t border-slate-200/80 pt-3 text-[11px] text-slate-400">
            <span>{t.disclaimer}</span>
            {qr && <img src={qr} alt="" className="size-12" />}
          </div>
        </div>

        {share && (
          <div className="mt-4 flex items-center gap-2 rounded-xl bg-teal-50 px-3 py-2 ring-1 ring-teal-200">
            <Link2 className="size-3.5 shrink-0 text-teal-700" />
            <a
              href={share.passport_url}
              target="_blank"
              rel="noreferrer"
              className="min-w-0 flex-1 truncate font-mono text-[11px] text-teal-800 underline"
            >
              {share.passport_url}
            </a>
            <button
              type="button"
              onClick={() => void navigator.clipboard?.writeText(share.passport_url).then(() => push("Link copied", "success"))}
              aria-label="Copy link"
              className="grid size-7 place-items-center rounded-full text-teal-700 hover:bg-teal-100"
            >
              <Copy className="size-3.5" />
            </button>
          </div>
        )}

        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-full px-4 py-2 text-xs font-semibold text-slate-500 transition hover:bg-slate-100"
          >
            Close
          </button>
          <button
            type="button"
            onClick={() => void createShareLink()}
            className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold text-teal-800 ring-1 ring-teal-300 transition hover:bg-teal-50"
          >
            <Link2 className="size-3.5" />
            Share link
          </button>
          <a
            href={serverPdfUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-full bg-teal-700 px-5 py-2 text-xs font-semibold text-white shadow-md shadow-teal-700/15 transition hover:bg-teal-800"
          >
            <ExternalLink className="size-3.5" />
            Open passport PDF
          </a>
        </div>
      </div>
    </div>
  );
}
