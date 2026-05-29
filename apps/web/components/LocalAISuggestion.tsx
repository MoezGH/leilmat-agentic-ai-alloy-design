"use client";
/**
 * LocalAISuggestion — popover that anchors next to a selected canvas
 * element (a property bar, composition slider, phase region…) and
 * streams a short, targeted LLM analysis with one-click action pills.
 *
 * Shares the agentic-actions wire format with Global AI:
 *   * Streamed text consists of a short prose explanation
 *   * Followed by a fenced ```actions``` JSON block
 *   * ``parseAssistantMessage`` extracts both
 *   * Pills render via the shared ``AIActionPill`` components
 *
 * Differences from Global AI:
 *   * Popover, not side-panel — narrower (360 px)
 *   * Transient — the popover closes on outside-click or X, and we
 *     don't persist the response in ``session.messages`` (so applied-
 *     state is tracked in local component state, not via
 *     ``markActionApplied``)
 *   * Smart positioning relative to the anchor + Global AI panel
 */
import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, X, Loader2 } from "lucide-react";

import { useCanvasStore } from "@/lib/store";
import { streamLocalAI } from "@/lib/api";
import { useSession } from "@/components/providers/AuthProvider";
import { parseAssistantMessage } from "@/lib/ai/actions";
import { AIActionPill, AIActionApplyAll } from "@/components/AIActionPill";
import { MarkdownMessage } from "@/components/MarkdownMessage";


const POPOVER_W = 380;
const POPOVER_MAX_H = 480;
const GAP = 12;
const ACCENT_HSL = "38 96% 60%";


