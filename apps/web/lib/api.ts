/**
 * Typed fetch helpers for the FastAPI backend.
 *
 * Gated helpers (the ones that hit /api/chat/*, /api/design/*, and the
 * `interpret*` / `simulate` endpoints behind the backend's
 * ENFORCED_PREFIXES) accept an optional `accessToken` argument.  When
 * provided, the Supabase JWT is attached as `Authorization: Bearer
 * <token>`; the backend's AuthMiddleware needs this to return 200
 * instead of 401.
 *
 * Callers in client components should pull the token from
 * `useSession().session?.access_token`.  Use buildAuthHeaders() (from
 * ./api/client) to keep the header-construction code uniform.
 */

import { buildAuthHeaders } from "./api/client";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function predictProperties(
  composition: Record<string, number>,
  temper?: string | null,
) {
  const res = await fetch(`${BASE}/api/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ composition, temper: temper ?? null }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface TemperVocab {
  family: string;
  default: string;
  options: string[];
}

export async function getTempers(family?: string): Promise<TemperVocab | Record<string, TemperVocab>> {
  const url = family
    ? `${BASE}/api/predict/tempers?family=${encodeURIComponent(family)}`
    : `${BASE}/api/predict/tempers`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  if (family) return data as TemperVocab;
  return data.families as Record<string, TemperVocab>;
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

export async function runInverseDesign(
  body: {
    elements: string[];
    targets: { name: string; min_val?: number; max_val?: number; optimize: string }[];
    n_candidates?: number;
    n_iterations?: number;
  },
  accessToken?: string | null,
) {
  const res = await fetch(`${BASE}/api/design/inverse`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken, { "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Stream a Local AI response for a selected canvas element.
 * Returns an AsyncIterable of text chunks.
 */
export async function* streamLocalAI(
  selectedElement: object,
  userQuestion?: string,
  accessToken?: string | null,
): AsyncIterable<string> {
  const res = await fetch(`${BASE}/api/chat/local`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken, { "Content-Type": "application/json" }),
    body: JSON.stringify({ selected_element: selectedElement, user_question: userQuestion }),
  });
  if (!res.ok || !res.body) throw new Error("Local AI request failed");
  yield* parseSSE(res.body);
}

/**
 * Stream a Global AI response over the full session context.
 */
export async function* streamGlobalAI(
  session: object,
  userMessage: string,
  accessToken?: string | null,
): AsyncIterable<string> {
  const res = await fetch(`${BASE}/api/chat/global`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken, { "Content-Type": "application/json" }),
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
 * Request a multi-page PDF report of the current design session.
 *
 * Returns the raw response Blob so the caller can wire up the download
 * itself (typically by creating a blob URL + clicking an anchor — see
 * ``ExportReportButton.tsx``).  Throws on non-2xx so the button can
 * surface a toast.
 */
export interface ReportPayload {
  alloy_name?:         string;
  designer?:           string;
  session_id?:         string;
  composition:         Record<string, number>;
  temper?:             string;
  properties?:         Record<string, number | null>;
  property_intervals?: Record<string, [number, number] | null>;
  goals?:              Record<string, string>;
  constraints?:        Record<string, unknown>;
  messages?:           unknown[];
  simulation_results?: Record<string, unknown>;
  stable_phases?:      Array<{ formula: string; formation_energy: number }>;
}

export async function generateReport(
  payload:     ReportPayload,
  accessToken?: string | null,
): Promise<Blob> {
  const res = await fetch(`${BASE}/api/report/generate`, {
    method:  "POST",
    headers: buildAuthHeaders(accessToken, { "Content-Type": "application/json" }),
    body:    JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail || `Report generation failed (HTTP ${res.status})`);
  }
  return res.blob();
}

/**
 * Stream a Global Scan over the full session.
 */
export async function* streamGlobalScan(
  session: object,
  accessToken?: string | null,
): AsyncIterable<string> {
  const res = await fetch(`${BASE}/api/chat/scan`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken, { "Content-Type": "application/json" }),
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
