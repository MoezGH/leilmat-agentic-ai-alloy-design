/**
 * Zustand store for the design canvas session.
 * Holds composition, properties, targets, exploration trajectory + all session metadata.
 */
import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import { predictProperties } from "@/lib/api";

export interface CompositionEntry {
  id: string;
  composition: Record<string, number>;
  properties: Record<string, number | null>;
  label?: string;
  bookmarked: boolean;
  rejected: boolean;
  createdAt: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  contextType: "local" | "global";
  selectedElement?: SelectedElement;
  createdAt: string;
  // Agentic AI: ``ExecutableAction``s parsed out of the assistant's
  // response that the user can click to apply to the canvas.  Persisted
  // on the message so the pills survive session reload.  See
  // ../lib/ai/actions.ts for the parser + the prompt convention.
  actions?: TaggedAction[];
  // Indices (into ``actions``) already applied, so the pills can render
  // a ✓ across re-renders without re-running the dispatch.
  appliedActionIdx?: number[];
}

/** An ExecutableAction paired with a user-facing label for the pill UI. */
export interface TaggedAction {
  label:  string;
  action: ExecutableAction;
}

/**
 * A single design action the user applied from ANY AI surface (Global
 * AI pill, Local AI pill, or an interpret-card "Apply" button).
 *
 * Logged into a unified ``actionLog`` so the design-decision trail
 * lives in one place: rendered as event rows interleaved into the
 * Global AI timeline, summarised into the Global AI's prompt context
 * (so the model reasons with awareness of what's been applied), and
 * carried into the PDF report's decision-log section.
 */
export interface AppliedAction {
  id:        string;
  source:    "global_ai" | "local_ai" | "interpret_card" | "grain_card" | "cpfem_card";
  label:     string;        // human summary, e.g. "Crystal symmetry → 4-fold"
  detail?:   string;        // optional motivating rationale
  op?:       string;        // the executable op kind, when known
  createdAt: string;        // ISO timestamp — used to interleave with messages
}

export interface SelectedElement {
  type: "composition_point" | "phase_boundary" | "property_bar" | "candidate_card" | "ternary_region";
  data: Record<string, unknown>;
  canvas_summary?: Record<string, unknown>;
  anchor?: { x: number; y: number };
}

export interface DesignSession {
  id: string;
  name: string;
  goals: Record<string, string>;
  constraints: Record<string, unknown>;
  compositions: CompositionEntry[];
  messages: ChatMessage[];
  // Unified design-decision trail — every applied AI action across all
  // surfaces.  Persisted with the session + fed into the Global AI's
  // context.  Optional for back-compat with rows saved before this
  // field existed.
  actionLog?: AppliedAction[];
}

export interface SweepPoint {
  variedValue: number;
  composition: Record<string, number>;
  properties: Record<string, number | null>;
}

export interface SweepResult {
  vary: string;
  from: number;
  to: number;
  points: SweepPoint[];
  createdAt: string;
}

export type ExecutableAction =
  // ── Atomic ops (originally for LocalAI suggestions) ──
  | { op: "set_element"; element: string; value: number }
  | { op: "delta_element"; element: string; delta: number }
  | { op: "set_target"; name: string; value: number; optimize?: string }
  | { op: "sweep"; vary: string; from: number; to: number; steps: number }
  // ── Bulk / canvas-wide ops (Global AI agentic flow) ──
  // Each one maps to a single store mutation OR a UI-side command bus
  // event.  Added 2026-05-26 alongside the agentic Global AI feature.
  | { op: "set_composition"; composition: Record<string, number> }
  | { op: "set_phase_system"; elements: string[] }
  | { op: "set_goals"; goals: Record<string, string> }
  | { op: "set_constraints"; constraints: Record<string, unknown> }
  | { op: "run_predict" }
  | { op: "run_optimization" }
  // ── Cloud compute (grain-structure tier) ──
  // Triggers the GrainStructureCard's submit→poll flow via the command bus.
  | { op: "simulate_grain_structure"; parameters: Record<string, unknown> };

/**
 * Buckets that the sprint cards write to so a session restore can
 * repopulate each card without re-running the (cost-bearing!)
 * simulation.  Each value is the raw result the card cached locally.
 */
