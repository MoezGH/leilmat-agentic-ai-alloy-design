"use client";
/**
 * GlossaryModal — in-canvas quick reference for the materials-science
 * jargon the canvas surfaces (UI/UX audit Tier B2).
 *
 * A searchable term list grouped by category, plus a legend explaining
 * the calibration labels that gate every result (the honesty contract),
 * and a link out to the fuller /docs explainer.  Matches the
 * PeriodicTable modal pattern (framer-motion overlay, backdrop-dismiss).
 */
import { useMemo, useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Search, BookOpen } from "lucide-react";

import {
  GLOSSARY,
  CALIBRATION_LABELS,
  type GlossaryCategory,
  type GlossaryTerm,
} from "@/lib/glossary";
import { TONE_SOFT } from "@/lib/theme";

const CATEGORY_ORDER: GlossaryCategory[] = [
  "Simulation methods",
  "Strengthening physics",
  "Thermodynamics & phases",
  "ML & data",
  "Statistics & honesty",
];

export function GlossaryModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState("");

  // Close on Escape, and reset the search when the modal is dismissed.
  useEffect(() => {
    if (!open) { setQuery(""); return; }
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return GLOSSARY;
    return GLOSSARY.filter((t) =>
      (t.term + " " + (t.aka ?? "") + " " + t.def).toLowerCase().includes(q),
    );
  }, [query]);

  const grouped = useMemo(() => {
    const m = new Map<GlossaryCategory, GlossaryTerm[]>();
    for (const t of filtered) {
      if (!m.has(t.category)) m.set(t.category, []);
      m.get(t.category)!.push(t);
    }
    return m;
  }, [filtered]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/60 backdrop-blur-md"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.96, opacity: 0, y: 8 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.96, opacity: 0, y: 8 }}
            transition={{ duration: 0.15 }}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Glossary"
            className="flex flex-col rounded-2xl bg-[#0f1117]/95 border border-white/[0.08] shadow-2xl shadow-black/60 max-w-[720px] w-full max-h-[82vh]"
          >
            {/* Header */}
            <div className="flex items-start justify-between p-6 pb-4 border-b border-white/[0.06]">
              <div>
                <h2 className="text-[15px] font-semibold text-slate-100 tracking-tight">Glossary</h2>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Quick definitions for the terms the canvas uses · search below
                </p>
              </div>
              <button
                onClick={onClose}
                aria-label="Close glossary"
                title="Close (Esc)"
                className="p-1.5 rounded-md text-slate-500 hover:text-white hover:bg-white/5 transition-all"
              >
                <X size={16} />
              </button>
            </div>

            {/* Search */}
            <div className="px-6 pt-4">
              <div className="relative">
                <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600" />
                <input
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search terms — e.g. CPFEM, Scheil, Orowan, conformal…"
                  className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg pl-9 pr-3 py-2 text-[12px] text-slate-200 placeholder:text-slate-600 outline-none focus:border-sky-500/40 focus:bg-white/[0.05] transition-all"
                />
              </div>
            </div>

            {/* Scrollable body */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
              {CATEGORY_ORDER.map((cat) => {
                const terms = grouped.get(cat);
                if (!terms || terms.length === 0) return null;
                return (
                  <section key={cat}>
                    <h3 className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500 mb-2">
                      {cat}
                    </h3>
                    <div className="space-y-1.5">
                      {terms.map((t) => (
                        <div
                          key={t.term}
                          className="rounded-lg border border-white/[0.05] bg-white/[0.015] px-3.5 py-2.5"
                        >
                          <div className="text-[12.5px] font-semibold text-sky-200">{t.term}</div>
                          <div className="text-[11.5px] text-slate-400 leading-snug mt-0.5">{t.def}</div>
                        </div>
                      ))}
                    </div>
                  </section>
                );
              })}

              {filtered.length === 0 && (
                <div className="py-10 text-center">
                  <p className="text-[12px] text-slate-500">No terms match &ldquo;{query}&rdquo;.</p>
                  <p className="text-[11px] text-slate-600 mt-1">Try the full documentation below.</p>
                </div>
              )}

              {/* Calibration-label legend — always shown (it's the honesty
                  contract that gates trust in every result). */}
              {!query && (
                <section>
                  <h3 className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500 mb-2">
                    Calibration labels — how far to trust a number
                  </h3>
                  <div className="space-y-1.5">
                    {CALIBRATION_LABELS.map((c) => {
                      return (
                        <div
                          key={c.label}
                          className="flex items-start gap-2.5 rounded-lg border border-white/[0.05] bg-white/[0.015] px-3.5 py-2.5"
                        >
                          <span className={`shrink-0 mt-0.5 text-[9px] font-mono font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded border ${TONE_SOFT[c.tone]}`}>
                            {c.label}
                          </span>
                          <span className="text-[11.5px] text-slate-400 leading-snug">{c.meaning}</span>
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between gap-3 px-6 py-4 border-t border-white/[0.06]">
              <p className="text-[10.5px] text-slate-600 leading-snug">
                Screening tools — validate predictions against experiment before production.
              </p>
              <a
                href="/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white/[0.04] border border-white/[0.06] hover:bg-white/[0.07] hover:border-white/[0.12] text-[11px] font-medium text-slate-300 hover:text-white transition-colors"
              >
                <BookOpen size={12} />
                Full documentation
                <span aria-hidden>→</span>
              </a>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
