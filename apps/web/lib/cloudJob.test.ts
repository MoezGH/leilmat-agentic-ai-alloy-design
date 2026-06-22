import { describe, it, expect } from "vitest";
import { classifyJobPoll, type PollableJob } from "./cloudJob";

const base = <R>(over: Partial<PollableJob<R>>): PollableJob<R> => ({
  job_id: "j1",
  status: "running",
  result: null,
  error: null,
  ...over,
});

describe("classifyJobPoll", () => {
  it("keeps polling while queued or running", () => {
    expect(classifyJobPoll(base({ status: "queued" })).kind).toBe("pending");
    expect(classifyJobPoll(base({ status: "running" })).kind).toBe("pending");
  });

  it("returns the result when done with a payload", () => {
    const out = classifyJobPoll(base<{ grains: number }>({ status: "done", result: { grains: 42 } }));
    expect(out).toEqual({ kind: "done", result: { grains: 42 } });
  });

  it("stays pending if done but the result hasn't landed yet (race)", () => {
    // A 'done' status with a null result must not render — keep polling.
    expect(classifyJobPoll(base({ status: "done", result: null })).kind).toBe("pending");
  });

  it("surfaces the first line of a failure message", () => {
    const out = classifyJobPoll(base({ status: "failed", error: "boom: stack\nframe2\nframe3" }));
    expect(out).toEqual({ kind: "error", message: "boom: stack" });
  });

  it("falls back to the status string when failed with no error text", () => {
    expect(classifyJobPoll(base({ status: "failed", error: null }))).toEqual({ kind: "error", message: "failed" });
    expect(classifyJobPoll(base({ status: "timeout", error: "" }))).toEqual({ kind: "error", message: "timeout" });
  });
});
