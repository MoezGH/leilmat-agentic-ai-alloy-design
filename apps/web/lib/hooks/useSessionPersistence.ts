/**
 * useSessionPersistence — wires the Zustand canvas store to Supabase.
 *
 * Behaviour (mirrors LeilFlowsheet/App.tsx — 3 s debounce for state):
 *
 *   1. **On mount** (or when the user signs in)
 *      * If localStorage has ``leilmat_last_session_id``, try to load
 *        that row from Supabase.
 *      * Otherwise, fetch the user's most-recent session via
 *        sessionService.getSessions().
 *      * If still nothing, INSERT a fresh "Untitled session" row
 *        seeded from the current Zustand store.
 *      * Hydrate the store from whatever row we ended up with.
 *
 *   2. **On every store mutation** (Zustand subscribe → diff →
 *      debounce 3 s):
 *      * Pack the persistable fields into a DesignSessionRow update
 *        and call sessionService.updateSession(id, …).
 *      * Surface progress via saveState ("idle" | "saving" | "saved"
 *        | "error") + lastSavedAt for the UI's save indicator.
 *
 *   3. **Imperative API** (returned by the hook so the UI can drive
 *      session-list actions): createNewSession, switchToSession,
 *      renameSession, deleteSession, refreshList.
 *
 * Persistable fields (what gets serialised into the DB row):
 *   * canvas_state        — current composition / properties /
 *                            targetDensityMax / targetMeltMin /
 *                            sweepResult
 *   * session_data        — goals / constraints / compositions[]
 *                            (the bookmarked-history list)
 *   * messages            — chat history (Local AI + Global AI)
 *   * simulation_results  — NOT auto-saved by Zustand subscribe (the
 *                            sprint cards' results aren't in the
 *                            store); the cards can call
 *                            persistResultPatch() to opt in.
 *
 * Reference: ../../services/sessionService.ts
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useUser } from "@/components/providers/AuthProvider";
import {
  sessionService,
  type DesignSessionRow,
  type DesignSessionUpdate,
} from "@/services/sessionService";
import { useCanvasStore } from "@/lib/store";


export type SaveState = "idle" | "saving" | "saved" | "error";

const DEBOUNCE_MS         = 3_000;
const LAST_SESSION_KEY    = "leilmat_last_session_id";


// ─────────────────────────────────────────────────────────────────────
// Translation helpers: Zustand store ↔ DB row
// ─────────────────────────────────────────────────────────────────────

/** Pack the persistable slices of the store into a DB-row update. */
function packStoreSnapshot(): DesignSessionUpdate {
  const s = useCanvasStore.getState();
  return {
    name: s.session.name,
    canvas_state: {
      composition:        s.composition,
      properties:         s.properties,
      target_density_max: s.targetDensityMax,
      target_melt_min:    s.targetMeltMin,
      sweep_result:       s.sweepResult,
    },
    session_data: {
      goals:        s.session.goals,
      constraints:  s.session.constraints,
      compositions: s.session.compositions,
    },
    messages: s.session.messages,
    simulation_results: s.simulationResults as Record<string, unknown>,
  };
}

/** Hydrate the Zustand store from a DB row.  Soft-merges — fields
 * missing on the row keep the current store value rather than going
 * undefined. */
function hydrateStoreFromRow(row: DesignSessionRow) {
  const setter = useCanvasStore.setState;
  setter((s) => {
    s.session.id           = row.id;
    s.session.name         = row.name;
    const sd = (row.session_data ?? {}) as Record<string, unknown>;
    if (sd.goals)        s.session.goals        = sd.goals as typeof s.session.goals;
    if (sd.constraints)  s.session.constraints  = sd.constraints as typeof s.session.constraints;
    if (Array.isArray(sd.compositions))
      s.session.compositions = sd.compositions as typeof s.session.compositions;

    if (Array.isArray(row.messages))
      s.session.messages = row.messages as typeof s.session.messages;

    const cs = (row.canvas_state ?? {}) as Record<string, unknown>;
    if (cs.composition)        s.composition        = cs.composition        as typeof s.composition;
    if (cs.properties)         s.properties         = cs.properties         as typeof s.properties;
    if (typeof cs.target_density_max === "number") s.targetDensityMax = cs.target_density_max;
    if (typeof cs.target_melt_min    === "number") s.targetMeltMin    = cs.target_melt_min;
    if ("sweep_result" in cs)  s.sweepResult        = cs.sweep_result       as typeof s.sweepResult;

    // Per-card simulation results — keyed by bucket name (phase / scheil
    // / ttt / microstructure / precipitation / inverse).  Cards seed
    // their useState from here on mount, so a refreshed page shows the
    // last result without re-running the (cost-bearing!) simulation.
    if (row.simulation_results && typeof row.simulation_results === "object") {
      s.simulationResults = row.simulation_results as typeof s.simulationResults;
    } else {
      s.simulationResults = {};
    }
  });
}


