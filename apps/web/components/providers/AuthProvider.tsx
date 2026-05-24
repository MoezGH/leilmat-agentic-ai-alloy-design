/**
 * AuthProvider — client-side context exposing the current Supabase user
 * and session to the React tree.
 *
 * Two hooks:
 *   useUser()    → { user, loading }
 *   useSession() → { session, loading }
 *
 * The provider subscribes to `auth.onAuthStateChange` so anywhere in
 * the tree that reads useUser() updates instantly on sign-in/out.  No
 * manual refresh-after-callback needed — Supabase fires the event
 * after `exchangeCodeForSession` completes.
 *
 * Reference: AUTH_BILLING_REFERENCE.md §4 + Supabase docs.
 */
"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { Session, User, SupabaseClient } from "@supabase/supabase-js";

import { createSupabaseBrowserClient } from "@/lib/supabase/client";

interface AuthContextValue {
  user:     User    | null;
  session:  Session | null;
  loading:  boolean;
  supabase: SupabaseClient;
}

const AuthContext = createContext<AuthContextValue | null>(null);


export function AuthProvider({ children }: { children: React.ReactNode }) {
  // The Supabase client is identity-stable across renders; memoise so
  // every consumer of `auth.supabase` gets the same instance.
  const supabase = useMemo(() => createSupabaseBrowserClient(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    // Initial load — read whatever session is in the cookie / local
    // storage so the header doesn't flash "signed-out" on first paint.
    supabase.auth.getSession().then(({ data }) => {
      if (cancelled) return;
      setSession(data.session);
      setLoading(false);
    });

    // Live subscription — keeps the React tree in sync with sign-in /
    // sign-out events from any tab.
    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      if (cancelled) return;
      setSession(next);
      setLoading(false);
    });

    return () => {
      cancelled = true;
      sub.subscription.unsubscribe();
    };
  }, [supabase]);

  const value: AuthContextValue = {
    user:    session?.user ?? null,
    session,
    loading,
    supabase,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}


// ─────────────────────────────────────────────────────────────────────
// Hooks
// ─────────────────────────────────────────────────────────────────────

function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error(
      "useAuth / useUser / useSession must be called inside <AuthProvider>. " +
      "Wrap apps/web/app/layout.tsx with <AuthProvider> first."
    );
  }
  return ctx;
}

export function useUser() {
  const { user, loading } = useAuth();
  return { user, loading };
}

export function useSession() {
  const { session, loading } = useAuth();
  return { session, loading };
}

/**
 * Convenience: kicks off the Google OAuth round-trip from anywhere in
 * the tree.  Mirrors landing_header_spec.md §5 verbatim, including
 * `prompt: 'select_account'` so users with multiple Google accounts
 * can pick.
 */
export function useSignInWithGoogle() {
  const { supabase } = useAuth();
  return async function signIn() {
    return supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
        queryParams: { prompt: "select_account" },
      },
    });
  };
}

export function useSignOut() {
  const { supabase } = useAuth();
  return async function signOut() {
    await supabase.auth.signOut();
    // Force the page to re-fetch the SSR root layout so the header
    // immediately reflects the signed-out state.
    if (typeof window !== "undefined") window.location.href = "/";
  };
}
