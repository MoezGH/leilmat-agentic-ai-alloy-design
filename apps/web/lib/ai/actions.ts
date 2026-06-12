/**
 * AI actions parser + dispatcher.
 *
 * The agentic Global AI flow asks the LLM to end every response with a
 * fenced JSON block listing concrete, clickable actions:
 *
 *   ```actions
 *   [
 *     { "op": "set_composition", "composition": {"Al": 99.5, "Mg": 0.5},
 *       "label": "Start with high-purity Al-Mg" },
 *     { "op": "set_target_density"... wait no, the op is "set_target", name "density_g_cm3"... }
 *   ]
 *   ```
 *
 * This module
 *   * extracts the actions block from the streamed text
 *   * validates each entry against the ``ExecutableAction`` discriminated union
 *   * pairs each one with its human-readable label
 *
 * Robust failure mode: any parse / validation problem causes the parser
 * to return ``{ cleanText: original, actions: [] }`` so a misbehaving
 * LLM never crashes the UI — the user just sees the raw text without
 * pills.
 */
import type { ExecutableAction, TaggedAction } from "@/lib/store";


// Regex captures everything between ``` actions and the closing ``` .
// Tolerant of leading whitespace + alternative language tags
// ("action" singular).  The ``[\s\S]*?`` is the lazy "any char incl
// newlines" body.
const ACTIONS_BLOCK_RE = /```actions?\s*\n([\s\S]*?)```/i;

/** Valid op names that the LLM is allowed to emit. */
const VALID_OPS: ReadonlySet<string> = new Set([
  "set_element",
  "delta_element",
  "set_target",
  "sweep",
  "set_composition",
  "set_phase_system",
  "set_goals",
  "set_constraints",
  "run_predict",
  "run_optimization",
]);


export interface ParsedAssistantMessage {
  /** The assistant's prose with the ```actions``` block stripped out. */
  cleanText: string;
  /** Validated, tagged actions ready to render as pills. */
  actions:   TaggedAction[];
}


// Any fenced code block, whatever the language tag (```actions, ```json,
// or a bare ```).  Global flag so we can scan all of them.
const ANY_FENCE_RE = /```[a-zA-Z0-9_-]*\s*\n([\s\S]*?)```/g;

// A trailing bare JSON array (no fence at all) — last-resort match.
const TRAILING_ARRAY_RE = /\[\s*\{[\s\S]*\}\s*\]\s*$/;


/**
 * Parse a JSON string into validated TaggedActions.  Returns [] for
 * anything that isn't a JSON array of objects with a recognised ``op``.
 * This is the guard that lets us scan arbitrary code blocks safely: an
 * illustrative ```json composition (no ``op`` fields) yields zero valid
 * actions and is skipped, so only genuine action arrays get adopted.
 */
function parseActionsArray(body: string): TaggedAction[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(body.trim());
  } catch {
    return [];
  }
  if (!Array.isArray(parsed)) return [];
  const actions: TaggedAction[] = [];
  for (const item of parsed) {
    const tagged = validateAction(item);
    if (tagged) actions.push(tagged);
  }
  return actions;
}


/**
 * Extract + validate the actions block from a streamed assistant message.
 *
 * Tolerant by design — the prompt asks for a ```actions fence, but LLMs
 * frequently emit the same array under ```json, a bare ```, or even no
 * fence at all.  Before this was tolerant, those variants slipped past
 * the parser and rendered as a raw JSON code block instead of clickable
 * pills.  Resolution order:
 *
 *   1. Explicit ```actions fence (the documented contract).
 *   2. Any other fenced block whose body validates as an actions array.
 *   3. A trailing bare JSON array (no fence).
 *
 * Whichever matches first wins; its block is stripped from cleanText so
 * the markdown renderer doesn't also show the raw JSON.
 */
export function parseAssistantMessage(raw: string): ParsedAssistantMessage {
  // ── 1. Preferred: explicit ```actions fence ──────────────────────
  const explicit = ACTIONS_BLOCK_RE.exec(raw);
  if (explicit) {
    const actions = parseActionsArray(explicit[1]);
    if (actions.length > 0) {
      return { cleanText: raw.replace(ACTIONS_BLOCK_RE, "").trimEnd(), actions };
    }
  }

  // ── 2. Any fenced block whose body is a valid actions array ──────
  // (LLM tagged it ```json, or left the fence bare.)
  ANY_FENCE_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = ANY_FENCE_RE.exec(raw)) !== null) {
    const actions = parseActionsArray(m[1]);
    if (actions.length > 0) {
      const cleanText = (raw.slice(0, m.index) + raw.slice(m.index + m[0].length)).trimEnd();
      return { cleanText, actions };
    }
  }

  // ── 3. Last resort: a trailing un-fenced JSON array ──────────────
  const bare = TRAILING_ARRAY_RE.exec(raw);
  if (bare) {
    const actions = parseActionsArray(bare[0]);
    if (actions.length > 0) {
      const cleanText = raw.slice(0, bare.index).trimEnd();
      return { cleanText, actions };
    }
  }

  return { cleanText: raw, actions: [] };
}


