import { Link } from "react-router-dom";
import { Camera, Upload } from "lucide-react";
import type { Quality } from "../../types";

/** Shown instead of prediction panels when the quality gate failed. */
export function RetakeCard({ quality }: { quality: Quality }) {
  return (
    <div className="rounded-3xl bg-amber-50/70 p-6 shadow-xs ring-1 ring-amber-200/80 backdrop-blur-sm">
      <div className="flex items-center gap-2">
        <span className="grid size-9 place-items-center rounded-xl bg-amber-100 text-amber-700 ring-1 ring-amber-200">
          <Camera className="size-4.5" />
        </span>
        <div>
          <p className="text-sm font-semibold text-amber-900">Image quality too low</p>
          <p className="text-[11px] text-amber-700/80">No prediction was made</p>
        </div>
      </div>

      {quality.reason !== "OK" && (
        <p className="mt-3 rounded-xl bg-white/60 p-3 text-xs leading-relaxed text-amber-800 ring-1 ring-amber-200/60">
          {quality.reason}
        </p>
      )}

      <ul className="mt-3 space-y-1.5">
        {[
          "Check focus — the retinal vessels must be sharp",
          "Check lighting — avoid under- or over-exposed captures",
          "Center the retina so it fills most of the frame",
        ].map((tip) => (
          <li key={tip} className="flex gap-2 text-xs leading-relaxed text-amber-800/90">
            <span className="mt-1.5 size-1 shrink-0 rounded-full bg-amber-500" />
            {tip}
          </li>
        ))}
      </ul>

      <Link
        to="/screening"
        className="mt-4 inline-flex items-center gap-2 rounded-full bg-amber-600 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-amber-700"
      >
        <Upload className="size-3.5" />
        Upload a new image
      </Link>
    </div>
  );
}
