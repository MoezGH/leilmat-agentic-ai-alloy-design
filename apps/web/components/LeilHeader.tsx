/**
 * LeilHeader — universal Leil sub-app header.
 *
 * Implements landing_header_spec.md §1-§10 verbatim for LeilMat:
 *   * 56 px desktop / 48 px mobile
 *   * hsl(0 0% 4%) background, 1px hsl(0 0% 10%) border-bottom
 *   * sticky top, z-50
 *   * accent: warm gold (38 96% 60%) per spec §3
 *
 * Four states:
 *   A. Loading        — "⋯ loading"
 *   B. Signed-out     — "[ Sign in with Google ]"  (gold-accent button)
 *   C. Signed-in      — "[ {tier} • {bal} credits ] [ 👤 ▼ ]"
 *   D. Error / API    — "[ — credits ]"           (degraded chip)
 *   E. Low credits    — "[ {tier} • {bal} credits ]"  (amber chip)
 *
 * The avatar dropdown opens on click, traps focus, closes on Esc, and
 * shows: name (bold), email (muted), Manage subscription, Sign out.
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { LogOut, Loader2, ExternalLink } from "lucide-react";

import {
  useUser,
  useSession,
  useSignInWithGoogle,
  useSignOut,
} from "@/components/providers/AuthProvider";
import { useCredits } from "@/lib/hooks/useCredits";

// Spec §3 brand accent — LeilMat warm gold.
const ACCENT_HSL = "38 96% 60%";

// Where the credit chip and "Manage subscription" link go.
const BILLING_URL = "https://www.leil.app/billing";


export function LeilHeader() {
  // The landing page hosts its own SignInPanel on the right rail; the
  // canvas page has its own page-level header that absorbs the user
  // cluster (see ``LeilUserCluster`` below).  In both cases the global
  // LeilHeader is suppressed entirely to avoid double-banner stacking.
  const pathname = usePathname();
  if (pathname === "/" || pathname.startsWith("/canvas")) return null;

  return (
    <header
      style={{
        ["--accent" as keyof React.CSSProperties as string]: ACCENT_HSL,
      } as React.CSSProperties}
      className="sticky top-0 z-50 w-full bg-[hsl(0_0%_4%)] border-b border-[hsl(0_0%_10%)] h-12 md:h-14 px-4 flex items-center justify-between"
    >
      {/* Left cluster — logo + app name.  Clickable returns to /. */}
      <a
        href="/"
        className="flex items-center gap-2.5 group"
        aria-label="LeilMat home"
      >
        <div
          className="w-6 h-6 rounded-md grid place-items-center text-[10px] font-bold font-mono"
          style={{
            background: "hsl(var(--accent) / 0.15)",
            color:      "hsl(var(--accent))",
            border:     "1px solid hsl(var(--accent) / 0.4)",
          }}
        >
          LM
        </div>
        <span className="text-[13px] font-semibold text-slate-100 tracking-tight group-hover:text-white transition-colors">
          LeilMat
        </span>
      </a>

      {/* Right cluster */}
      <div className="flex items-center gap-3">
        <LeilUserCluster />
      </div>
    </header>
  );
}


/**
 * LeilUserCluster — extractable right-hand cluster (loading chip /
 * signed-in cluster with credits + avatar / Google sign-in button).
 *
 * The canvas page mounts this directly inside its own page-level
 * header so the user cluster lives next to the canvas-specific
 * controls without LeilHeader rendering a second banner above it.
 * Honours the same warm-gold ``--accent`` set by the parent.
 */
export function LeilUserCluster() {
  const { loading: sessionLoading } = useSession();
  const { user } = useUser();
  const credits  = useCredits();
  const signedIn = !!user;

  if (sessionLoading) return <LoadingChip />;
  return signedIn
    ? <SignedInCluster credits={credits} />
    : <SignedOutCluster />;
}


// ─────────────────────────────────────────────────────────────────────
// State A: Loading
// ─────────────────────────────────────────────────────────────────────

