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
  | { op: "set_element"; element: string; value: number }
  | { op: "delta_element"; element: string; delta: number }
  | { op: "set_target"; name: string; value: number; optimize?: string }
  | { op: "sweep"; vary: string; from: number; to: number; steps: number };

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

      return { ok: false, message: "Unknown action" };
    },
  }))
);
