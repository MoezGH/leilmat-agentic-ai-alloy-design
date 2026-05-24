-- design_sessions — LeilMat's per-user design workspace.
--
-- Pattern ported verbatim from LeilFlowsheet's projects table
-- (supabase/migrations/20260409171936_create_projects_table.sql).  One
-- row per "design session", JSONB columns for the heavy state, RLS
-- so users can only see their own rows.
--
-- Schema notes (vs the dead apps/api/data/models.py — to be removed
-- in Phase E5):
--   * The old SQLAlchemy schema had three tables (design_sessions,
--     saved_compositions, chat_messages) with FK relationships.  Here
--     we flatten to ONE row with JSONB columns — same pattern as
--     LeilFlowsheet.  Trades joinability for atomic writes; row sizes
--     stay bounded because microstructure frames are the only big
--     payload (~1-3 MB at Publication preset) and the rest is light.
--   * user_id is a UUID FK to auth.users(id) — no separate users
--     table on LeilMat's side, identity flows from Supabase Auth.

CREATE TABLE public.design_sessions (
  id              uuid       DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id         uuid       REFERENCES auth.users(id) ON DELETE CASCADE,
  name            text       NOT NULL DEFAULT 'Untitled session',
  description     text,

  -- Current working state of the canvas: composition sliders,
  -- predicted properties, inverse-design targets, last sweep result.
  canvas_state    jsonb      NOT NULL DEFAULT '{}'::jsonb,

  -- Session-level history: goals, constraints, bookmarked/rejected
  -- compositions explored during this session.
  session_data    jsonb      NOT NULL DEFAULT '{}'::jsonb,

  -- Chat history (Local AI + Global AI messages).
  messages        jsonb      NOT NULL DEFAULT '[]'::jsonb,

  -- Last successful result from each cost-bearing card so the user
  -- doesn't pay twice when they reopen a session:
  --   {phase, scheil, ttt, microstructure, precipitation, inverse}
  simulation_results jsonb   NOT NULL DEFAULT '{}'::jsonb,

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX design_sessions_user_id_updated_at_idx
  ON public.design_sessions (user_id, updated_at DESC);


-- ─────────────────────────────────────────────────────────────────────
-- Row-level security: users see only their own sessions
-- ─────────────────────────────────────────────────────────────────────

ALTER TABLE public.design_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own design sessions"
  ON public.design_sessions FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own design sessions"
  ON public.design_sessions FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own design sessions"
  ON public.design_sessions FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own design sessions"
  ON public.design_sessions FOR DELETE
  USING (auth.uid() = user_id);


-- ─────────────────────────────────────────────────────────────────────
-- updated_at trigger — mirrors LeilFlowsheet's handle_updated_at()
-- ─────────────────────────────────────────────────────────────────────

-- The function is shared across sub-app tables, so CREATE OR REPLACE
-- (LeilFlowsheet's migration already creates it; idempotent here).
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_design_sessions_updated_at
  BEFORE UPDATE ON public.design_sessions
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_updated_at();
