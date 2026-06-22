/**
 * Shared cloud-job poll logic (UI/UX audit Tier C — "centralize polling").
 *
 * The three cloud cards (grain structure, CPFEM, grain growth) each polled
 * /api/compute/jobs/{id} with a byte-identical status-branching block.
 * `classifyJobPoll` is that branching, extracted once and unit-tested, so
 * the cards share one well-tested decision instead of three copies.
 *
 * NOTE: this deliberately does NOT change the polling *mechanism* (each
 * card still owns its loop + completion side-effects like persist/
 * auto-interpret).  Rewiring a paid async feature to be store-driven was
 * judged high-consequence / negligible-benefit (results already persist;
 * traffic is trivial) and is intentionally left alone.
 */

export type JobStatus = "queued" | "running" | "done" | "failed" | "timeout";

export interface PollableJob<R> {
  job_id: string;
  status: JobStatus;
  result: R | null;
  error: string | null;
}

export type PollOutcome<R> =
  | { kind: "done"; result: R }
  | { kind: "error"; message: string }
  | { kind: "pending" };

/**
 * Decide what a single poll response means.
 *  - done + result   → render it
 *  - failed/timeout   → surface the first line of the error (or the status)
 *  - anything else    → keep polling
 */
export function classifyJobPoll<R>(job: PollableJob<R>): PollOutcome<R> {
  if (job.status === "done" && job.result) {
    return { kind: "done", result: job.result };
  }
  if (job.status === "failed" || job.status === "timeout") {
    return { kind: "error", message: job.error?.split("\n")[0] || job.status };
  }
  return { kind: "pending" };
}
