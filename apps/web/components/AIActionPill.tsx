"use client";

/**
 * AIActionPill — a single clickable action from the Global AI's
 * agentic response.  Renders as a small chip:
 *
 *   ┌──────────────────────────────────────────────────┐
 *   │ ◐ Start with Al 99.5%, Mg 0.5%                  │  ← idle
 *   └──────────────────────────────────────────────────┘
 *   ┌──────────────────────────────────────────────────┐
 *   │ ✓ Start with Al 99.5%, Mg 0.5%                  │  ← applied
 *   └──────────────────────────────────────────────────┘
 *
 * Applied state persists on the parent ``ChatMessage`` so re-renders
 * (and full session reloads from Supabase) don't lose the ✓ mark.
 */
import { Check, Loader2, Sparkles } from "lucide-react";
import { useState } from "react";

import { useCanvasStore, type TaggedAction } from "@/lib/store";


// Brand-gold accent (matches LeilHeader / landing page / favicon).
const ACCENT = "38 96% 60%";


export interface AIActionPillProps {
  action:  TaggedAction;
  /** Whether this pill has already been applied. */
  applied: boolean;
  /**
   * Called after the action's underlying dispatch resolves with ok=true.
   * The parent owns the "applied" state model — persisted on the message
   * row (Global AI) or kept in local component state (Local AI popover,
   * where there's no persisted message to mark).
   */
  onApplied: () => void;
  /** Which AI surface this pill lives on — recorded in the action log. */
  source?: "global_ai" | "local_ai";
}


export function AIActionPill({ action, applied, onApplied, source = "global_ai" }: AIActionPillProps) {
  const applyAction      = useCanvasStore((s) => s.applyAction);
  const logAction        = useCanvasStore((s) => s.logAction);
  const [busy, setBusy]  = useState(false);

  const run = async () => {
    if (busy || applied) return;
    setBusy(true);
    try {
      const result = await applyAction(action.action);
      if (result.ok) {
        // Record into the unified design-decision trail before notifying
        // the parent.  Carries the human label + the executable op so the
        // Global AI timeline + PDF decision log can render it.
        logAction({ source, label: action.label, op: action.action.op });
        onApplied();
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      onClick={run}
      disabled={busy || applied}
      title={tooltipFor(action)}
      className="group inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11.5px] font-medium transition-all disabled:cursor-default"
      style={{
        // Applied pills dim, but keep the accent so they still read as
        // "AI-suggested".  Idle pills have a faint accent glow on hover.
        background: applied
          ? "hsl(var(--accent) / 0.07)"
          : "hsl(var(--accent) / 0.12)",
        borderColor: applied
          ? "hsl(var(--accent) / 0.18)"
          : "hsl(var(--accent) / 0.35)",
        color: applied
          ? "hsl(var(--accent) / 0.55)"
          : "hsl(var(--accent))",
        ["--accent" as keyof React.CSSProperties as string]: ACCENT,
      } as React.CSSProperties}
    >
      {busy
        ? <Loader2 size={11} className="animate-spin" />
        : applied
          ? <Check size={11} />
          : <Sparkles size={11} />}
      <span>{action.label}</span>
    </button>
  );
}


/**
 * Apply-all master button.  Skips already-applied actions so a re-click
 * doesn't double-apply (e.g. re-running a sweep would be expensive).
 */
export function AIActionApplyAll({
  actions,
  appliedIdx,
  onActionApplied,
  source = "global_ai",
}: {
  actions:         TaggedAction[];
  appliedIdx:      number[];
  /** Fired once per successfully-applied action with its index. */
  onActionApplied: (index: number) => void;
  /** Which AI surface — recorded in the action log. */
  source?: "global_ai" | "local_ai";
}) {
  const applyAction     = useCanvasStore((s) => s.applyAction);
  const logAction       = useCanvasStore((s) => s.logAction);
  const [busy, setBusy] = useState(false);

  // If everything is already applied, hide the button.
  const remaining = actions.filter((_, i) => !appliedIdx.includes(i));
  if (remaining.length === 0) return null;

  const run = async () => {
    if (busy) return;
    setBusy(true);
    try {
      for (let i = 0; i < actions.length; i++) {
        if (appliedIdx.includes(i)) continue;
        const result = await applyAction(actions[i].action);
        if (result.ok) {
          logAction({ source, label: actions[i].label, op: actions[i].action.op });
          onActionApplied(i);
        }
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      onClick={run}
      disabled={busy}
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11.5px] font-semibold transition-all"
      style={{
        background:  "hsl(var(--accent) / 0.22)",
        borderColor: "hsl(var(--accent) / 0.5)",
        color:       "hsl(var(--accent))",
        border:      "1px solid hsl(var(--accent) / 0.5)",
        ["--accent" as keyof React.CSSProperties as string]: ACCENT,
      } as React.CSSProperties}
    >
      {busy
        ? <Loader2 size={11} className="animate-spin" />
        : <Sparkles size={11} />}
      Apply all ({remaining.length})
    </button>
  );
}


/** Build a readable tooltip describing the action payload. */
function tooltipFor({ action }: TaggedAction): string {
  switch (action.op) {
    case "set_element":      return `${action.element} → ${action.value}%`;
    case "delta_element":    return `${action.element} ${action.delta >= 0 ? "+" : ""}${action.delta}%`;
    case "set_target":       return `${action.name} = ${action.value}`;
    case "sweep":            return `Sweep ${action.vary} from ${action.from}% to ${action.to}% (${action.steps} pts)`;
    case "set_composition":  return Object.entries(action.composition)
                                    .map(([k, v]) => `${k}: ${v}%`).join(", ");
    case "set_phase_system": return action.elements.join("-");
    case "set_goals":        return Object.entries(action.goals)
                                    .map(([k, v]) => `${k}: ${v}`).join(" · ");
    case "set_constraints":  return Object.entries(action.constraints)
                                    .map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(" · ");
    case "run_predict":      return "Trigger the Predict Properties button";
    case "run_optimization": return "Trigger the Run Optimization button";
    case "simulate_grain_structure": {
      const p = action.parameters as { n_grains?: number; morpho?: string };
      return `Generate grain structure${p.n_grains ? ` · ${p.n_grains} grains` : ""}${p.morpho ? ` (${p.morpho})` : ""}`;
    }
  }
}
