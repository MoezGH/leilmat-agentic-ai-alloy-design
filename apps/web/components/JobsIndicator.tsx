"use client";
/**
 * Header chip showing cloud-compute jobs (running + recent), fed by the
 * Zustand `cloudJobs` slice that ComputeJobsProvider keeps in sync. Renders
 * nothing when the user has no jobs. Click to open a small tray.
 */
import { useState } from "react";

import { useCanvasStore } from "@/lib/store";

const KIND_LABEL: Record<string, string> = {
  grain_grow: "Grain growth",
  grain_tessellate: "Grain structure",
  cpfem_stress_strain: "Stress–strain (CPFEM)",
};
const ACTIVE = new Set(["queued", "running"]);

const STATUS_COLOR: Record<string, string> = {
  queued: "text-muted",
  running: "text-fg",
  done: "text-ok",
  failed: "text-bad",
  timeout: "text-warn",
};

function ago(iso?: string | null): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
}

export function JobsIndicator() {
  const jobs = useCanvasStore((s) => s.cloudJobs);
  const [open, setOpen] = useState(false);
  if (!jobs || jobs.length === 0) return null;

  const running = jobs.filter((j) => ACTIVE.has(j.status)).length;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-[10px] font-mono px-2 py-1 rounded border border-line bg-fg/[0.03] hover:bg-fg/[0.06] text-muted"
        title="Cloud compute jobs"
      >
        {running > 0 ? (
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-fg animate-pulse" />
        ) : (
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-subtle" />
        )}
        Jobs
        {running > 0 && (
          <span className="px-1 rounded bg-fg/10 text-fg">{running}</span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-64 max-h-80 overflow-auto rounded-lg border border-line bg-bg shadow-xl z-50 p-1.5">
          {jobs.slice(0, 12).map((j) => (
            <div key={j.job_id} className="flex items-center justify-between gap-2 px-2 py-1.5 rounded hover:bg-fg/[0.04]">
              <div className="min-w-0">
                <div className="text-[10px] text-fg truncate">{KIND_LABEL[j.kind] ?? j.kind}</div>
                <div className="text-[8.5px] text-subtle font-mono">{ago(j.finished_at ?? j.created_at)}</div>
              </div>
              <span className={`text-[9px] font-mono uppercase tracking-wider ${STATUS_COLOR[j.status] ?? "text-muted"}`}>
                {j.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
