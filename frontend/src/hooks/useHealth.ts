import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Health } from "../types";

/** Polls GET /api/health for the status dot in the top bar. */
export function useHealth(intervalMs = 30_000) {
  const [data, setData] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const health = await api<Health>("/api/health");
        if (!cancelled) {
          setData(health);
          setError(null);
        }
      } catch {
        if (!cancelled) setError("unreachable");
      }
    };
    void load();
    const t = setInterval(load, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [intervalMs]);

  return { data, error };
}
