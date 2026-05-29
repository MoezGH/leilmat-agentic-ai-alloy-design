"use client";
/**
 * GlobalAIPanel — right panel for full-session AI chat + Global Scan.
 * Rendered as a flex sibling of the main canvas so it pushes content when open.
 */
import { useState, useRef, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Scan, X, Sparkles, Loader2, RefreshCw, Check } from "lucide-react";
import { useCanvasStore, ChatMessage, type AppliedAction } from "@/lib/store";
import { streamGlobalAI, streamGlobalScan } from "@/lib/api";
import { useSession } from "@/components/providers/AuthProvider";
import { parseAssistantMessage } from "@/lib/ai/actions";
import { AIActionPill, AIActionApplyAll } from "@/components/AIActionPill";
import { MarkdownMessage } from "@/components/MarkdownMessage";


// ─── Starter-prompt catalogue ─────────────────────────────────────────
// 12 example prompts spanning the main use cases.  The empty state of
// the Global AI panel renders a random sample of 4 as clickable pills;
// clicking one fills + sends the prompt in a single tap.  A shuffle
// button re-samples without sending.
//
// Categories represented:
//   * "design X for Y"   (alloy → application)
//   * "compare A vs B"   (cross-family head-to-head)
//   * "find Pareto"      (multi-objective optimisation)
//   * "process / temper" (heat-treatment + manufacturability)
//   * "explore system"   (composition-space sweep)
//
// Keep each prompt ≤ 80 chars so it fits on two lines at the 420 px
// panel width without truncation.
const STARTER_PROMPTS: readonly string[] = [
  "Design a high-strength aluminum alloy for aerospace",
  "Find a corrosion-resistant marine alloy",
  "Compare Ti-6Al-4V with Inconel 718 for high-temperature service",
  "Explore Al-Mg-Si compositions for automotive body panels",
  "Design a low-density alloy with yield strength above 300 MPa",
  "What heat treatment maximises 6061's yield strength?",
  "Find Pareto-optimal compositions in the Al-Cu-Mg system",
  "Suggest an alloy for laser powder-bed fusion (LPBF)",
  "Design a copper alloy with high thermal conductivity + strength",
  "Optimise a Ni-based superalloy for turbine blades at 900 °C",
  "Find a magnesium alloy with good castability and corrosion resistance",
  "Compare Al-Si vs Al-Mg-Si for cast structural components",
];

const STARTER_SAMPLE_SIZE = 4;

/** Deterministic-on-first-render shuffle: pick N unique items. */
function pickStarters(n: number): string[] {
  const pool = [...STARTER_PROMPTS];
  const out: string[] = [];
  for (let i = 0; i < n && pool.length; i++) {
    const idx = Math.floor(Math.random() * pool.length);
    out.push(pool.splice(idx, 1)[0]);
  }
  return out;
}

