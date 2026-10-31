/**
 * Shared Supabase client for direct (non-SSR-component) reads/writes
 * — sessionService.ts is the primary consumer.
 *
 * Previously this file created its own client via
 * ``@supabase/supabase-js``'s ``createClient``.  That works in pure
 * SPA apps (like LeilFlowsheet, which we ported this pattern from)
 * but BREAKS in a Next.js app that uses ``@supabase/ssr`` elsewhere,
 * because ``createClient`` stores its session in **localStorage**
 * while ``createBrowserClient`` stores it in **cookies**.  The two
 * clients lived side-by-side with disjoint sessions; the resulting
 * RLS-violation 42501 on every design_sessions insert was the
 * user-visible symptom.
 *
 * Now we just re-export the singleton from ``lib/supabase/client.ts``
 * so the entire app shares ONE GoTrueClient instance with ONE
 * cookie-backed session.
 */
import { authConfigured } from "@/lib/features";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

// Accounts are optional (lib/features.ts): without Supabase the app runs open, which is a supported mode, not an error.
export const hasSupabaseConfig = authConfigured();

/**
 * Singleton — shared with the AuthProvider and any other module that
 * imports ``createSupabaseBrowserClient`` from ``@/lib/supabase/client``.
 * Both call sites resolve to the same instance, so sign-ins from the
 * provider are visible to all subsequent supabase.from(...) calls.
 */
export const supabase = hasSupabaseConfig
  ? createSupabaseBrowserClient()
  // Placeholder client for env-missing builds.  hasSupabaseConfig
  // guards every real call site, so this is never actually invoked.
  : (null as unknown as ReturnType<typeof createSupabaseBrowserClient>);
