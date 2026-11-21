import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileImage, Loader2, ScanEye, UploadCloud, X } from "lucide-react";
import { analyze } from "../../api/cases";
import { useToast } from "../ui/ToastProvider";

const MAX_BYTES = 10 * 1024 * 1024; // MAX_UPLOAD_MB on the backend
const ACCEPTED_TYPES = ["image/jpeg", "image/png"];

export function UploadCard() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [patientRef, setPatientRef] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { push } = useToast();

  /** Validate and accept a picked/dropped file. */
  function pick(f: File | undefined | null) {
    if (!f) return;
    if (!ACCEPTED_TYPES.includes(f.type)) {
      push("Only JPG or PNG images are accepted", "error");
      return;
    }
    if (f.size > MAX_BYTES) {
      push("Image must be under 10 MB", "error");
      return;
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(f);
    setPreviewUrl(URL.createObjectURL(f));
  }

  function clear() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(null);
    setPreviewUrl(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  async function submit() {
    if (!file || busy) return;
    setBusy(true);
    try {
      const c = await analyze(file, patientRef.trim() || undefined);
      navigate(`/case/${c.case_id}`);
    } catch (e) {
      push(e instanceof Error ? e.message : "Analysis failed", "error");
      setBusy(false); // on success we navigate away — nothing to reset
    }
  }

  return (
    <section className="rounded-3xl bg-white/75 p-6 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm">
      <div>
        <h2 className="text-sm font-semibold text-slate-900">Upload a fundus image</h2>
        <p className="mt-0.5 text-xs text-slate-500">
          JPG or PNG, up to 10 MB · one retinal photo per analysis
        </p>
      </div>

      {!previewUrl ? (
        <div
          role="button"
          tabIndex={0}
          aria-label="Upload a retinal fundus image"
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            pick(e.dataTransfer.files[0]);
          }}
          className={`mt-4 grid cursor-pointer place-items-center rounded-2xl border-2 border-dashed p-10 text-center transition ${
            dragOver
              ? "border-teal-500 bg-teal-50/60"
              : "border-slate-300 bg-white/40 hover:border-teal-400 hover:bg-teal-50/30"
          }`}
        >
          <span className="grid size-12 place-items-center rounded-2xl bg-teal-50 text-teal-700 ring-1 ring-teal-200/70">
            <UploadCloud className="size-6" />
          </span>
          <p className="mt-4 text-sm font-medium text-slate-700">
            Drag &amp; drop a retinal image, or{" "}
            <span className="text-teal-700 underline decoration-teal-300 underline-offset-2">
              browse files
            </span>
          </p>
          <p className="mt-1 text-xs text-slate-400">JPG or PNG · max 10 MB</p>
        </div>
      ) : (
        <div className="mt-4 flex flex-col gap-4 sm:flex-row">
          <div className="relative shrink-0">
            <img
              src={previewUrl}
              alt="Selected fundus photograph"
              className="h-32 w-48 rounded-2xl object-cover ring-1 ring-slate-200"
            />
            <button
              type="button"
              onClick={clear}
              disabled={busy}
              aria-label="Remove image"
              className="absolute -top-2 -right-2 grid size-6 place-items-center rounded-full bg-slate-900 text-white shadow-md transition hover:bg-slate-700 disabled:opacity-40"
            >
              <X className="size-3.5" />
            </button>
          </div>

          <div className="flex min-w-0 flex-1 flex-col justify-between gap-3">
            <div>
              <p className="flex items-center gap-1.5 truncate text-xs font-medium text-slate-700">
                <FileImage className="size-3.5 shrink-0 text-teal-700" />
                {file?.name}
              </p>
              <p className="mt-0.5 text-[11px] text-slate-400">
                {file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : ""}
              </p>
            </div>

            <label className="block">
              <span className="text-[11px] font-medium text-slate-500">
                Patient reference (optional)
              </span>
              <input
                value={patientRef}
                onChange={(e) => setPatientRef(e.target.value)}
                maxLength={100}
                placeholder="e.g. DEMO-042"
                disabled={busy}
                className="mt-1 w-full rounded-xl border-0 bg-slate-100/80 px-3 py-2 text-sm text-slate-900 ring-1 ring-slate-200 transition placeholder:text-slate-400 focus:ring-2 focus:ring-teal-500 focus:outline-none"
              />
            </label>

            <button
              type="button"
              onClick={() => void submit()}
              disabled={busy}
              className="inline-flex items-center justify-center gap-2 rounded-full bg-teal-700 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-teal-700/15 transition hover:bg-teal-800 disabled:opacity-60"
            >
              {busy ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <ScanEye className="size-4" />
              )}
              {busy ? "Analyzing retina…" : "Analyze image"}
            </button>
          </div>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png"
        className="hidden"
        onChange={(e) => pick(e.target.files?.[0])}
      />
    </section>
  );
}
