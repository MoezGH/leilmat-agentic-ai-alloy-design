/**
 * Typed fetch helpers for the FastAPI backend.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function predictProperties(composition: Record<string, number>) {
  const res = await fetch(`${BASE}/api/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ composition }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function predictBatch(compositions: Record<string, number>[]) {
  const res = await fetch(`${BASE}/api/predict/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ compositions }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<{ results: { composition: Record<string, number>; [k: string]: unknown }[] }>;
}

export async function getPhaseDiagram(elements: string[]) {
  const res = await fetch(`${BASE}/api/phase/diagram?elements=${elements.join(",")}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Fetch distance-above-convex-hull from the Materials Project DFT database.
 * Requires the predicted formation energy (eV/atom) from /api/predict.
 * Returns null if the MP API key is not configured or the request fails.
 */
export async function getHullDistance(
  composition: Record<string, number>,
  formationEnergyEVPerAtom: number,
): Promise<{
  e_above_hull: number | null;
  e_above_hull_meV?: number;
  stability: "stable" | "metastable" | "unstable" | "unknown";
  note: string;
  source?: string;
  error?: string;
} | null> {
  try {
    const compStr = Object.entries(composition)
      .map(([el, frac]) => `${el}:${frac}`)
      .join(",");
    const res = await fetch(
      `${BASE}/api/phase/hull?composition=${encodeURIComponent(compStr)}&formation_energy=${formationEnergyEVPerAtom}`,
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function runInverseDesign(body: {
  elements: string[];
  targets: { name: string; min_val?: number; max_val?: number; optimize: string }[];
  n_candidates?: number;
  n_iterations?: number;
}) {
  const res = await fetch(`${BASE}/api/design/inverse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Stream a Local AI response for a selected canvas element.
 * Returns an AsyncIterable of text chunks.
 */
export async function* streamLocalAI(selectedElement: object, userQuestion?: string): AsyncIterable<string> {
  const res = await fetch(`${BASE}/api/chat/local`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selected_element: selectedElement, user_question: userQuestion }),
  });
  if (!res.ok || !res.body) throw new Error("Local AI request failed");
  yield* parseSSE(res.body);
}

/**
 * Stream a Global AI response over the full session context.
 */
export async function* streamGlobalAI(session: object, userMessage: string): AsyncIterable<string> {
  const res = await fetch(`${BASE}/api/chat/global`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session, user_message: userMessage, use_rag: true }),
  });
  if (!res.ok || !res.body) throw new Error("Global AI request failed");
  yield* parseSSE(res.body);
}

// ── Model health (Track A.3) ─────────────────────────────────────────────

export interface ModelHealth {
  m3gnet: {
    status: "not_started" | "loading" | "loaded" | "failed";
    elapsed_load_s: number | null;
    error: string | null;
  };
  calibrator: {
    status: "not_started" | "fitting" | "fitted" | "failed";
    elapsed_fit_s: number | null;
    n_calibration: number | null;
    q_eV_per_atom: number | null;
    error: string | null;
  };
  yield_strength: Record<string, {
    present: boolean;
    n_training?: number;
    cv_mae_MPa?: number;
    y_min?: number;
    y_max?: number;
    domain?: string;
    has_ood?: boolean;
    has_conformal?: boolean;
    size_kB?: number;
    error?: string;
  }>;
}

export async function getModelHealth(): Promise<ModelHealth | null> {
  try {
    const res = await fetch(`${BASE}/api/health/models`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/**
 * Stream a Global Scan over the full session.
 */
export async function* streamGlobalScan(session: object): AsyncIterable<string> {
  const res = await fetch(`${BASE}/api/chat/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session }),
  });
  if (!res.ok || !res.body) throw new Error("Global Scan request failed");
  yield* parseSSE(res.body);
}

async function* parseSSE(body: ReadableStream<Uint8Array>): AsyncIterable<string> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6).trim();
      if (payload === "[DONE]") return;
      try {
        const obj = JSON.parse(payload);
        if (obj.text) yield obj.text as string;
      } catch {
        // skip malformed chunks
      }
    }
  }
}
