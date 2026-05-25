"use client";
/**
 * GlobalAIPanel — right panel for full-session AI chat + Global Scan.
 * Rendered as a flex sibling of the main canvas so it pushes content when open.
 */
import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Scan, X, Sparkles, Loader2 } from "lucide-react";
import { useCanvasStore, ChatMessage } from "@/lib/store";
import { streamGlobalAI, streamGlobalScan } from "@/lib/api";
import { useSession } from "@/components/providers/AuthProvider";
import { parseAssistantMessage } from "@/lib/ai/actions";
import { AIActionPill, AIActionApplyAll } from "@/components/AIActionPill";

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
                <div className="text-center mt-12 space-y-3">
                  <div className="w-10 h-10 rounded-full bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mx-auto">
                    <Sparkles size={16} className="text-slate-600" />
                  </div>
                  <div>
                    <p className="text-[13px] font-medium text-slate-300">Ask about your design session</p>
                    <p className="text-[11px] text-slate-500 mt-1 leading-relaxed max-w-[220px] mx-auto">
                      Or click <span className="text-violet-300 font-medium">Global Scan</span> to get proactive insights across your work
                    </p>
                  </div>
                </div>
              )}
              {session.messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
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
        <p className="whitespace-pre-wrap">{message.content}</p>
        {isStreaming && <span className="inline-block w-1 h-3 bg-sky-400 animate-pulse ml-0.5" />}

        {/* Agentic pills row — only on assistant messages with at least
            one parsed action.  Apply-all hides itself when fully applied. */}
        {actions.length > 0 && (
          <div className="mt-3 -mx-0.5 flex flex-wrap items-center gap-1.5 border-t border-white/[0.06] pt-2.5">
            {actions.length >= 2 && (
              <AIActionApplyAll
                messageId={fullMessage.id}
                actions={actions}
                appliedIdx={appliedIdx}
              />
            )}
            {actions.map((a, i) => (
              <AIActionPill
                key={i}
                messageId={fullMessage.id}
                action={a}
                index={i}
                applied={appliedIdx.includes(i)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
