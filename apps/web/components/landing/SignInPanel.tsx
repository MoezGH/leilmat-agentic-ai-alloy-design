"use client";

/**
 * SignInPanel — the right-rail call-to-action panel on the landing page.
 *
 * Replaces the header's "Sign in with Google" button (the user asked
 * for the CTA to live on the page itself, not floating in the header).
 *
 * States
 * ──────
 *   loading    — initial session check; skeleton chip
 *   signed-out — Google button + soft "you can browse without signing
 *                in" hint that links straight to /canvas
 *   signed-in  — "Welcome back" + prominent "Open Design Canvas" CTA
 *                with the user's email as proof-of-session
 *
 * Visual language
 * ───────────────
 *   * Same warm-gold ``--accent`` as the header.
 *   * Hairline border + soft inner glow so the panel reads as "calm
 *     focal point" against the lattice backdrop.
 *   * Sticky positioning on lg+ so it stays visible during scroll;
 *     stacks above the hero on mobile.
 */
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { useState } from "react";

import {
  useSession,
  useUser,
  useSignInWithGoogle,
  useSignOut,
} from "@/components/providers/AuthProvider";


export function SignInPanel() {
  const { loading } = useSession();
  const { user } = useUser();

  return (
    <aside className="relative lg:sticky lg:top-20 w-full max-w-md mx-auto lg:mx-0">
      <div
        className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.025] p-8 backdrop-blur-sm"
        style={{
          boxShadow:
            "0 0 60px -20px hsl(var(--accent) / 0.18), " +
            "inset 0 1px 0 0 hsl(var(--accent) / 0.08)",
        }}
      >
        {/* Faint accent gradient in the top-left corner */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-12 -left-12 h-48 w-48 rounded-full opacity-40"
          style={{
            background:
              "radial-gradient(circle at center, hsl(var(--accent) / 0.18), transparent 70%)",
          }}
        />

        {loading
          ? <LoadingState />
          : user
            ? <SignedInState email={user.email ?? "you"} />
            : <SignedOutState />}
      </div>

      {/* Footer microcopy — same regardless of auth state */}
      <p className="mt-4 px-2 text-center text-[11px] leading-relaxed text-slate-500 lg:text-left">
        By signing in you agree to the LeilMat acceptable-use terms.
        We&rsquo;ll never share your data with third parties.
      </p>
    </aside>
  );
}


// ─── States ──────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-slate-500">
      <Loader2 size={16} className="animate-spin" />
      <span className="text-[13px]">Checking session…</span>
    </div>
  );
}


function SignedOutState() {
  const signIn = useSignInWithGoogle();
  const [busy, setBusy] = useState(false);

  return (
    <div className="relative space-y-6">
      <div className="space-y-2">
        <p
          className="font-mono text-[10px] tracking-[0.18em] uppercase"
          style={{ color: "hsl(var(--accent))" }}
        >
          Start designing
        </p>
        <h2 className="text-2xl font-semibold tracking-tight text-white">
          Sign in to LeilMat
        </h2>
        <p className="text-sm leading-relaxed text-slate-400">
          Save sessions to the cloud, run physics-grade simulations, and
          unlock the AI copilot on every property.
        </p>
      </div>

      <button
        onClick={async () => {
          setBusy(true);
          try { await signIn(); }
          finally { setBusy(false); }
        }}
        disabled={busy}
        className="flex w-full items-center justify-center gap-2.5 rounded-lg px-4 py-3 text-[13px] font-semibold transition-all hover:brightness-110 disabled:opacity-50"
        style={{
          background: "hsl(var(--accent) / 0.18)",
          color:      "hsl(var(--accent))",
          border:     "1px solid hsl(var(--accent) / 0.4)",
        }}
      >
        {busy ? <Loader2 size={14} className="animate-spin" /> : <GoogleIcon />}
        Sign in with Google
      </button>

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-white/[0.06]" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-[#0a0b0f] px-3 text-[11px] uppercase tracking-widest text-slate-500">
            or
          </span>
        </div>
      </div>

      <Link
        href="/canvas"
        className="block text-center text-[13px] text-slate-400 transition-colors hover:text-white"
      >
        Browse the canvas without signing in
        <span aria-hidden className="ml-1.5">→</span>
      </Link>
    </div>
  );
}


function SignedInState({ email }: { email: string }) {
  const signOut = useSignOut();

  return (
    <div className="relative space-y-6">
      <div className="space-y-2">
        <p
          className="font-mono text-[10px] tracking-[0.18em] uppercase"
          style={{ color: "hsl(var(--accent))" }}
        >
          Welcome back
        </p>
        <h2 className="text-2xl font-semibold tracking-tight text-white">
          Pick up where you left off
        </h2>
        <p className="text-sm leading-relaxed text-slate-400">
          Signed in as <span className="text-slate-300">{email}</span>. Your
          sessions, results, and credit balance follow you across the canvas.
        </p>
      </div>

      <Link
        href="/canvas"
        className="flex w-full items-center justify-center gap-2 rounded-lg px-4 py-3 text-[13px] font-semibold transition-all hover:brightness-110"
        style={{
          background: "hsl(var(--accent) / 0.18)",
          color:      "hsl(var(--accent))",
          border:     "1px solid hsl(var(--accent) / 0.4)",
        }}
      >
        Open Design Canvas
        <span aria-hidden>→</span>
      </Link>

      <button
        onClick={() => { void signOut(); }}
        className="block w-full text-center text-[12px] text-slate-500 transition-colors hover:text-slate-300"
      >
        Sign out
      </button>
    </div>
  );
}


// Inline Google "G" mark — kept in this file so the panel has no external
// asset dependency (matches the pattern in LeilHeader.tsx).
function GoogleIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden>
      <path fill="#EA4335" d="M12 11v3.6h5.1c-.2 1.3-1.6 3.8-5.1 3.8-3.1 0-5.6-2.6-5.6-5.8s2.5-5.8 5.6-5.8c1.8 0 2.9.8 3.6 1.4l2.4-2.3C16.7 4.5 14.6 3.5 12 3.5 7.3 3.5 3.5 7.3 3.5 12s3.8 8.5 8.5 8.5c4.9 0 8.2-3.4 8.2-8.3 0-.6-.1-1-.1-1.2H12z"/>
      <path fill="#4285F4" d="M21.5 12.2c0-.6-.1-1-.1-1.2H12V14h5.3c-.2 1.2-1.6 3.6-5.3 3.6V14h-.1l5.4-1.8h4z"/>
      <path fill="#FBBC05" d="M5.5 14.3c-.2-.6-.4-1.4-.4-2.3s.1-1.6.4-2.3L2.9 7.5C2.3 8.8 2 10.3 2 12s.3 3.2.9 4.5l2.6-2.2z"/>
      <path fill="#34A853" d="M12 20.5c2.4 0 4.5-.8 6-2.1l-2.9-2.3c-.8.6-1.9 1-3.1 1-2.4 0-4.4-1.6-5.1-3.8l-2.6 2c1.4 2.9 4.3 5.2 7.7 5.2z"/>
    </svg>
  );
}