export function LocalAISuggestion() {
  const { selectedElement, localAIPopoverOpen, selectElement, globalAIPanelOpen } = useCanvasStore();
  const { session: authSession } = useSession();
  const authToken = authSession?.access_token ?? null;

  const [rawText, setRawText]     = useState("");
  const [loading, setLoading]     = useState(false);
  const [error,   setError]       = useState<string | null>(null);
  // Local applied-action tracking.  The popover is transient (closes on
  // outside-click), so we don't persist this in the store — a small
  // Set of indices, reset whenever a new selection opens the popover.
  const [appliedIdx, setAppliedIdx] = useState<number[]>([]);

  // Reset + restream whenever the selection changes.
  useEffect(() => {
    if (!selectedElement || !localAIPopoverOpen) return;
    setRawText("");
    setError(null);
    setLoading(true);
    setAppliedIdx([]);

    (async () => {
      try {
        for await (const chunk of streamLocalAI(selectedElement, undefined, authToken)) {
          setRawText((prev) => prev + chunk);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    })();
  }, [selectedElement, localAIPopoverOpen, authToken]);

  // Parse the streamed text into prose + agentic actions.  Re-runs on
  // every render but the regex is cheap (≤ a couple of hundred chars).
  const { cleanText, actions } = useMemo(
    () => parseAssistantMessage(rawText),
    [rawText],
  );

  // Smart positioning — anchor next to the selected canvas element,
  // avoiding the Global AI side panel if it's open.
  const position = useMemo(() => {
    if (typeof window === "undefined") return { left: 100, top: 100 };
    const anchor = selectedElement?.anchor;
    if (!anchor) {
      return {
        left: Math.max(20, window.innerWidth  / 2 - POPOVER_W     / 2),
        top:  Math.max(80, window.innerHeight / 2 - POPOVER_MAX_H / 2),
      };
    }
    const rightBoundary  = window.innerWidth  - (globalAIPanelOpen ? 420 : 0) - 20;
    const bottomBoundary = window.innerHeight - 20;

    let left = anchor.x + GAP;
    if (left + POPOVER_W > rightBoundary) left = anchor.x - GAP - POPOVER_W;
    left = Math.max(20, left);
    if (left + POPOVER_W > rightBoundary) left = rightBoundary - POPOVER_W;

    let top = anchor.y - 60;
    top = Math.max(80, top);
    if (top + POPOVER_MAX_H > bottomBoundary) top = bottomBoundary - POPOVER_MAX_H;
    return { left, top };
  }, [selectedElement, localAIPopoverOpen, globalAIPanelOpen]);

  return (
    <AnimatePresence>
      {localAIPopoverOpen && selectedElement && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 4 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 4 }}
          transition={{ duration: 0.12 }}
          style={{
            position:  "fixed",
            left:      position.left,
            top:       position.top,
            width:     POPOVER_W,
            maxHeight: POPOVER_MAX_H,
            zIndex:    50,
            // Expose --accent so the AIActionPill / AIActionApplyAll
            // children can pick up the warm-gold colour.
            ["--accent" as keyof React.CSSProperties as string]: ACCENT_HSL,
          } as React.CSSProperties}
          className="rounded-xl bg-[#15171d] border border-white/15 shadow-2xl shadow-black/60 overflow-hidden flex flex-col"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-white/10 shrink-0 bg-gradient-to-r from-[hsl(var(--accent)/0.08)] to-transparent">
            <div className="flex items-center gap-2">
              <div
                className="w-5 h-5 rounded-md flex items-center justify-center"
                style={{
                  background: "hsl(var(--accent) / 0.18)",
                  border:     "1px solid hsl(var(--accent) / 0.3)",
                }}
              >
                <Sparkles size={10} style={{ color: "hsl(var(--accent))" }} />
              </div>
              <div>
                <div className="text-[12px] font-semibold text-slate-100 leading-none">Local AI</div>
                <div className="text-[10px] text-slate-500 mt-0.5 font-medium uppercase tracking-wider">
                  {selectedElement.type.replace(/_/g, " ")}
                </div>
              </div>
            </div>
            <button
              onClick={() => selectElement(null)}
              className="p-1 rounded-md text-slate-500 hover:text-white hover:bg-white/10 transition-all"
              aria-label="Close"
            >
              <X size={13} />
            </button>
          </div>

          {/* Content */}
          <div className="px-3.5 py-3 space-y-3 overflow-y-auto flex-1">

            {/* Loading state — before any text streams in */}
            {loading && !cleanText && !error && (
              <div className="flex items-center gap-2 text-[11px] text-slate-400 py-3 px-1">
                <Loader2 size={11} className="animate-spin" style={{ color: "hsl(var(--accent))" }} />
                <span>Analysing selection…</span>
              </div>
            )}

            {error && (
              <div className="text-[11px] text-red-400 py-2 px-3 rounded-md bg-red-500/10 border border-red-500/20">
                {error}
              </div>
            )}

            {/* Prose — render the cleanText (without the actions block)
                as markdown so **bold** / bullets / headers render rather
                than showing literal markdown characters. */}
            {cleanText && (
              <div>
                <MarkdownMessage>{cleanText}</MarkdownMessage>
                {loading && (
                  <span
                    className="inline-block w-1 h-3 ml-0.5 animate-pulse"
                    style={{ background: "hsl(var(--accent))" }}
                  />
                )}
              </div>
            )}

            {/* Pills — same component as Global AI.  Local AI uses a
                local appliedIdx Set because the popover doesn't
                persist its messages. */}
            {!loading && actions.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-white/[0.06]">
                {actions.length >= 2 && (
                  <AIActionApplyAll
                    actions={actions}
                    appliedIdx={appliedIdx}
                    source="local_ai"
                    onActionApplied={(i) =>
                      setAppliedIdx((prev) => (prev.includes(i) ? prev : [...prev, i]))
                    }
                  />
                )}
                {actions.map((a, i) => (
                  <AIActionPill
                    key={i}
                    action={a}
                    applied={appliedIdx.includes(i)}
                    source="local_ai"
                    onApplied={() =>
                      setAppliedIdx((prev) => (prev.includes(i) ? prev : [...prev, i]))
                    }
                  />
                ))}
              </div>
            )}

            {/* Edge case: stream finished, no parseable actions AND no
                prose.  Show the raw text so the user isn't staring at
                an empty popover. */}
            {!loading && !cleanText && !actions.length && rawText && !error && (
              <pre className="text-[11px] text-slate-400 whitespace-pre-wrap font-mono leading-relaxed bg-black/20 rounded-md p-2 border border-white/5">
                {rawText}
              </pre>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