/**
 * Validate a single LLM-emitted action and pair it with its label.
 * Returns null when the entry fails any check; the caller should skip
 * (the others may still be valid).
 */
function validateAction(input: unknown): TaggedAction | null {
  if (!input || typeof input !== "object") return null;
  const obj = input as Record<string, unknown>;
  const op = obj.op;
  if (typeof op !== "string" || !VALID_OPS.has(op)) return null;

  const label = typeof obj.label === "string" && obj.label.trim()
    ? obj.label.trim()
    : humaniseOp(op);

  // Type-narrow + payload validation per op.  We strip `label` before
  // building the ExecutableAction object so the discriminated-union
  // type-check downstream sees exactly the right shape.
  switch (op) {
    case "set_element": {
      const element = obj.element;
      const value   = obj.value;
      // A weight-% must be a real number in [0, 100].  Reject a
      // hallucinated negative / >100 / NaN value rather than feed it to
      // the physics engine and show the output as a "computed" property.
      if (typeof element !== "string" || typeof value !== "number" ||
          !Number.isFinite(value) || value < 0 || value > 100) return null;
      return { label, action: { op, element, value } };
    }
    case "delta_element": {
      const element = obj.element;
      const delta   = obj.delta;
      // A delta may be negative, but a |Δ| > 100 wt-% is nonsense.
      if (typeof element !== "string" || typeof delta !== "number" ||
          !Number.isFinite(delta) || Math.abs(delta) > 100) return null;
      return { label, action: { op, element, delta } };
    }
    case "set_target": {
      const name    = obj.name;
      const value   = obj.value;
      const optimize = obj.optimize;
      if (typeof name !== "string" || typeof value !== "number" ||
          !Number.isFinite(value)) return null;
      // Physical bounds per target so the optimizer can't be driven by a
      // hallucinated value (e.g. density −5 or melt 99999).
      const bounds: Record<string, [number, number]> = {
        density_g_cm3:   [0.1, 30],
        melting_point_K: [200, 4500],
      };
      const b = bounds[name];
      if (b && (value < b[0] || value > b[1])) return null;
      return {
        label,
        action: {
          op,
          name,
          value,
          ...(typeof optimize === "string" ? { optimize } : {}),
        },
      };
    }
    case "sweep": {
      const vary  = obj.vary;
      const from  = obj.from;
      const to    = obj.to;
      const steps = obj.steps;
      if (typeof vary !== "string" || typeof from !== "number" ||
          typeof to !== "number" || typeof steps !== "number" ||
          !Number.isFinite(from) || !Number.isFinite(to) ||
          from < 0 || from > 100 || to < 0 || to > 100 ||
          steps < 2 || steps > 50) return null;
      return { label, action: { op, vary, from, to, steps } };
    }
    case "set_composition": {
      const composition = obj.composition;
      if (!composition || typeof composition !== "object" || Array.isArray(composition)) return null;
      const c: Record<string, number> = {};
      for (const [k, v] of Object.entries(composition)) {
        // Only adopt physically valid weight-% values; silently drop
        // negative / >100 / NaN entries from a hallucinated composition.
        if (typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 100) c[k] = v;
      }
      if (Object.keys(c).length === 0) return null;
      return { label, action: { op, composition: c } };
    }
    case "set_phase_system": {
      const elements = obj.elements;
      if (!Array.isArray(elements) || elements.some((e) => typeof e !== "string")) return null;
      return { label, action: { op, elements: elements as string[] } };
    }
    case "set_goals": {
      const goals = obj.goals;
      if (!goals || typeof goals !== "object" || Array.isArray(goals)) return null;
      const g: Record<string, string> = {};
      for (const [k, v] of Object.entries(goals)) {
        if (typeof v === "string") g[k] = v;
      }
      return { label, action: { op, goals: g } };
    }
    case "set_constraints": {
      const constraints = obj.constraints;
      if (!constraints || typeof constraints !== "object" || Array.isArray(constraints)) return null;
      return { label, action: { op, constraints: constraints as Record<string, unknown> } };
    }
    case "run_predict":
    case "run_optimization": {
      return { label, action: { op } as ExecutableAction };
    }
  }
  return null;
}


/** Fallback human label when the LLM forgets to provide one. */
function humaniseOp(op: string): string {
  return op.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
