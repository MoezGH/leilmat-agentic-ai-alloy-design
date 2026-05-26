"use client";
/**
 * ExportReportButton — one-click button that snapshots the current
 * canvas + Zustand session into a PDF report and triggers a download.
 *
 * Flow
 * ────
 *   1. User clicks "Export Report" in the canvas header.
 *   2. We assemble a ReportPayload from the Zustand store + the user's
 *      Supabase session (for the JWT).
 *   3. POST to ``/api/report/generate``.  The api builds an audit-grade
 *      multi-page PDF using ReportLab + matplotlib (server-side).
 *   4. Response Blob is converted to a blob URL; we synthesise an <a
 *      download> click to save it.
 *
 * UX
 * ──
 *   * Loading state: spinner + "Building…" (PDF assembly takes
 *     ~1-3 s including matplotlib chart rendering).
 *   * Success: tiny toast "Report downloaded".
 *   * Failure: toast with the server's error message; no console-only
 *     errors (the user needs to know if their report didn't build).
 *
 * Visual treatment matches the warm-gold accent shared with the
 * agentic action pills + landing page.
 */
import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useCanvasStore } from "@/lib/store";
import { useSession }     from "@/components/providers/AuthProvider";
import { generateReport, type ReportPayload } from "@/lib/api";


export function ExportReportButton() {
  const composition       = useCanvasStore((s) => s.composition);
  const properties        = useCanvasStore((s) => s.properties);
  const sessionState      = useCanvasStore((s) => s.session);
  const simulationResults = useCanvasStore((s) => s.simulationResults);
  const { session: authSession } = useSession();
  const accessToken = authSession?.access_token ?? null;

  const [busy, setBusy] = useState(false);

  const run = async () => {
    if (busy) return;
    if (!composition || Object.keys(composition).length === 0) {
      toast.error("Nothing to export — set a composition first.");
      return;
    }

    setBusy(true);
    try {
      const payload: ReportPayload = {
        alloy_name:         sessionState.name || undefined,
        session_id:         sessionState.id   || undefined,
        composition,
        properties:         properties ?? {},
        goals:              sessionState.goals ?? {},
        constraints:        sessionState.constraints ?? {},
        messages:           sessionState.messages ?? [],
        simulation_results: simulationResults ?? {},
      };
      const blob = await generateReport(payload, accessToken);

      // Trigger the download via a synthesised <a> click.  Browsers
      // accept this pattern uniformly and keep the URL bar clean.
      const url = URL.createObjectURL(blob);
      const a   = document.createElement("a");
      a.href     = url;
      a.download = filenameFor(payload);
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

      toast.success("Report downloaded");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Couldn't build report";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      onClick={run}
      disabled={busy}
      title="Export an audit-grade PDF report of this design session"
      className="flex items-center gap-1.5 text-[12px] font-semibold px-2.5 py-1.5 rounded-md transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      style={{
        background:  "hsl(38 96% 60% / 0.15)",
        border:      "1px solid hsl(38 96% 60% / 0.35)",
        color:       "hsl(38 96% 60%)",
      }}
    >
      {busy
        ? <Loader2 size={12} className="animate-spin" />
        : <Download size={12} />}
      <span className="hidden md:inline">{busy ? "Building…" : "Export PDF"}</span>
    </button>
  );
}


/** Slug helper — mirrors the backend filename so locals and downloads agree. */
function filenameFor(p: ReportPayload): string {
  const slug = (p.alloy_name || "design").toLowerCase().trim().replace(/\s+/g, "-");
  const sid  = (p.session_id || "session").slice(0, 8);
  return `leilmat-${slug}-${sid}.pdf`;
}