export type SimulationBucket =
  | "phase"           // CALPHAD equilibrium  PhaseAssemblageCard
  | "scheil"          // Scheil-Gulliver       SolidificationCard
  | "ttt"             // Fe-C TTT diagram       TTTCard
  | "microstructure"  // Taichi dendrite        MicrostructureCard
  | "precipitation"   // KWN kinetics           PrecipitationCard
  | "grain_structure" // Neper polycrystal      GrainStructureCard (cloud)
  | "grain_growth"    // SPPARKS Potts growth   GrainGrowthCard (cloud)
  | "stress_strain"   // DAMASK CPFEM flow curve CPFEMStressStrainCard (cloud)
  | "inverse";        // BoTorch inverse design canvas page

export interface SimulationBucketEntry {
  result?:         unknown;          // primary fetch payload
  interpretation?: unknown;          // optional LLM AI Insights payload
}

/**
 * A long-running cloud compute job (Daytona-backed grain sims).  The
 * ComputeJobsProvider polls /api/compute/jobs/mine and writes the list here so
 * the header indicator + any card can react, and so a job survives navigating
 * away from the card that launched it.
 */
export interface CloudJob {
  job_id:       string;
  kind:         string;   // "grain_grow" | "grain_tessellate"
  status:       "queued" | "running" | "done" | "failed" | "timeout";
  created_at?:  string | null;
  finished_at?: string | null;
  result?:      unknown;
  error?:       string | null;
}


interface CanvasStore {
  session: DesignSession;
  selectedElement: SelectedElement | null;
  globalAIPanelOpen: boolean;
  localAIPopoverOpen: boolean;

  // Canvas state (lifted from page so actions can mutate it)
  composition: Record<string, number>;
  properties: Record<string, number | null>;
  targetDensityMax: number;
  targetMeltMin: number;
  sweepResult: SweepResult | null;
  sweepInProgress: boolean;

  // Sprint-card cached results — persisted to Supabase under
  // simulation_results so a session reload restores every card.
  simulationResults: Partial<Record<SimulationBucket, SimulationBucketEntry>>;
  setSimulationResult: (
    bucket: SimulationBucket,
    patch: SimulationBucketEntry,
  ) => void;

  // Long-running cloud jobs, kept in sync by ComputeJobsProvider (polls
  // /api/compute/jobs/mine).  Powers the header jobs indicator.
  cloudJobs: CloudJob[];
  setCloudJobs: (jobs: CloudJob[]) => void;

  // Session actions
  setGoals: (goals: Record<string, string>) => void;
  setConstraints: (constraints: Record<string, unknown>) => void;
  addComposition: (entry: Omit<CompositionEntry, "id" | "createdAt">) => void;
  toggleBookmark: (id: string) => void;
  toggleReject: (id: string) => void;

  // Canvas state setters
  setComposition: (c: Record<string, number>) => void;
  setProperties: (p: Record<string, number | null>) => void;
  setTargetDensityMax: (v: number) => void;
  setTargetMeltMin: (v: number) => void;

  // Selection
  selectElement: (el: SelectedElement | null) => void;

  // Chat
  addMessage: (msg: Omit<ChatMessage, "id" | "createdAt">) => void;
  // Mark a pill on a message as applied (idempotent — appending a
  // duplicate index is a no-op).
  markActionApplied: (messageId: string, actionIdx: number) => void;
  // Append an applied action to the unified design-decision trail.
  logAction: (entry: Omit<AppliedAction, "id" | "createdAt">) => void;

  // Panel toggles
  setGlobalAIPanelOpen: (open: boolean) => void;
  setLocalAIPopoverOpen: (open: boolean) => void;

  // Agentic action handler
  applyAction: (action: ExecutableAction) => Promise<{ ok: boolean; message: string }>;
}

let _idCounter = 0;
const uid = () => `${Date.now()}-${++_idCounter}`;

/* ── Helpers for composition arithmetic ───────────────────────── */

function normalizeCompositionAroundFixed(
  current: Record<string, number>,
  fixedElement: string,
  fixedValue: number
): Record<string, number> {
  // Clamp the fixed element to [0, 100]
  const clampedFixed = Math.max(0, Math.min(100, fixedValue));
  const remaining = 100 - clampedFixed;

  const others = Object.entries(current).filter(([el]) => el !== fixedElement);
  const otherSum = others.reduce((s, [, v]) => s + v, 0);

  const next: Record<string, number> = { [fixedElement]: clampedFixed };
  if (otherSum > 0) {
    for (const [el, v] of others) {
      next[el] = Math.round((v / otherSum) * remaining * 10) / 10;
    }
  } else {
    // If no other elements exist, just add the fixed one
    const eachShare = others.length > 0 ? remaining / others.length : 0;
    for (const [el] of others) next[el] = eachShare;
  }
  return next;
}

