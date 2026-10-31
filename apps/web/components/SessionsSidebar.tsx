/**
 * SessionsSidebar — slide-out drawer listing the user's design sessions.
 *
 * Mirrors LeilFlowsheet's project drawer ergonomics:
 *   * Triggered by a header button (FolderOpen icon)
 *   * Lists sessions newest-first with name + relative time
 *   * Active session is highlighted (gold accent for LeilMat)
 *   * "+ New session" pinned at the top
 *   * Inline rename (double-click)
 *   * Delete via row-hover trash button (confirm prompt)
 *
 * Hidden entirely when the user is signed-out — auto-save is
 * Supabase-only; without a session there's nothing to show.
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Folder, Plus, Trash2, X, Pencil } from "lucide-react";

import type { DesignSessionRow } from "@/services/sessionService";
import type { SessionPersistenceState } from "@/lib/hooks/useSessionPersistence";


function relTime(iso: string): string {
  const t = new Date(iso).getTime();
  const secs = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (secs < 60)   return "just now";
  const mins = Math.floor(secs / 60);
  if (mins < 60)   return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)    return `${hrs} h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30)   return `${days} d ago`;
  return new Date(iso).toLocaleDateString();
}


export function SessionsSidebar({
  open,
  onClose,
  persistence,
}: {
  open:        boolean;
  onClose:     () => void;
  persistence: SessionPersistenceState;
}) {
  const {
    sessions, currentSessionId, isHydrating,
    createNewSession, switchToSession, renameSession, deleteSession,
    refreshList,
  } = persistence;

  const [renamingId,  setRenamingId]  = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  // Refresh the list every time the drawer opens so the timestamps
  // and any newly-created rows from another tab show up.
  useEffect(() => {
    if (open) void refreshList();
  }, [open, refreshList]);

  // Esc to close
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const startRename = useCallback((row: DesignSessionRow) => {
    setRenamingId(row.id);
    setRenameValue(row.name);
  }, []);

  const commitRename = useCallback(async () => {
    if (renamingId && renameValue.trim() && renamingId === currentSessionId) {
      await renameSession(renameValue.trim());
    }
    setRenamingId(null);
    setRenameValue("");
  }, [renamingId, renameValue, currentSessionId, renameSession]);

  const onDeleteRow = useCallback(async (row: DesignSessionRow) => {
    const ok = window.confirm(
      `Delete "${row.name}"?  This cannot be undone.`,
    );
    if (!ok) return;
    await deleteSession(row.id);
  }, [deleteSession]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]"
        onClick={onClose}
      />
      {/* Drawer */}
      <aside
        className="fixed top-0 left-0 z-50 h-full w-80 bg-surface border-r border-line flex flex-col"
        role="dialog"
        aria-label="Design sessions"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 h-14 border-b border-line">
          <div className="flex items-center gap-2">
            <Folder size={14} className="text-[hsl(var(--accent))]" />
            <span className="text-[13px] font-semibold text-fg">
              Design sessions
            </span>
          </div>
          <button
            onClick={onClose}
            aria-label="Close sessions sidebar"
            className="text-muted hover:text-fg transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* New-session button */}
        <button
          onClick={async () => {
            await createNewSession();
            onClose();
          }}
          className="mx-3 mt-3 flex items-center gap-2 px-3 py-2 rounded-md text-[12px] font-semibold border transition-colors"
          style={{
            background:  "hsl(var(--accent) / 0.15)",
            color:       "hsl(var(--accent))",
            borderColor: "hsl(var(--accent) / 0.4)",
          }}
        >
          <Plus size={13} />
          New session
        </button>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
          {isHydrating && sessions.length === 0 ? (
            <p className="text-[11px] text-subtle text-center py-4">Loading…</p>
          ) : sessions.length === 0 ? (
            <p className="text-[11px] text-subtle text-center py-4">
              No sessions yet — create one above.
            </p>
          ) : (
            sessions.map((row) => {
              const active = row.id === currentSessionId;
              const renaming = renamingId === row.id;
              return (
                <div
                  key={row.id}
                  className={`group relative px-2.5 py-2 rounded-md border transition-colors ${
                    active
                      ? "bg-fg/[0.06] border-[hsl(var(--accent)/0.4)]"
                      : "bg-fg/[0.02] border-line hover:bg-fg/[0.04]"
                  }`}
                >
                  {renaming ? (
                    <form
                      onSubmit={(e) => { e.preventDefault(); void commitRename(); }}
                      className="flex items-center gap-1"
                    >
                      <input
                        autoFocus
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onBlur={commitRename}
                        className="flex-1 bg-transparent text-[12px] text-fg outline-none border-b border-[hsl(var(--accent)/0.6)] pb-0.5"
                      />
                    </form>
                  ) : (
                    <button
                      onClick={async () => {
                        if (!active) {
                          await switchToSession(row.id);
                          onClose();
                        }
                      }}
                      onDoubleClick={(e) => { e.preventDefault(); if (active) startRename(row); }}
                      className="w-full text-left"
                      title={active ? "Double-click to rename" : "Click to open"}
                    >
                      <p className={`text-[12px] font-medium truncate ${
                        active ? "text-[hsl(var(--accent))]" : "text-fg"
                      }`}>
                        {row.name}
                      </p>
                      <p className="text-[10px] text-subtle mt-0.5 font-mono">
                        {relTime(row.updated_at)}
                      </p>
                    </button>
                  )}

                  {/* Hover actions — only on the active row to avoid
                       footguns on background sessions */}
                  {active && !renaming && (
                    <div className="absolute top-1.5 right-1.5 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => { e.stopPropagation(); startRename(row); }}
                        aria-label="Rename"
                        className="p-1 rounded text-muted hover:text-fg hover:bg-fg/[0.06]"
                      >
                        <Pencil size={11} />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); void onDeleteRow(row); }}
                        aria-label="Delete session"
                        className="p-1 rounded text-bad hover:text-bad hover:bg-bad/10"
                      >
                        <Trash2 size={11} />
                      </button>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer note */}
        <div className="px-4 py-3 border-t border-line">
          <p className="text-[10px] text-subtle leading-snug">
            Auto-saves to Supabase 3 s after each edit.  Row-level
            security restricts each session to its owner.
          </p>
        </div>
      </aside>
    </>
  );
}
