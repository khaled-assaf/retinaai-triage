import { useState } from "react";

interface Props {
  imageUrl: string;
  /** null when the quality gate failed — overlay/slider hidden */
  heatmapUrl: string | null;
}

/** Fundus image with a Grad-CAM crossfade slider. */
export function HeatmapViewer({ imageUrl, heatmapUrl }: Props) {
  const [opacity, setOpacity] = useState(0);

  return (
    <div className="rounded-3xl bg-white/75 p-4 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm">
      <div className="relative overflow-hidden rounded-2xl ring-1 ring-slate-200">
        <img
          src={imageUrl}
          alt="Retinal fundus photograph"
          className="block w-full object-cover"
        />
        {heatmapUrl && (
          <img
            src={heatmapUrl}
            alt=""
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 size-full object-cover transition-opacity duration-200"
            style={{ opacity }}
          />
        )}
      </div>

      {heatmapUrl ? (
        <div className="mt-3 flex items-center gap-3">
          <span className="text-xs font-medium text-slate-500">Grad-CAM</span>
          <input
            type="range"
            min={0}
            max={100}
            value={Math.round(opacity * 100)}
            onChange={(e) => setOpacity(Number(e.target.value) / 100)}
            aria-label="Heatmap overlay opacity"
            className="h-1.5 flex-1 cursor-pointer accent-teal-600"
          />
          <span className="w-9 text-right text-xs tabular-nums text-slate-400">
            {Math.round(opacity * 100)}%
          </span>
        </div>
      ) : (
        <p className="mt-3 text-center text-xs text-slate-400">
          No heatmap — image did not pass the quality gate.
        </p>
      )}
    </div>
  );
}
