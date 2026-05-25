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


/** Extract + validate the actions block from a streamed assistant message. */
export function parseAssistantMessage(raw: string): ParsedAssistantMessage {
  const match = ACTIONS_BLOCK_RE.exec(raw);
  if (!match) return { cleanText: raw, actions: [] };

  const blockBody = match[1].trim();
  const cleanText = raw.replace(ACTIONS_BLOCK_RE, "").trimEnd();

  let parsed: unknown;
  try {
    parsed = JSON.parse(blockBody);
  } catch (err) {
    // LLM emitted invalid JSON — log and skip silently rather than
    // crash.  Users still see the prose; pills just don't appear.
    // eslint-disable-next-line no-console
    console.warn("[ai.actions] JSON parse failed:", err, blockBody.slice(0, 200));
    return { cleanText, actions: [] };
  }
  if (!Array.isArray(parsed)) {
    // eslint-disable-next-line no-console
    console.warn("[ai.actions] actions block was not an array; got:", typeof parsed);
    return { cleanText, actions: [] };
  }

  const actions: TaggedAction[] = [];
  for (const raw of parsed) {
    const tagged = validateAction(raw);
    if (tagged) actions.push(tagged);
  }
  return { cleanText, actions };
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
      if (typeof element !== "string" || typeof value !== "number") return null;
      return { label, action: { op, element, value } };
    }
    case "delta_element": {
      const element = obj.element;
      const delta   = obj.delta;
      if (typeof element !== "string" || typeof delta !== "number") return null;
      return { label, action: { op, element, delta } };
    }
    case "set_target": {
      const name    = obj.name;
      const value   = obj.value;
      const optimize = obj.optimize;
      if (typeof name !== "string" || typeof value !== "number") return null;
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
          typeof to !== "number" || typeof steps !== "number") return null;
      return { label, action: { op, vary, from, to, steps } };
    }
    case "set_composition": {
      const composition = obj.composition;
      if (!composition || typeof composition !== "object" || Array.isArray(composition)) return null;
      const c: Record<string, number> = {};
      for (const [k, v] of Object.entries(composition)) {
        if (typeof v === "number") c[k] = v;
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
