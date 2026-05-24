/**
 * CRUD wrapper for the design_sessions Supabase table.
 *
 * Pattern ported verbatim from LeilFlowsheet/services/projectService.ts.
 * Two execution modes:
 *
 *   * **Supabase configured** — direct supabase-js calls.  RLS
 *     restricts every query to the current user's rows.
 *   * **localStorage fallback** — used during local dev when no
 *     Supabase env is set, and as a graceful-degradation path when
 *     the user is offline.  Keyed by user_id so multiple test
 *     accounts don't collide.
 *
 * The DB row shape (DesignSessionRow) is intentionally decoupled
 * from the Zustand store shape (apps/web/lib/store.ts:DesignSession).
 * Phase E3's useSessionPersistence() hook handles the translation.
 *
 * Reference: ../supabase/migrations/20260524000000_create_design_sessions_table.sql
 */
import { supabase, hasSupabaseConfig } from "./supabase";


export interface DesignSessionRow {
  id:                  string;
  user_id:             string;
  name:                string;
  description?:        string | null;
  canvas_state:        Record<string, unknown>;
  session_data:        Record<string, unknown>;
  messages:            unknown[];
  simulation_results:  Record<string, unknown>;
  created_at:          string;
  updated_at:          string;
}

export type DesignSessionInsert = Omit<
  DesignSessionRow,
  "id" | "created_at" | "updated_at"
>;
export type DesignSessionUpdate = Partial<
  Omit<DesignSessionRow, "id" | "user_id" | "created_at" | "updated_at">
>;


// ─────────────────────────────────────────────────────────────────────
// localStorage fallback
// ─────────────────────────────────────────────────────────────────────

const LOCAL_STORAGE_KEY = "leilmat_local_design_sessions";

function getLocalSessions(): DesignSessionRow[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as DesignSessionRow[]) : [];
  } catch {
    return [];
  }
}

function saveLocalSessions(rows: DesignSessionRow[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(rows));
  } catch {
    // localStorage quota or private-mode failure — soft-fail
  }
}


// ─────────────────────────────────────────────────────────────────────
// Public service surface
// ─────────────────────────────────────────────────────────────────────

export const sessionService = {

  /** List the user's sessions, most-recently-updated first. */
  async getSessions(userId: string): Promise<DesignSessionRow[]> {
    if (hasSupabaseConfig) {
      const { data, error } = await supabase
        .from("design_sessions")
        .select("*")
        .eq("user_id", userId)
        .order("updated_at", { ascending: false });
      if (error) throw error;
      return (data as DesignSessionRow[]) ?? [];
    }
    return getLocalSessions().filter(s => s.user_id === userId);
  },

  /** Load one session by id.  Returns null when not found. */
  async getSession(id: string): Promise<DesignSessionRow | null> {
    if (hasSupabaseConfig) {
      const { data, error } = await supabase
        .from("design_sessions")
        .select("*")
        .eq("id", id)
        .maybeSingle();
      if (error) throw error;
      return (data as DesignSessionRow | null) ?? null;
    }
    return getLocalSessions().find(s => s.id === id) ?? null;
  },

  /**
   * Insert a brand-new session.  The Supabase server fills `id`,
   * `created_at`, `updated_at` — never pass them.
   */
  async createSession(row: DesignSessionInsert): Promise<DesignSessionRow> {
    if (hasSupabaseConfig) {
      const { data, error } = await supabase
        .from("design_sessions")
        .insert([row])
        .select()
        .single();
      if (error) throw error;
      return data as DesignSessionRow;
    }
    const now = new Date().toISOString();
    const fresh: DesignSessionRow = {
      ...row,
      id:         (typeof crypto !== "undefined" && "randomUUID" in crypto)
                    ? crypto.randomUUID()
                    : `local-${Date.now()}`,
      created_at: now,
      updated_at: now,
    };
    const all = getLocalSessions();
    saveLocalSessions([fresh, ...all]);
    return fresh;
  },

  /**
   * Partial update.  Server-side trigger refreshes updated_at on
   * every UPDATE, so the local fallback mirrors that explicitly.
   */
  async updateSession(
    id: string,
    updates: DesignSessionUpdate,
  ): Promise<DesignSessionRow> {
    if (hasSupabaseConfig) {
      const { data, error } = await supabase
        .from("design_sessions")
        .update({ ...updates, updated_at: new Date().toISOString() })
        .eq("id", id)
        .select()
        .single();
      if (error) throw error;
      return data as DesignSessionRow;
    }
    const all = getLocalSessions();
    const idx = all.findIndex(s => s.id === id);
    if (idx === -1) throw new Error(`Local session ${id} not found`);
    const next: DesignSessionRow = {
      ...all[idx],
      ...updates,
      updated_at: new Date().toISOString(),
    };
    all[idx] = next;
    saveLocalSessions(all);
    return next;
  },

  /** Delete a session.  Cascade is handled by the FK CASCADE on user_id. */
  async deleteSession(id: string): Promise<void> {
    if (hasSupabaseConfig) {
      const { error } = await supabase
        .from("design_sessions")
        .delete()
        .eq("id", id);
      if (error) throw error;
      return;
    }
    saveLocalSessions(getLocalSessions().filter(s => s.id !== id));
  },
};
