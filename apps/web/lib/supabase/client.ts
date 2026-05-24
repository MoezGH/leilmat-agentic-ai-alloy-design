/**
 * Browser-side Supabase client.
 *
 * Used by any "use client" component that needs to talk to Supabase
 * directly — `signInWithOAuth`, `signOut`, `getUser`, real-time
 * subscriptions, etc.
 *
 * Pattern: createBrowserClient from @supabase/ssr handles cookie
 * synchronisation with the Next.js server-side client so the session
 * stays consistent across SSR boundaries.
 *
 * Reads:
 *   NEXT_PUBLIC_SUPABASE_URL
 *   NEXT_PUBLIC_SUPABASE_ANON_KEY
 *
 * Reference: AUTH_BILLING_REFERENCE.md §4 + landing_header_spec.md §9.
 */
import { createBrowserClient } from "@supabase/ssr";

export function createSupabaseBrowserClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    throw new Error(
      "Supabase env vars missing — set NEXT_PUBLIC_SUPABASE_URL and " +
      "NEXT_PUBLIC_SUPABASE_ANON_KEY in apps/web/.env.local (or the repo-root .env)."
    );
  }
  return createBrowserClient(url, key);
}
