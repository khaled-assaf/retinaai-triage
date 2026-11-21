import { Loader2 } from "lucide-react";

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-500">
      <Loader2 className="size-4 animate-spin" />
      {label}
    </div>
  );
}