/* ── Store ────────────────────────────────────────────────────── */

export const useCanvasStore = create<CanvasStore>()(
  immer((set, get) => ({
    session: {
      id: uid(),
      name: "Untitled session",
      goals: {},
      constraints: {},
      compositions: [],
      messages: [],
      actionLog: [],
    },
    selectedElement: null,
    globalAIPanelOpen: false,
    localAIPopoverOpen: false,

    composition: { Al: 80, Mg: 10, Si: 10 },
    properties: {},
    targetDensityMax: 3.0,
    targetMeltMin: 800,
    sweepResult: null,
    sweepInProgress: false,

    simulationResults: {},
    setSimulationResult: (bucket, patch) =>
      set((s) => {
        // Merge so a card writing just `result` doesn't wipe its
        // previously-saved `interpretation` (and vice-versa).
        s.simulationResults[bucket] = {
          ...(s.simulationResults[bucket] ?? {}),
          ...patch,
        };
      }),

    cloudJobs: [],
    setCloudJobs: (jobs) => set((s) => { s.cloudJobs = jobs; }),

    setGoals: (goals) => set((s) => { s.session.goals = goals; }),
    setConstraints: (constraints) => set((s) => { s.session.constraints = constraints; }),

    addComposition: (entry) =>
      set((s) => {
        s.session.compositions.push({ ...entry, id: uid(), createdAt: new Date().toISOString() });
      }),

    toggleBookmark: (id) => set((s) => {
      const c = s.session.compositions.find((x) => x.id === id);
      if (c) c.bookmarked = !c.bookmarked;
    }),

    toggleReject: (id) => set((s) => {
      const c = s.session.compositions.find((x) => x.id === id);
      if (c) c.rejected = !c.rejected;
    }),

    setComposition: (c) => set((s) => { s.composition = c; }),
    setProperties: (p) => set((s) => { s.properties = p; }),
    setTargetDensityMax: (v) => set((s) => { s.targetDensityMax = v; }),
    setTargetMeltMin: (v) => set((s) => { s.targetMeltMin = v; }),

    selectElement: (el) => set((s) => {
      s.selectedElement = el;
      s.localAIPopoverOpen = el !== null;
    }),

    addMessage: (msg) => set((s) => {
      s.session.messages.push({ ...msg, id: uid(), createdAt: new Date().toISOString() });
    }),

    setGlobalAIPanelOpen: (open) => set((s) => { s.globalAIPanelOpen = open; }),
    setLocalAIPopoverOpen: (open) => set((s) => { s.localAIPopoverOpen = open; }),

    /* ── Agentic action handler ──────────────────────────────── */
    applyAction: async (action) => {
      const current = get().composition;

      if (action.op === "set_element") {
        const next = normalizeCompositionAroundFixed(current, action.element, action.value);
        set((s) => { s.composition = next; });
        // Auto-predict
        try {
          const res = await predictProperties(next);
          set((s) => { s.properties = res.properties; });
          get().addComposition({ composition: next, properties: res.properties, bookmarked: false, rejected: false });
          return { ok: true, message: `${action.element} set to ${action.value}%` };
        } catch {
          return { ok: true, message: `${action.element} → ${action.value}% (predict failed)` };
        }
      }

      if (action.op === "delta_element") {
        const newVal = (current[action.element] ?? 0) + action.delta;
        const next = normalizeCompositionAroundFixed(current, action.element, newVal);
        set((s) => { s.composition = next; });
        try {
          const res = await predictProperties(next);
          set((s) => { s.properties = res.properties; });
          get().addComposition({ composition: next, properties: res.properties, bookmarked: false, rejected: false });
          return { ok: true, message: `${action.element} ${action.delta > 0 ? "+" : ""}${action.delta}%` };
        } catch {
          return { ok: true, message: `${action.element} adjusted by ${action.delta}%` };
        }
      }

      if (action.op === "set_target") {
        if (action.name === "density_g_cm3") set((s) => { s.targetDensityMax = action.value; });
        else if (action.name === "melting_point_K") set((s) => { s.targetMeltMin = action.value; });
        return { ok: true, message: `Target ${action.name} → ${action.value}` };
      }

      if (action.op === "sweep") {
        const { vary, from, to, steps } = action;
        const stepSize = (to - from) / Math.max(1, steps - 1);
        const baseOthers = Object.fromEntries(
          Object.entries(current).filter(([el]) => el !== vary)
        );
        const baseOtherSum = Object.values(baseOthers).reduce((a, b) => a + b, 0);

        set((s) => { s.sweepInProgress = true; });

        const points: SweepPoint[] = [];
        for (let i = 0; i < steps; i++) {
          const value = from + i * stepSize;
          const remaining = Math.max(0, 100 - value);
          const composition: Record<string, number> = { [vary]: Math.round(value * 10) / 10 };
          if (baseOtherSum > 0) {
            for (const [el, v] of Object.entries(baseOthers)) {
              composition[el] = Math.round((v / baseOtherSum) * remaining * 10) / 10;
            }
          }
          try {
            const res = await predictProperties(composition);
            points.push({ variedValue: value, composition, properties: res.properties });
            // Live update so UI shows progress
            set((s) => {
              s.sweepResult = {
                vary, from, to,
                points: [...points],
                createdAt: new Date().toISOString(),
              };
            });
          } catch {
            points.push({ variedValue: value, composition, properties: {} });
          }
        }

        set((s) => { s.sweepInProgress = false; });
        return { ok: true, message: `Swept ${vary} from ${from}% to ${to}% (${steps} points)` };
      }

      // ── Bulk / canvas-wide ops (Global AI agentic flow) ──
      if (action.op === "set_composition") {
        set((s) => { s.composition = { ...action.composition }; });
        return { ok: true, message: "Composition updated" };
      }

      if (action.op === "set_phase_system") {
        // The "phase system" is the set of elements present in the
        // composition.  Preserve the weight-% of any element that's
        // already present (don't overwrite a deliberate composition with
        // a meaningless equal split) and distribute only the *remaining*
        // budget across genuinely new elements as a starting point.
        const next: Record<string, number> = {};
        let known = 0;
        const newEls: string[] = [];
        for (const el of action.elements) {
          if (typeof current[el] === "number") { next[el] = current[el]; known += current[el]; }
          else newEls.push(el);
        }
        const remaining = Math.max(0, 100 - known);
        if (newEls.length > 0) {
          const share = Math.round((remaining / newEls.length) * 10) / 10;
          for (const el of newEls) next[el] = share;
        }
        set((s) => { s.composition = next; });
        return { ok: true, message: `Phase system → ${action.elements.join("-")}` };
      }

      if (action.op === "set_goals") {
        set((s) => { s.session.goals = { ...s.session.goals, ...action.goals }; });
        return { ok: true, message: "Goals updated" };
      }

      if (action.op === "set_constraints") {
        set((s) => { s.session.constraints = { ...s.session.constraints, ...action.constraints }; });
        return { ok: true, message: "Constraints updated" };
      }

      // ── Canvas-command bus (run_predict / run_optimization) ──
      // These don't have direct store mutations; they trigger the
      // existing buttons on the canvas page via a DOM custom event so
      // we don't have to plumb refs through three component layers.
      if (action.op === "run_predict") {
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("leilmat:ai_command", {
            detail: { kind: "predict" },
          }));
        }
        return { ok: true, message: "Predicting properties…" };
      }

      if (action.op === "run_optimization") {
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("leilmat:ai_command", {
            detail: { kind: "optimize" },
          }));
        }
        return { ok: true, message: "Running optimization…" };
      }

      if (action.op === "simulate_grain_structure") {
        // GrainStructureCard listens for this and runs its submit→poll flow.
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("leilmat:ai_command", {
            detail: { kind: "grain_structure", parameters: action.parameters },
          }));
        }
        return { ok: true, message: "Simulating grain structure…" };
      }

      return { ok: false, message: "Unknown action" };
    },

    markActionApplied: (messageId, actionIdx) => set((s) => {
      const msg = s.session.messages.find((m) => m.id === messageId);
      if (!msg) return;
      if (!msg.appliedActionIdx) msg.appliedActionIdx = [];
      if (!msg.appliedActionIdx.includes(actionIdx)) {
        msg.appliedActionIdx.push(actionIdx);
      }
    }),

    logAction: (entry) => set((s) => {
      if (!s.session.actionLog) s.session.actionLog = [];
      s.session.actionLog.push({
        ...entry,
        id:        uid(),
        createdAt: new Date().toISOString(),
      });
    }),
  }))
);
