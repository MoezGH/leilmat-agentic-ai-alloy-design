/**
 * useModelHealth — polls /api/health/models until M3GNet is loaded and its
 * conformal calibrator is fitted. Stops polling once both reach a terminal
 * state ("loaded" + "fitted", or "failed").
 *
 * Used by the canvas to show a small loading indicator on the formation
 * energy property card during the ~3-second cold start. Without this, the
 * first prediction silently falls back to the Miedema heuristic and the
 * user wouldn't know the M3GNet path was unavailable.
 */
"use client";
import { useEffect, useState } from "react";
import { getModelHealth, type ModelHealth } from "./api";

const POLL_INTERVAL_MS = 2000;
const STARTUP_FAST_POLL_MS = 500;
const FAST_POLL_DURATION_MS = 10000;

export function useModelHealth(enabled: boolean = true): ModelHealth | null {
  const [health, setHealth] = useState<ModelHealth | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;
    const startedAt = Date.now();

    const tick = async () => {
      if (cancelled) return;
      const h = await getModelHealth();
      if (cancelled) return;
      setHealth(h);

      // Stop polling once we reach a terminal state for both layers.
      const m3 = h?.m3gnet?.status;
      const cal = h?.calibrator?.status;
      const m3Done = m3 === "loaded" || m3 === "failed";
      const calDone = cal === "fitted" || cal === "failed";
      if (m3Done && calDone) return;

      // Poll fast for the first 10 s (the cold-start window), then slow.
      const elapsed = Date.now() - startedAt;
      const interval = elapsed < FAST_POLL_DURATION_MS ? STARTUP_FAST_POLL_MS : POLL_INTERVAL_MS;
      timer = setTimeout(tick, interval);
    };

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [enabled]);

  return health;
}
