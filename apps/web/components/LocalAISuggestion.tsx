"use client";
import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, X, Loader2, ArrowRight, Check } from "lucide-react";
import { toast } from "sonner";
import { useCanvasStore, type ExecutableAction } from "@/lib/store";
import { streamLocalAI } from "@/lib/api";
import { useSession } from "@/components/providers/AuthProvider";

interface Suggestion {
  action: string;
  detail: string;
  type: "composition" | "property" | "explore" | "constraint";
  executable?: ExecutableAction;
}

const POPOVER_W = 360;
const POPOVER_MAX_H = 460;
const GAP = 12;

const TYPE_STYLE: Record<string, { bg: string; text: string; border: string }> = {
  composition: { bg: "bg-sky-500/15",     text: "text-sky-300",     border: "border-sky-500/30" },
  property:    { bg: "bg-violet-500/15",  text: "text-violet-300",  border: "border-violet-500/30" },
  explore:     { bg: "bg-emerald-500/15", text: "text-emerald-300", border: "border-emerald-500/30" },
  constraint:  { bg: "bg-amber-500/15",   text: "text-amber-300",   border: "border-amber-500/30" },
};

function parseSuggestions(raw: string): Suggestion[] {
  try {
    const match = raw.match(/\[[\s\S]*\]/);
    if (!match) return [];
    return JSON.parse(match[0]);
  } catch {
    return [];
  }
}

function describeAction(a?: ExecutableAction): string {
  if (!a) return "";
  switch (a.op) {
    case "set_element": return `${a.element} → ${a.value}%`;
    case "delta_element": return `${a.element} ${a.delta > 0 ? "+" : ""}${a.delta}%`;
    case "set_target": return `${a.name} → ${a.value}`;
    case "sweep": return `Sweep ${a.vary}: ${a.from}–${a.to}% × ${a.steps}`;
  }
}

export function LocalAISuggestion() {
  const { selectedElement, localAIPopoverOpen, selectElement, globalAIPanelOpen, applyAction } = useCanvasStore();
  const { session: authSession } = useSession();
  const authToken = authSession?.access_token ?? null;
  const [rawText, setRawText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [appliedIdx, setAppliedIdx] = useState<number | null>(null);
  const [applyingIdx, setApplyingIdx] = useState<number | null>(null);

  useEffect(() => {
    if (!selectedElement || !localAIPopoverOpen) return;
    setRawText(""); setError(null); setLoading(true); setAppliedIdx(null);

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

  // Smart positioning
  const position = useMemo(() => {
    if (typeof window === "undefined") return { left: 100, top: 100 };
    const anchor = selectedElement?.anchor;
    if (!anchor) {
      return {
        left: Math.max(20, window.innerWidth / 2 - POPOVER_W / 2),
        top: Math.max(80, window.innerHeight / 2 - POPOVER_MAX_H / 2),
      };
    }
    const rightBoundary = window.innerWidth - (globalAIPanelOpen ? 420 : 0) - 20;
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

  async function handleApply(idx: number, s: Suggestion) {
    if (!s.executable) {
      toast.error("This suggestion has no executable action");
      return;
    }
    setApplyingIdx(idx);
    try {
      const result = await applyAction(s.executable);
      if (result.ok) {
        setAppliedIdx(idx);
        toast.success(result.message);
        // Auto-close popover after a brief success indicator
        setTimeout(() => selectElement(null), 800);
      } else {
        toast.error(result.message);
      }
    } finally {
      setApplyingIdx(null);
    }
  }

  const suggestions = parseSuggestions(rawText);
  const showRaw = (loading && suggestions.length === 0) || (suggestions.length === 0 && rawText.length > 0);

  return (
    <AnimatePresence>
      {localAIPopoverOpen && selectedElement && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 4 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 4 }}
          transition={{ duration: 0.12 }}
          style={{
            position: "fixed",
            left: position.left,
            top: position.top,
            width: POPOVER_W,
            maxHeight: POPOVER_MAX_H,
            zIndex: 50,
          }}
          className="rounded-xl bg-[#15171d] border border-white/15 shadow-2xl shadow-black/60 overflow-hidden flex flex-col"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-white/10 shrink-0 bg-gradient-to-r from-sky-500/[0.08] to-transparent">
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded-md bg-sky-500/20 border border-sky-500/30 flex items-center justify-center">
                <Sparkles size={10} className="text-sky-400" />
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
            >
              <X size={13} />
            </button>
          </div>

          {/* Content */}
          <div className="px-3 py-3 space-y-2 overflow-y-auto flex-1">
            {loading && suggestions.length === 0 && !rawText && (
              <div className="flex items-center gap-2 text-[11px] text-slate-400 py-3 px-1">
                <Loader2 size={11} className="animate-spin text-sky-400" />
                <span>Analysing selection…</span>
              </div>
            )}

            {error && (
              <div className="text-[11px] text-red-400 py-2 px-3 rounded-md bg-red-500/10 border border-red-500/20">
                {error}
              </div>
            )}

            {showRaw && !error && (
              <pre className="text-[11px] text-slate-400 whitespace-pre-wrap font-mono leading-relaxed bg-black/20 rounded-md p-2 border border-white/5">
                {rawText}
              </pre>
            )}

            {suggestions.map((s, i) => {
              const style = TYPE_STYLE[s.type] ?? TYPE_STYLE.explore;
              const isApplying = applyingIdx === i;
              const isApplied = appliedIdx === i;
              const hasExecutable = !!s.executable;
              return (
                <div
                  key={i}
                  className="rounded-lg bg-white/[0.04] border border-white/[0.08] px-3 py-2.5 transition-all"
                >
                  <div className={`inline-block text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border ${style.bg} ${style.text} ${style.border} mb-1.5`}>
                    {s.type}
                  </div>
                  <div className="text-[12px] font-semibold text-slate-100 leading-snug">{s.action}</div>
                  <div className="text-[11px] text-slate-400 mt-1 leading-relaxed">{s.detail}</div>

                  {hasExecutable && (
                    <div className="mt-2.5 flex items-center justify-between gap-2 pt-2 border-t border-white/[0.06]">
                      <span className="text-[10px] font-mono text-slate-500 truncate">
                        {describeAction(s.executable)}
                      </span>
                      <button
                        onClick={() => handleApply(i, s)}
                        disabled={isApplying || isApplied}
                        className={`shrink-0 inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-md transition-all ${
                          isApplied
                            ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                            : isApplying
                              ? "bg-sky-500/20 text-sky-300 border border-sky-500/30"
                              : "bg-sky-500 hover:bg-sky-400 text-white border border-sky-400 shadow-sm shadow-sky-500/20"
                        }`}
                      >
                        {isApplied ? <><Check size={11} /> Applied</>
                          : isApplying ? <><Loader2 size={11} className="animate-spin" /> Applying</>
                          : <>Apply <ArrowRight size={11} /></>}
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
