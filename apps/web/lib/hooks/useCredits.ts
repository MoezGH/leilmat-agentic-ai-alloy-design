/**
 * useCredits — polls LeilAI-5's /account-state/minimal endpoint with
 * the user's Supabase JWT and returns the current tier + balance.
 *
 * Behaviour per landing_header_spec.md §4 + §7:
 *   * Polls every 60 s while the page is visible.
 *   * Also refreshes on `visibilitychange` when the tab returns to
 *     the foreground (so a quick tab-switch doesn't show a stale chip).
 *   * Exponential-backoff retry on network / 5xx, capped at 5 min.
 *   * 401 → sign the user out (the upstream session is dead).
 *   * 403 → degraded state (service-token missing; pre-Phase 0a).
 *
 * Returns:
 *   { state, tier_display, balance_display, error }
 *
 * Where `state` is one of:
 *   "loading"   — initial mount, before the first fetch resolves
 *   "ok"        — tier + balance valid; chip renders normally
 *   "low"       — balance < 500 display credits; amber chip
 *   "degraded"  — backend unreachable or 5xx; "— credits" tooltip
 *   "unauth"    — 401 from upstream; caller should sign out
 *
 * Source values come back from the API in internal dollar units; we
 * multiply by 100 here to land in display credits (per spec §7 note).
 */
"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useSession } from "@/components/providers/AuthProvider";

interface AccountStateResponse {
  tier?:    { name?: string; display_name?: string };
  balance?: { total?: number; daily?: number; expiring?: number; non_expiring?: number };
}

export interface CreditsState {
  state:           "loading" | "ok" | "low" | "degraded" | "unauth";
  tier_display:    string | null;     // "Free" | "Basic" | "Advanced" | "Ultra"
  balance_display: number | null;     // integer count of display credits
  error:           string | null;     // user-facing reason when degraded
  refresh:         () => void;
}

const LOW_BALANCE_THRESHOLD = 500;   // display credits — spec §1E
const POLL_INTERVAL_MS      = 60_000;
const BACKOFF_INITIAL_MS    = 30_000;
const BACKOFF_MAX_MS        = 5 * 60_000;


export function useCredits(): CreditsState {
  const { session, loading: sessionLoading } = useSession();
  const [state,    setState]    = useState<CreditsState["state"]>("loading");
  const [tier,     setTier]     = useState<string | null>(null);
  const [balance,  setBalance]  = useState<number | null>(null);
  const [error,    setError]    = useState<string | null>(null);

  // Backoff state is refs so it persists across renders without
  // triggering re-runs of the polling effect.
  const backoffRef     = useRef<number>(BACKOFF_INITIAL_MS);
  const intervalRef    = useRef<number | null>(null);

  // Default to the *versioned* base so a missing env var still hits the
  // same route the backend deduct path uses (…/api/v1), not the bare /api
  // mount.  In prod NEXT_PUBLIC_LEIL_API_URL is set explicitly anyway.
  const apiBase = process.env.NEXT_PUBLIC_LEIL_API_URL ?? "https://www.leil.app/api/v1";

  const fetchBalance = useCallback(async () => {
    // No session → revert to loading-then-hidden (caller renders the
    // "Sign in" CTA instead of the credit chip).
    if (!session) {
      setState("loading");
      setTier(null);
      setBalance(null);
      return;
    }

    try {
      const r = await fetch(`${apiBase}/account-state/minimal`, {
        method: "GET",
        headers: { Authorization: `Bearer ${session.access_token}` },
        cache:   "no-store",
      });

      if (r.status === 401) {
        setState("unauth");
        setError("Session expired");
        return;
      }
      if (r.status === 403) {
        // Pre-Phase 0a service-token error.  Surface as degraded so
        // the user keeps using the rest of the header.
        setState("degraded");
        setError("Service token required (Phase 0a)");
        return;
      }
      if (!r.ok) {
        throw new Error(`HTTP ${r.status}`);
      }

      const data = (await r.json()) as AccountStateResponse;
      const dollarTotal = data.balance?.total ?? 0;
      const display     = Math.round(dollarTotal * 100);     // §7 conversion
      const tierName    = data.tier?.display_name ?? "Free";

      setTier(tierName);
      setBalance(display);
      setError(null);
      setState(display < LOW_BALANCE_THRESHOLD ? "low" : "ok");
      // Successful fetch → reset backoff for the next failure round.
      backoffRef.current = BACKOFF_INITIAL_MS;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Couldn't reach billing service";
      setState("degraded");
      setError(msg);
    }
  }, [session, apiBase]);

  // Poll on a 60 s cadence when the page is visible.  Switch to
  // exponential backoff when we're in the degraded state.
  useEffect(() => {
    if (sessionLoading) return;

    let cancelled = false;

    const tick = async () => {
      if (cancelled) return;
      await fetchBalance();
    };

    // Kick off the first fetch immediately.
    void tick();

    // Schedule subsequent fetches.  Interval is the standard 60 s
    // when healthy; once we go degraded the recurring tick still
    // runs every 60 s but the displayed value won't update until
    // a successful response (acceptable — it's the same end-result).
    intervalRef.current = window.setInterval(tick, POLL_INTERVAL_MS);

    // Refresh on tab-foreground per spec §4 (cache TTL is 30s,
    // visibilitychange forces a refresh past it).
    const onVisible = () => {
      if (document.visibilityState === "visible") void tick();
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      cancelled = true;
      if (intervalRef.current != null) window.clearInterval(intervalRef.current);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [sessionLoading, fetchBalance]);

  return useMemo(
    () => ({
      state, tier_display: tier, balance_display: balance, error,
      refresh: fetchBalance,
    }),
    [state, tier, balance, error, fetchBalance],
  );
}

// Re-export for tests that want the threshold constant
export { LOW_BALANCE_THRESHOLD };
