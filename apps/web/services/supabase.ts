/**
 * Singleton supabase-js client for direct (non-SSR) reads/writes —
 * sessionService.ts is the primary consumer.
 *
 * For React-component flows that need the SSR-aware client (cookie
 * sync, server components), use ``createSupabaseBrowserClient`` /
 * ``createSupabaseServerClient`` in ../lib/supabase/{client,server}.ts.
 *
 * Pattern ported from LeilFlowsheet/services/supabase.ts.
 */
import { createClient } from "@supabase/supabase-js";

const supabaseUrl     = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

// Fail loudly during development so misconfiguration is immediately obvious.
if (typeof window !== "undefined" && (!supabaseUrl || !supabaseAnonKey)) {
  // eslint-disable-next-line no-console
  console.error(
    "[LeilMat] Missing Supabase config.  Copy .env.example → " +
    ".env.local (under apps/web) and fill in NEXT_PUBLIC_SUPABASE_URL " +
    "+ NEXT_PUBLIC_SUPABASE_ANON_KEY from the Supabase dashboard."
  );
}

export const hasSupabaseConfig = !!(supabaseUrl && supabaseAnonKey);

// Singleton — createClient() called exactly once regardless of how
// many modules import this.
export const supabase = createClient(
  supabaseUrl     ?? "https://placeholder.supabase.co",
  supabaseAnonKey ?? "placeholder-anon-key",
);
