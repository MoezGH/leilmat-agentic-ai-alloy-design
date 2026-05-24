/**
 * Authenticated fetch helpers.
 *
 * Until Step 11 lands, the cost-bearing endpoints behind LeilMat's
 * AuthMiddleware (the LLM-firing routes, microstructure/precipitation
 * simulators, Scheil, /api/chat/*, /api/design/*) reject every request
 * with 401 because nothing in the existing fetch path was attaching
 * the Supabase session's access_token.  This module fixes that.
 *
 * Two surfaces:
 *
 *   useAuthFetch()
 *     React hook for client components.  Returns a function with the
 *     same signature as `fetch` that auto-attaches `Authorization:
 *     Bearer <session.access_token>` when a session exists.  Relative
 *     paths (anything that doesn't start with "http") are prefixed
 *     with NEXT_PUBLIC_API_URL.
 *
 *   buildAuthHeaders(accessToken)
 *     Pure helper for non-React callers (lib/api.ts top-level
 *     functions, server components, tests).  Returns a `HeadersInit`
 *     with the Bearer token set when present.
 *
 * Design notes:
 *   * No mutation of the session — the hook only reads.  Refresh /
 *     rotation is the AuthProvider's job.
 *   * Never silently swallows fetch errors — callers handle 401/403/
 *     network errors using existing patterns (see AIInsightsBlock's
 *     rateLimited handling for 429 as a template).
 *   * Same-origin (production: app.example.org) means the browser would
 *     send cookies anyway; we still send the Bearer header explicitly
 *     because backend auth checks the header, not the cookie.
 */
"use client";

import { useCallback } from "react";

import { useSession } from "@/components/providers/AuthProvider";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";


/**
 * Returns a `fetch`-shaped function bound to the current Supabase
 * session.  When a session is present, `Authorization: Bearer <token>`
 * is added (unless the caller's `init.headers` already carries one —
 * we never overwrite an explicit Authorization).
 *
 * URL handling: if the input starts with "http", it's used as-is;
 * otherwise NEXT_PUBLIC_API_URL is prepended.  So both of these work:
 *
 *   authFetch("/api/microstructure/simulate", { method: "POST", … })
 *   authFetch("https://example.com/external", { … })
 */
export function useAuthFetch() {
  const { session } = useSession();
  const accessToken = session?.access_token ?? null;

  return useCallback(
    (input: string, init?: RequestInit) => {
      const url = input.startsWith("http") ? input : `${BASE}${input}`;
      const headers = new Headers(init?.headers ?? {});
      if (accessToken && !headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${accessToken}`);
      }
      return fetch(url, { ...init, headers });
    },
    [accessToken],
  );
}


/**
 * Pure helper for non-React callers — top-level functions in
 * apps/web/lib/api.ts, server-side fetches, tests.
 *
 * Pass the token explicitly so this function stays stateless:
 *
 *     const headers = buildAuthHeaders(session?.access_token, {
 *       "Content-Type": "application/json",
 *     });
 */
export function buildAuthHeaders(
  accessToken: string | null | undefined,
  extra?: HeadersInit,
): HeadersInit {
  const h = new Headers(extra ?? {});
  if (accessToken && !h.has("Authorization")) {
    h.set("Authorization", `Bearer ${accessToken}`);
  }
  return h;
}