function LoadingChip() {
  return (
    <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
      <Loader2 size={12} className="animate-spin" />
      <span>loading</span>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────
// State B: Signed-out
// ─────────────────────────────────────────────────────────────────────

function SignedOutCluster() {
  const signIn = useSignInWithGoogle();
  const [busy, setBusy] = useState(false);

  return (
    <button
      onClick={async () => {
        setBusy(true);
        try { await signIn(); }
        finally { setBusy(false); }
      }}
      disabled={busy}
      className="flex items-center gap-2 text-[12px] px-3 py-1.5 rounded-md font-semibold transition-all disabled:opacity-50"
      style={{
        background: "hsl(var(--accent) / 0.18)",
        color:      "hsl(var(--accent))",
        border:     "1px solid hsl(var(--accent) / 0.4)",
      }}
    >
      {busy ? <Loader2 size={13} className="animate-spin" /> : <GoogleIcon />}
      Sign in with Google
    </button>
  );
}


// ─────────────────────────────────────────────────────────────────────
// State C + D + E: Signed-in
// ─────────────────────────────────────────────────────────────────────

function SignedInCluster({ credits }: { credits: ReturnType<typeof useCredits> }) {
  return (
    <>
      <CreditChip credits={credits} />
      <AvatarMenu />
    </>
  );
}


function CreditChip({ credits }: { credits: ReturnType<typeof useCredits> }) {
  // Build the visible label.  Loading shows nothing (the avatar handles
  // the perceived-progress); degraded shows "— credits" + tooltip.
  if (credits.state === "loading") {
    return (
      <div className="text-[11px] text-slate-500 font-mono">
        loading…
      </div>
    );
  }

  if (credits.state === "degraded" || credits.state === "unauth") {
    return (
      <a
        href={BILLING_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[11px] px-2.5 py-1 rounded-md bg-white/[0.03] border border-white/8 text-slate-500 font-mono"
        title={`Couldn't reach billing service${credits.error ? `: ${credits.error}` : ""}. Try again in a moment.`}
      >
        — credits
      </a>
    );
  }

  const low = credits.state === "low";
  const tier    = credits.tier_display    ?? "Free";
  const balance = credits.balance_display ?? 0;

  return (
    <a
      href={BILLING_URL}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`${tier} plan, ${balance} credits remaining. Click to upgrade.`}
      className={`text-[11px] px-2.5 py-1 rounded-md font-medium transition-colors border ${
        low
          ? "bg-amber-500/15 text-amber-300 border-amber-500/30 hover:bg-amber-500/25"
          : "bg-white/[0.03] hover:bg-white/[0.06] border-white/[0.06]"
      }`}
      style={low ? undefined : {
        borderColor: "hsl(var(--accent) / 0.3)",
        color:       "hsl(var(--accent))",
      }}
    >
      <span className={low ? undefined : "text-slate-300"}>{tier}</span>
      <span className="mx-1.5 text-slate-600">·</span>
      <span className="font-mono">
        {balance.toLocaleString()} credits
      </span>
    </a>
  );
}


function AvatarMenu() {
  const { user } = useUser();
  const signOut  = useSignOut();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // Close on click-outside + Esc, per spec §10.
  useEffect(() => {
    if (!open) return;
    function onPointer(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const name  = (user?.user_metadata?.full_name as string)
              ?? (user?.user_metadata?.name      as string)
              ?? user?.email
              ?? "Signed in";
  const email = user?.email ?? "—";
  const avatar = (user?.user_metadata?.avatar_url as string) ?? null;
  const initial = (name || "?").trim().charAt(0).toUpperCase();

  const onSignOut = useCallback(async () => {
    setOpen(false);
    await signOut();
  }, [signOut]);

  return (
    <div ref={rootRef} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        aria-label="User menu"
        aria-expanded={open}
        aria-haspopup="menu"
        className="w-7 h-7 rounded-full overflow-hidden grid place-items-center bg-white/[0.04] border border-white/[0.08] hover:ring-2 transition-shadow text-[11px] font-semibold text-slate-300"
        style={{
          ["--tw-ring-color" as keyof React.CSSProperties as string]: "hsl(var(--accent) / 0.5)",
        } as React.CSSProperties}
      >
        {avatar
          ? // eslint-disable-next-line @next/next/no-img-element
            <img src={avatar} alt="" className="w-full h-full object-cover" />
          : initial}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-9 w-56 rounded-md border border-white/8 bg-[hsl(0_0%_6%)] shadow-xl shadow-black/60 overflow-hidden motion-safe:animate-in fade-in-0 zoom-in-95 duration-100"
        >
          <div className="px-3 py-2.5 border-b border-white/[0.06]">
            <p className="text-[12px] font-semibold text-slate-100 truncate">{name}</p>
            <p className="text-[11px] text-slate-500 truncate">{email}</p>
          </div>
          <a
            href={BILLING_URL}
            target="_blank"
            rel="noopener noreferrer"
            role="menuitem"
            className="flex items-center justify-between gap-2 px-3 py-2 text-[12px] text-slate-300 hover:bg-white/[0.04] hover:text-white transition-colors"
            onClick={() => setOpen(false)}
          >
            <span>Manage subscription</span>
            <ExternalLink size={11} className="text-slate-500" />
          </a>
          <button
            type="button"
            role="menuitem"
            onClick={onSignOut}
            className="w-full flex items-center justify-between gap-2 px-3 py-2 text-[12px] text-slate-300 hover:bg-white/[0.04] hover:text-white transition-colors border-t border-white/[0.04]"
          >
            <span>Sign out</span>
            <LogOut size={11} className="text-slate-500" />
          </button>
        </div>
      )}
    </div>
  );
}


// Inline Google "G" mark — keeps the spec's "Sign in with Google" button
// recognisable without adding the @react-oauth/google asset.
function GoogleIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.6-6 8-11.3 8-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/>
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 16 19 13 24 13c3.1 0 5.9 1.2 8 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.4 6.3 14.7z"/>
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.5-5.2l-6.2-5.2c-2 1.5-4.5 2.4-7.3 2.4-5.2 0-9.7-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"/>
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.3 4.3-4.2 5.6l6.2 5.2C40.9 36 44 30.5 44 24c0-1.3-.1-2.4-.4-3.5z"/>
    </svg>
  );
}
