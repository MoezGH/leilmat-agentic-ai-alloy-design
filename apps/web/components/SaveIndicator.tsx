/**
 * SaveIndicator — small pill that surfaces the persistence state next
 * to the LeilHeader's existing AI-online + budget chips.
 *
 * Four visual states, each with a colour + label + tooltip:
 *
 *    saving   gold spinner   "Saving…"                "Auto-saving to Supabase"
 *    saved    green dot      "Saved {relative-time}"  "All changes saved"
 *    error    rose dot       "Save failed"            "Last save error — check console"
 *    idle     muted dot      "Local only"             "Sign in to auto-save"
 *
 * Hidden entirely when the user is signed-out AND there's nothing
 * persistable yet (avoids a flash of "Local only" on the landing
 * page).
 *
 * The persistence state is owned by useSessionPersistence() — this
 * component just renders what it's given so it stays trivially
 * testable.
 */
"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import type { SaveState } from "@/lib/hooks/useSessionPersistence";


function relTime(date: Date | null): string {
  if (!date) return "";
  const secs = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (secs < 5)   return "just now";
  if (secs < 60)  return `${secs} s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60)  return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)   return `${hrs} h ago`;
  return date.toLocaleDateString();
}


export function SaveIndicator({
  saveState,
  lastSavedAt,
  signedIn,
}: {
  saveState:   SaveState;
  lastSavedAt: Date | null;
  signedIn:    boolean;
}) {
  // Tick every 15 s so "2 min ago" auto-rolls forward without
  // re-rendering the rest of the header.
  const [, tick] = useState(0);
  useEffect(() => {
    if (saveState !== "saved") return;
    const id = window.setInterval(() => tick((n) => n + 1), 15_000);
    return () => window.clearInterval(id);
  }, [saveState]);

  if (!signedIn) {
    return (
      <div
        className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-fg/[0.04] border border-line"
        title="Sign in to auto-save your design sessions to Supabase."
      >
        <div className="w-1.5 h-1.5 rounded-full bg-subtle" />
        <span className="text-[11px] text-subtle font-medium">Local only</span>
      </div>
    );
  }

  if (saveState === "saving") {
    return (
      <div
        className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-fg/[0.04] border border-line"
        title="Auto-saving the current session to Supabase…"
      >
        <Loader2 size={10} className="animate-spin text-muted" />
        <span className="text-[11px] text-muted font-medium">Saving…</span>
      </div>
    );
  }

  if (saveState === "error") {
    return (
      <div
        className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-bad/10 border border-bad/30"
        title="Last save failed — check the browser console for the Supabase error."
      >
        <div className="w-1.5 h-1.5 rounded-full bg-bad" />
        <span className="text-[11px] text-bad font-medium">Save failed</span>
      </div>
    );
  }

  // "saved" or "idle"
  return (
    <div
      className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-ok/8 border border-ok/20"
      title="All changes saved.  Auto-save fires 3 seconds after the last edit."
    >
      <div className="w-1.5 h-1.5 rounded-full bg-ok" />
      <span className="text-[11px] text-ok font-medium">
        {lastSavedAt ? `Saved ${relTime(lastSavedAt)}` : "Saved"}
      </span>
    </div>
  );
}
