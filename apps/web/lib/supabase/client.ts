/**
 * Browser-side Supabase client (singleton).
 *
 * Used by any "use client" component that needs to talk to Supabase
 * directly — `signInWithOAuth`, `signOut`, `getUser`, real-time
 * subscriptions, and the design-session CRUD in services/sessionService.ts.
 *
 * Pattern: `createBrowserClient` from `@supabase/ssr` handles cookie
 * synchronisation with the Next.js server-side client so the session
 * stays consistent across SSR boundaries.
 *
 * **Singleton, not a factory.**
 *   Previously this returned a new client per call.  Combined with
 *   ``services/supabase.ts`` calling vanilla ``createClient`` (which
 *   stores its session in localStorage, not cookies), the app ran
 *   with TWO independent GoTrueClient instances that disagreed about
 *   the user's session — sign-in landed in cookies, ``sessionService``
 *   used the localStorage-backed client which had no session and sent
 *   inserts with only the anon key, tripping a 42501 RLS violation on
 *   every auto-save.
 *
 *   Caching the instance at module scope makes both call sites
 *   ``createSupabaseBrowserClient()`` and ``services/supabase.ts``
 *   resolve to the SAME GoTrueClient with the SAME cookie-backed
 *   session, fixing the "Multiple GoTrueClient instances" warning
 *   and the auto-save RLS error.
 *
 * Reads:
 *   NEXT_PUBLIC_SUPABASE_URL
 *   NEXT_PUBLIC_SUPABASE_ANON_KEY
 *
 * Reference: AUTH_BILLING_REFERENCE.md §4 + landing_header_spec.md §9.
 */
import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

let _client: SupabaseClient | null = null;

export function createSupabaseBrowserClient(): SupabaseClient {
  if (_client) return _client;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    throw new Error(
      "Supabase env vars missing — set NEXT_PUBLIC_SUPABASE_URL and " +
      "NEXT_PUBLIC_SUPABASE_ANON_KEY in apps/web/.env.local (or the repo-root .env)."
    );
  }
  _client = createBrowserClient(url, key);
  return _client;
}