// ─────────────────────────────────────────────────────────────────────
// Public hook
// ─────────────────────────────────────────────────────────────────────

export interface SessionPersistenceState {
  saveState:        SaveState;
  lastSavedAt:      Date | null;
  currentSessionId: string | null;
  sessions:         DesignSessionRow[];
  isHydrating:      boolean;

  // Imperative actions
  createNewSession: (name?: string) => Promise<void>;
  switchToSession:  (id: string)    => Promise<void>;
  renameSession:    (name: string)  => Promise<void>;
  deleteSession:    (id: string)    => Promise<void>;
  refreshList:      ()              => Promise<void>;
  /** Carve out a server-side patch that bypasses the debounce — used
   *  by the sprint cards to persist their simulation result the
   *  instant it lands. */
  persistResultPatch: (
    bucket: "phase" | "scheil" | "ttt" | "microstructure"
          | "precipitation" | "inverse",
    value: unknown,
  ) => Promise<void>;
}


export function useSessionPersistence(): SessionPersistenceState {
  const { user, loading: userLoading } = useUser();

  const [saveState,        setSaveState]        = useState<SaveState>("idle");
  const [lastSavedAt,      setLastSavedAt]      = useState<Date | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sessions,         setSessions]         = useState<DesignSessionRow[]>([]);
  const [isHydrating,      setIsHydrating]      = useState(true);

  // Refs to read inside the Zustand-subscribe callback without
  // re-binding every render.
  const sessionIdRef = useRef<string | null>(null);
  const debounceRef  = useRef<number | null>(null);
  const skipNextRef  = useRef(false);   // set during hydrate to avoid save-on-load

  // Keep the ref in sync with state.
  useEffect(() => { sessionIdRef.current = currentSessionId; }, [currentSessionId]);

  // ─── Bootstrap: load-or-create on mount / sign-in ───────────────
  useEffect(() => {
    if (userLoading) return;
    if (!user) {
      // Signed-out — nothing to hydrate from Supabase.  Local
      // changes go into the in-memory store and would be lost on
      // refresh; the LeilHeader's sign-in CTA is the prompt.
      setIsHydrating(false);
      return;
    }

    let cancelled = false;
    (async () => {
      setIsHydrating(true);
      try {
        // 1. Refresh the session list for the sidebar
        const list = await sessionService.getSessions(user.id);
        if (cancelled) return;
        setSessions(list);

        // 2. Pick which session to open
        const lastId = (typeof window !== "undefined")
          ? localStorage.getItem(LAST_SESSION_KEY) : null;
        let row: DesignSessionRow | null = null;
        if (lastId) row = await sessionService.getSession(lastId);
        if (!row && list.length > 0) row = list[0];

        // 3. None yet — create the first one seeded from the current store
        if (!row) {
          const seed   = packStoreSnapshot();
          row = await sessionService.createSession({
            user_id:            user.id,
            name:               seed.name ?? "Untitled session",
            canvas_state:       (seed.canvas_state       ?? {}) as Record<string, unknown>,
            session_data:       (seed.session_data       ?? {}) as Record<string, unknown>,
            messages:           (seed.messages           ?? []) as unknown[],
            simulation_results: {} as Record<string, unknown>,
          });
          setSessions((prev) => [row!, ...prev]);
        }

        if (cancelled) return;

        // 4. Hydrate
        skipNextRef.current = true;
        hydrateStoreFromRow(row);
        setCurrentSessionId(row.id);
        if (typeof window !== "undefined")
          localStorage.setItem(LAST_SESSION_KEY, row.id);
        setLastSavedAt(new Date(row.updated_at));
        setSaveState("saved");
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error("[session] bootstrap failed", err);
        setSaveState("error");
      } finally {
        if (!cancelled) setIsHydrating(false);
      }
    })();

    return () => { cancelled = true; };
  }, [user, userLoading]);

  // ─── Auto-save: subscribe to Zustand mutations ──────────────────
  useEffect(() => {
    if (!user || !currentSessionId) return;

    const unsubscribe = useCanvasStore.subscribe((state, prevState) => {
      // Cheap diff — skip when only ephemeral UI fields changed
      // (selectedElement, panel open flags, sweepInProgress).
      const persistableChanged =
           state.composition       !== prevState.composition
        || state.properties        !== prevState.properties
        || state.targetDensityMax  !== prevState.targetDensityMax
        || state.targetMeltMin     !== prevState.targetMeltMin
        || state.sweepResult       !== prevState.sweepResult
        || state.session.name      !== prevState.session.name
        || state.session.goals     !== prevState.session.goals
        || state.session.constraints !== prevState.session.constraints
        || state.session.compositions !== prevState.session.compositions
        || state.session.messages  !== prevState.session.messages
        // simulationResults is the top-level object the sprint cards
        // write to via setSimulationResult.  Immer + reference-swap
        // means a new top-level object on each card mutation.
        || state.simulationResults !== prevState.simulationResults;
      if (!persistableChanged) return;

      if (skipNextRef.current) { skipNextRef.current = false; return; }

      if (debounceRef.current != null) window.clearTimeout(debounceRef.current);
      setSaveState("saving");
      debounceRef.current = window.setTimeout(async () => {
        const id = sessionIdRef.current;
        if (!id) return;
        try {
          await sessionService.updateSession(id, packStoreSnapshot());
          setSaveState("saved");
          setLastSavedAt(new Date());
        } catch (err) {
          // eslint-disable-next-line no-console
          console.error("[session] auto-save failed", err);
          setSaveState("error");
        }
      }, DEBOUNCE_MS);
    });

    return () => {
      unsubscribe();
      if (debounceRef.current != null) {
        window.clearTimeout(debounceRef.current);
        debounceRef.current = null;
      }
    };
  }, [user, currentSessionId]);

  // ─── Imperative actions ─────────────────────────────────────────

  const refreshList = useCallback(async () => {
    if (!user) return;
    try { setSessions(await sessionService.getSessions(user.id)); }
    catch (err) { /* eslint-disable-next-line no-console */ console.error("[session] refreshList", err); }
  }, [user]);

  const createNewSession = useCallback(async (name?: string) => {
    if (!user) return;
    try {
      const row = await sessionService.createSession({
        user_id:            user.id,
        name:               name ?? "Untitled session",
        canvas_state:       { composition: { Al: 80, Mg: 10, Si: 10 }, properties: {},
                               target_density_max: 3.0, target_melt_min: 800,
                               sweep_result: null } as Record<string, unknown>,
        session_data:       { goals: {}, constraints: {}, compositions: [] } as Record<string, unknown>,
        messages:           [] as unknown[],
        simulation_results: {} as Record<string, unknown>,
      });
      setSessions((prev) => [row, ...prev]);
      skipNextRef.current = true;
      hydrateStoreFromRow(row);
      setCurrentSessionId(row.id);
      if (typeof window !== "undefined")
        localStorage.setItem(LAST_SESSION_KEY, row.id);
      setLastSavedAt(new Date(row.updated_at));
      setSaveState("saved");
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[session] createNewSession", err);
      setSaveState("error");
    }
  }, [user]);

  const switchToSession = useCallback(async (id: string) => {
    if (!user) return;
    try {
      const row = await sessionService.getSession(id);
      if (!row) return;
      skipNextRef.current = true;
      hydrateStoreFromRow(row);
      setCurrentSessionId(row.id);
      if (typeof window !== "undefined")
        localStorage.setItem(LAST_SESSION_KEY, row.id);
      setLastSavedAt(new Date(row.updated_at));
      setSaveState("saved");
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[session] switchToSession", err);
      setSaveState("error");
    }
  }, [user]);

  const renameSession = useCallback(async (name: string) => {
    if (!user || !sessionIdRef.current) return;
    useCanvasStore.setState((s) => { s.session.name = name; });   // optimistic
    try {
      await sessionService.updateSession(sessionIdRef.current, { name });
      setSessions((prev) => prev.map(r => r.id === sessionIdRef.current
        ? { ...r, name, updated_at: new Date().toISOString() } : r));
      setLastSavedAt(new Date());
      setSaveState("saved");
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[session] renameSession", err);
      setSaveState("error");
    }
  }, [user]);

  const deleteSession = useCallback(async (id: string) => {
    if (!user) return;
    try {
      await sessionService.deleteSession(id);
      setSessions((prev) => prev.filter(s => s.id !== id));
      // If we deleted the active one, switch to next-most-recent or create fresh.
      if (id === sessionIdRef.current) {
        const remaining = await sessionService.getSessions(user.id);
        if (remaining.length > 0) {
          await switchToSession(remaining[0].id);
        } else {
          await createNewSession();
        }
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[session] deleteSession", err);
      setSaveState("error");
    }
  }, [user, switchToSession, createNewSession]);

  const persistResultPatch = useCallback(async (
    bucket: "phase" | "scheil" | "ttt" | "microstructure"
          | "precipitation" | "inverse",
    value: unknown,
  ) => {
    const id = sessionIdRef.current;
    if (!user || !id) return;
    setSaveState("saving");
    try {
      // Read-modify-write rather than nested-JSONB SQL, since the
      // result blob is small enough that a whole-row update is fine.
      const row = await sessionService.getSession(id);
      const next = { ...(row?.simulation_results ?? {}), [bucket]: value };
      await sessionService.updateSession(id, { simulation_results: next });
      setLastSavedAt(new Date());
      setSaveState("saved");
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[session] persistResultPatch", err);
      setSaveState("error");
    }
  }, [user]);

  return {
    saveState,
    lastSavedAt,
    currentSessionId,
    sessions,
    isHydrating,
    createNewSession,
    switchToSession,
    renameSession,
    deleteSession,
    refreshList,
    persistResultPatch,
  };
}