export function GlobalAIPanel() {
  const { session, globalAIPanelOpen, setGlobalAIPanelOpen, addMessage } = useCanvasStore();
  // Note: `session` above is the LeilMat *design session* (Zustand store).
  // Supabase auth session is a separate concept — pulled in here so we
  // can attach its access_token to the chat-streaming requests, which
  // hit /api/chat/* (gated by the backend's ENFORCED_PREFIXES).
  const { session: authSession } = useSession();
  const authToken = authSession?.access_token ?? null;

  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamBuffer, setStreamBuffer] = useState("");
  // Starter-prompt sample — re-randomised when the user hits ↻ or when
  // the panel is closed and reopened on a fresh empty session.  We use
  // a counter (not raw Math.random in render) so the shuffle is
  // deterministic per "tick" and avoids the useEffect-double-render
  // SSR-hydration headache.
  const [starterSeed, setStarterSeed] = useState(0);
  const starters = useMemo(
    () => pickStarters(STARTER_SAMPLE_SIZE),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [starterSeed],
  );
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session.messages, streamBuffer]);

  async function sendMessage(text: string) {
    if (!text.trim() || streaming) return;
    setInput("");
    addMessage({ role: "user", content: text, contextType: "global" });
    setStreaming(true);
    setStreamBuffer("");

    try {
      let full = "";
      for await (const chunk of streamGlobalAI(session, text, authToken)) {
        full += chunk;
        setStreamBuffer(full);
      }
      // Parse the trailing ```actions``` block out of the raw stream so
      // the persisted message stores cleanText (for display) and the
      // structured actions (for the pill row).
      const { cleanText, actions } = parseAssistantMessage(full);
      addMessage({
        role:        "assistant",
        content:     cleanText,
        contextType: "global",
        ...(actions.length > 0 ? { actions } : {}),
      });
    } finally {
      setStreamBuffer("");
      setStreaming(false);
    }
  }

  async function runGlobalScan() {
    if (streaming) return;
    setStreaming(true);
    setStreamBuffer("");
    try {
      let full = "";
      for await (const chunk of streamGlobalScan(session, authToken)) {
        full += chunk;
        setStreamBuffer(full);
      }
      const { cleanText, actions } = parseAssistantMessage(full);
      addMessage({
        role:        "assistant",
        content:     cleanText,
        contextType: "global",
        ...(actions.length > 0 ? { actions } : {}),
      });
    } finally {
      setStreamBuffer("");
      setStreaming(false);
    }
  }

  return (
    <AnimatePresence initial={false}>
      {globalAIPanelOpen && (
        <motion.aside
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: 420, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ type: "spring", stiffness: 280, damping: 32 }}
          className="shrink-0 overflow-hidden border-l border-white/[0.06] bg-[#0c0e13]/80 backdrop-blur-xl"
        >
          <div className="flex flex-col h-full w-[420px]">
            {/* Header */}
            <div className="flex items-center justify-between px-5 h-14 border-b border-white/[0.06] shrink-0">
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-sky-400" />
                <span className="text-[14px] font-semibold text-slate-100">Global AI</span>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={runGlobalScan}
                  disabled={streaming}
                  className="flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1.5 rounded-md bg-violet-500/15 hover:bg-violet-500/25 border border-violet-500/30 text-violet-300 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {streaming ? <Loader2 size={11} className="animate-spin" /> : <Scan size={11} />}
                  Global Scan
                </button>
                <button
                  onClick={() => setGlobalAIPanelOpen(false)}
                  className="p-1.5 rounded-md text-slate-500 hover:text-white hover:bg-white/5 transition-all"
                >
                  <X size={14} />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4">
              {session.messages.length === 0 && !streaming && (
                <div className="mt-6 space-y-5">
                  {/* Heading: bigger and more inviting than the old icon-only block */}
                  <div className="text-center space-y-2">
                    <div
                      className="w-11 h-11 rounded-full mx-auto flex items-center justify-center"
                      style={{
                        background: "hsl(38 96% 60% / 0.12)",
                        border:     "1px solid hsl(38 96% 60% / 0.3)",
                      }}
                    >
                      <Sparkles size={18} style={{ color: "hsl(38 96% 60%)" }} />
                    </div>
                    <p className="text-[14px] font-semibold text-slate-200">
                      Start a design session
                    </p>
                    <p className="text-[11.5px] leading-relaxed text-slate-500 max-w-[280px] mx-auto">
                      Pick a starter below to kick things off, hit{" "}
                      <span className="text-violet-300 font-medium">Global Scan</span> for proactive insights,
                      or type your own question in the box below.
                    </p>
                  </div>

                  {/* Starter-prompt pills */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between px-1">
                      <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-600">
                        Try a starter
                      </span>
                      <button
                        type="button"
                        onClick={() => setStarterSeed((s) => s + 1)}
                        title="Shuffle suggestions"
                        className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] text-slate-500 hover:text-slate-300 hover:bg-white/[0.04] transition-all"
                      >
                        <RefreshCw size={10} />
                        Shuffle
                      </button>
                    </div>
                    {starters.map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        onClick={() => { void sendMessage(prompt); }}
                        disabled={streaming}
                        className="group w-full text-left rounded-lg px-3 py-2.5 text-[12.5px] leading-snug transition-all disabled:opacity-50 hover:bg-[hsl(38_96%_60%/0.06)]"
                        style={{
                          background:  "hsl(38 96% 60% / 0.03)",
                          border:      "1px solid hsl(38 96% 60% / 0.18)",
                          color:       "rgb(203 213 225)",
                        }}
                      >
                        <span className="flex items-start gap-2">
                          <Sparkles
                            size={11}
                            className="shrink-0 mt-0.5 opacity-60 group-hover:opacity-100 transition-opacity"
                            style={{ color: "hsl(38 96% 60%)" }}
                          />
                          <span>{prompt}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {/* Unified timeline: chat messages + applied-action event
                  rows, interleaved by timestamp.  Reads as a real session
                  narrative — you asked X, AI suggested Y, you applied Z. */}
              {buildTimeline(session.messages, session.actionLog ?? []).map((item) =>
                item.kind === "message"
                  ? <MessageBubble key={`m-${item.msg.id}`} message={item.msg} />
                  : <ActionEventRow key={`a-${item.action.id}`} action={item.action} />
              )}
              {streaming && streamBuffer && (
                <MessageBubble
                  message={{ id: "streaming", role: "assistant", content: streamBuffer, contextType: "global", createdAt: "" }}
                  isStreaming
                />
              )}
              {streaming && !streamBuffer && (
                <div className="flex items-center gap-2 text-[11px] text-slate-500">
                  <Loader2 size={11} className="animate-spin" />
                  <span>Thinking…</span>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-white/[0.06] shrink-0">
              <form
                onSubmit={(e) => { e.preventDefault(); sendMessage(input); }}
                className="flex gap-2"
              >
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about your design session…"
                  className="flex-1 bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-[13px] text-slate-200 placeholder:text-slate-600 outline-none focus:border-sky-500/40 focus:bg-white/[0.05] transition-all"
                  disabled={streaming}
                />
                <button
                  type="submit"
                  disabled={!input.trim() || streaming}
                  className="px-3 py-2 bg-sky-500 hover:bg-sky-400 rounded-lg disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-white shadow-lg shadow-sky-500/20"
                >
                  <Send size={13} />
                </button>
              </form>
            </div>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

function MessageBubble({ message, isStreaming }: { message: ChatMessage | { id: string; role: string; content: string; contextType: string; createdAt: string }; isStreaming?: boolean }) {
  const isUser = message.role === "user";
  const markActionApplied = useCanvasStore((s) => s.markActionApplied);

  // Only persisted ChatMessage rows carry agentic actions; the streaming
  // shim object never does.  Narrow with a type guard before reading.
  const fullMessage = message as ChatMessage;
  const actions     = !isUser && !isStreaming ? fullMessage.actions ?? [] : [];
  const appliedIdx  = fullMessage.appliedActionIdx ?? [];

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[90%] rounded-xl px-3.5 py-2.5 text-[13px] leading-relaxed ${
          isUser
            ? "bg-sky-500/15 text-sky-100 border border-sky-500/20"
            : "bg-white/[0.04] border border-white/[0.06] text-slate-200"
        }`}
      >
        {/* User messages are their own plain typed text — render as-is.
            Assistant messages are markdown (the LLM emits **bold**,
            ### headers, - bullets, tables) — render through the themed
            markdown component so they're not literal asterisks. */}
        {isUser
          ? <p className="whitespace-pre-wrap">{message.content}</p>
          : <MarkdownMessage>{message.content}</MarkdownMessage>}
        {isStreaming && <span className="inline-block w-1 h-3 bg-sky-400 animate-pulse ml-0.5" />}

        {/* Agentic pills row — only on assistant messages with at least
            one parsed action.  Apply-all hides itself when fully applied. */}
        {actions.length > 0 && (
          <div className="mt-3 -mx-0.5 flex flex-wrap items-center gap-1.5 border-t border-white/[0.06] pt-2.5">
            {actions.length >= 2 && (
              <AIActionApplyAll
                actions={actions}
                appliedIdx={appliedIdx}
                onActionApplied={(i) => markActionApplied(fullMessage.id, i)}
              />
            )}
            {actions.map((a, i) => (
              <AIActionPill
                key={i}
                action={a}
                applied={appliedIdx.includes(i)}
                onApplied={() => markActionApplied(fullMessage.id, i)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────
// Unified timeline — interleave chat messages + applied-action events
// by timestamp.  Messages without a parseable createdAt sort to the end
// (they're the freshest, mid-session); actions always carry an ISO ts.
// ─────────────────────────────────────────────────────────────────────

type TimelineItem =
  | { kind: "message"; ts: number; msg: ChatMessage }
  | { kind: "action";  ts: number; action: AppliedAction };

function buildTimeline(
  messages: ChatMessage[],
  actionLog: AppliedAction[],
): TimelineItem[] {
  const parse = (iso: string | undefined): number => {
    if (!iso) return Number.MAX_SAFE_INTEGER;   // undated → newest
    const t = Date.parse(iso);
    return Number.isNaN(t) ? Number.MAX_SAFE_INTEGER : t;
  };
  const items: TimelineItem[] = [
    ...messages.map((m): TimelineItem => ({ kind: "message", ts: parse(m.createdAt), msg: m })),
    ...actionLog.map((a): TimelineItem => ({ kind: "action", ts: parse(a.createdAt), action: a })),
  ];
  // Stable sort by timestamp; ties keep insertion order (messages before
  // their resulting actions, since the message is logged first).
  return items
    .map((item, i) => ({ item, i }))
    .sort((a, b) => (a.item.ts - b.item.ts) || (a.i - b.i))
    .map(({ item }) => item);
}


// A thin event row marking an applied design action — visually distinct
// from chat bubbles (no avatar, no background card, a small check +
// source tag) so it reads as "something happened" not "someone said
// something."
const SOURCE_LABEL: Record<AppliedAction["source"], string> = {
  global_ai:      "Global AI",
  local_ai:       "Local AI",
  interpret_card: "Insight",
};

function ActionEventRow({ action }: { action: AppliedAction }) {
  return (
    <div className="flex items-center gap-2 px-1 py-0.5 text-[11px]">
      <span
        className="shrink-0 grid place-items-center w-4 h-4 rounded-full"
        style={{
          background: "hsl(38 96% 60% / 0.15)",
          border:     "1px solid hsl(38 96% 60% / 0.35)",
        }}
      >
        <Check size={9} style={{ color: "hsl(38 96% 60%)" }} />
      </span>
      <span className="text-slate-400">
        Applied <span className="text-slate-200">{action.label}</span>
      </span>
      <span className="ml-auto shrink-0 text-[9px] font-mono uppercase tracking-wider text-slate-600">
        {SOURCE_LABEL[action.source]}
      </span>
    </div>
  );
}
