"use client";
/**
 * Global poller for long-running cloud jobs.
 *
 * Mounted once (in app/layout.tsx) so it runs app-wide regardless of route —
 * a 15-45 min grain-growth job keeps being tracked even after the user
 * navigates away from the card that launched it. It polls
 * /api/compute/jobs/mine, writes the list into the Zustand `cloudJobs` slice
 * (the header indicator reads it), and on a running→done/failed transition
 * fires a sonner toast + a browser desktop notification. (The backend also
 * sends an email — that covers the "tab fully closed" case.)
 *
 * Renders nothing; it's a sibling component that just runs the effect.
 */
import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { useSession } from "@/components/providers/AuthProvider";
import { useAuthFetch } from "@/lib/api/client";
import { useCanvasStore, type CloudJob } from "@/lib/store";

const ACTIVE = new Set(["queued", "running"]);
const TERMINAL = new Set(["done", "failed", "timeout"]);
const KIND_LABEL: Record<string, string> = {
  grain_grow: "Grain growth",
  grain_tessellate: "Grain structure",
};

function fireBrowserNotification(title: string, body: string) {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission === "granted") {
    try { new Notification(title, { body }); } catch { /* ignore */ }
  }
}

function requestNotifyPermission() {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission === "default") {
    try { void Notification.requestPermission(); } catch { /* ignore */ }
  }
}

export function ComputeJobsProvider() {
  const { session } = useSession();
  const authFetch = useAuthFetch();
  const setCloudJobs = useCanvasStore((s) => s.setCloudJobs);
  const prevStatus = useRef<Record<string, string>>({});
  const seeded = useRef(false);
  const askedPerm = useRef(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!session) return;        // only track jobs for a signed-in user
    let cancelled = false;

    const notify = (job: CloudJob) => {
      const label = KIND_LABEL[job.kind] ?? job.kind;
      if (job.status === "done") {
        toast.success(`${label} ready`);
        fireBrowserNotification(`${label} ready`, "Your simulation finished.");
      } else {
        toast.error(`${label} ${job.status}`);
        fireBrowserNotification(`${label} ${job.status}`, "The job did not finish.");
      }
    };

    const tick = async () => {
      if (cancelled) return;
      try {
        const res = await authFetch("/api/compute/jobs/mine");
        if (res.ok) {
          const data = (await res.json()) as { jobs?: CloudJob[] };
          const jobs = data.jobs ?? [];
          if (seeded.current) {
            for (const j of jobs) {
              const prev = prevStatus.current[j.job_id];
              if (prev && ACTIVE.has(prev) && TERMINAL.has(j.status)) notify(j);
            }
          }
          for (const j of jobs) prevStatus.current[j.job_id] = j.status;
          seeded.current = true;
          if (!cancelled) setCloudJobs(jobs);
        }
      } catch { /* transient — keep polling */ }

      const anyActive = Object.values(prevStatus.current).some((s) => ACTIVE.has(s));
      if (anyActive && !askedPerm.current) {
        askedPerm.current = true;
        requestNotifyPermission();   // ask once, when a job is actually running
      }
      const delay = anyActive ? 5000 : 30000;  // fast while a job runs, slow otherwise
      if (!cancelled) timer.current = window.setTimeout(tick, delay);
    };

    void tick();
    return () => {
      cancelled = true;
      if (timer.current != null) clearTimeout(timer.current);
    };
  }, [session, authFetch, setCloudJobs]);

  return null;
}
