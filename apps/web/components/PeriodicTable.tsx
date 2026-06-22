"use client";
/**
 * PeriodicTable — interactive grid for picking alloying elements.
 *
 *  Behaviour:
 *  - Click an enabled element → adds it to the composition at 5% (default),
 *    renormalising existing entries so the total stays at 100%
 *  - Click an element already in the composition → removes it (and renormalises others)
 *  - Disabled elements (noble gases, halogens, synthetic) are rendered grey + not clickable
 *  - Hover any cell → tooltip with full name, atomic number, category
 */
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { ELEMENTS, isElementDisabled, type ElementCategory, type PeriodicElement } from "@/data/elements";

const CATEGORY_STYLE: Record<ElementCategory, { fill: string; text: string; border: string; label: string }> = {
  "alkali":          { fill: "bg-rose-500/15 hover:bg-rose-500/25",         text: "text-rose-300",    border: "border-rose-500/40",    label: "Alkali"          },
  "alkaline":        { fill: "bg-orange-500/15 hover:bg-orange-500/25",     text: "text-orange-300",  border: "border-orange-500/40",  label: "Alkaline earth"  },
  "transition":      { fill: "bg-amber-500/15 hover:bg-amber-500/25",       text: "text-amber-300",   border: "border-amber-500/40",   label: "Transition"      },
  "post-transition": { fill: "bg-emerald-500/15 hover:bg-emerald-500/25",   text: "text-emerald-300", border: "border-emerald-500/40", label: "Post-transition" },
  "metalloid":       { fill: "bg-teal-500/15 hover:bg-teal-500/25",         text: "text-teal-300",    border: "border-teal-500/40",    label: "Metalloid"       },
  "nonmetal":        { fill: "bg-slate-500/15 hover:bg-slate-500/25",       text: "text-slate-300",   border: "border-slate-500/40",   label: "Non-metal"       },
  "halogen":         { fill: "bg-violet-500/10",                            text: "text-violet-400",  border: "border-violet-500/30",  label: "Halogen"         },
  "noble":           { fill: "bg-zinc-500/10",                              text: "text-zinc-500",    border: "border-zinc-500/20",    label: "Noble gas"       },
  "lanthanide":      { fill: "bg-pink-500/15 hover:bg-pink-500/25",         text: "text-pink-300",    border: "border-pink-500/40",    label: "Lanthanide"      },
  "actinide":        { fill: "bg-fuchsia-500/15 hover:bg-fuchsia-500/25",   text: "text-fuchsia-300", border: "border-fuchsia-500/40", label: "Actinide"        },
};

interface PeriodicTableProps {
  open: boolean;
  onClose: () => void;
  composition: Record<string, number>;
  onToggleElement: (symbol: string) => void;
}

export function PeriodicTable({ open, onClose, composition, onToggleElement }: PeriodicTableProps) {
  const [hovered, setHovered] = useState<PeriodicElement | null>(null);

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
            className="rounded-2xl bg-[#0f1117]/95 border border-white/[0.08] shadow-2xl shadow-black/60 p-6 max-w-[860px] w-full"
          >
            {/* Header */}
            <div className="flex items-start justify-between mb-5">
              <div>
                <h2 className="text-[15px] font-semibold text-slate-100 tracking-tight">Periodic Table</h2>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Click any element to add to the composition · already-selected elements glow
                </p>
              </div>
              <button
                onClick={onClose}
                aria-label="Close periodic table"
                title="Close"
                className="p-1.5 rounded-md text-slate-500 hover:text-white hover:bg-white/5 transition-all"
              >
                <X size={16} />
              </button>
            </div>

            {/* Hover detail card */}
            <div className="h-16 mb-3 flex items-center justify-center">
              {hovered ? (
                <div className="flex items-center gap-4 px-4 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <div className={`w-12 h-12 rounded-md border ${CATEGORY_STYLE[hovered.category].fill} ${CATEGORY_STYLE[hovered.category].border} flex flex-col items-center justify-center`}>
                    <span className={`text-[8px] ${CATEGORY_STYLE[hovered.category].text} opacity-70`}>{hovered.number}</span>
                    <span className={`text-base font-bold ${CATEGORY_STYLE[hovered.category].text} leading-none`}>{hovered.symbol}</span>
                  </div>
                  <div>
                    <div className="text-[13px] font-semibold text-slate-100">{hovered.name}</div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">
                      Z = {hovered.number} · {CATEGORY_STYLE[hovered.category].label}
                      {isElementDisabled(hovered.symbol) && <span className="ml-2 text-amber-400">· not alloyable</span>}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-[11px] text-slate-600">Hover over an element to see details</div>
              )}
            </div>

            {/* Grid */}
            <div
              className="grid gap-[3px]"
              style={{ gridTemplateColumns: "repeat(18, minmax(0, 1fr))", gridTemplateRows: "repeat(7, minmax(0, 1fr)) 12px repeat(2, minmax(0, 1fr))" }}
            >
              {/* Placeholder for La/Ac series links */}
              <div style={{ gridColumn: 3, gridRow: 6 }} className="rounded-md bg-pink-500/5 border border-pink-500/20 text-[8px] flex items-center justify-center text-pink-400/80 font-mono">57-71</div>
              <div style={{ gridColumn: 3, gridRow: 7 }} className="rounded-md bg-fuchsia-500/5 border border-fuchsia-500/20 text-[8px] flex items-center justify-center text-fuchsia-400/80 font-mono">89-103</div>

              {ELEMENTS.map((el) => {
                const inComp = composition[el.symbol] != null;
                const disabled = isElementDisabled(el.symbol);
                const cat = CATEGORY_STYLE[el.category];
                const row = el.period === 8 ? 9 : el.period === 9 ? 10 : el.period;

                return (
                  <button
                    key={el.symbol}
                    aria-label={`${el.name} (${el.symbol})${disabled ? ", not alloyable" : inComp ? ", in composition — click to remove" : " — click to add to composition"}`}
                    aria-pressed={inComp}
                    onMouseEnter={() => setHovered(el)}
                    onMouseLeave={() => setHovered(null)}
                    onClick={() => !disabled && onToggleElement(el.symbol)}
                    disabled={disabled}
                    style={{ gridColumn: el.group, gridRow: row }}
                    className={`
                      relative aspect-square min-w-0 rounded-md border transition-all
                      ${cat.fill} ${cat.border}
                      ${disabled ? "cursor-not-allowed opacity-40" : "cursor-pointer hover:scale-105 hover:z-10"}
                      ${inComp ? "ring-2 ring-sky-400 shadow-md shadow-sky-500/30 brightness-125" : ""}
                    `}
                  >
                    <div className={`absolute top-[2px] right-[3px] text-[7px] ${cat.text} opacity-60 font-mono leading-none`}>
                      {el.number}
                    </div>
                    <div className={`text-[11px] font-bold ${cat.text} leading-none mt-[8px]`}>
                      {el.symbol}
                    </div>
                    {inComp && (
                      <div className="absolute bottom-[2px] left-1/2 -translate-x-1/2 text-[8px] font-mono text-sky-300 leading-none">
                        {composition[el.symbol].toFixed(0)}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Legend */}
            <div className="mt-5 pt-4 border-t border-white/[0.06]">
              <div className="flex flex-wrap gap-2 text-[10px]">
                {(Object.entries(CATEGORY_STYLE) as [ElementCategory, typeof CATEGORY_STYLE[ElementCategory]][]).map(([cat, st]) => (
                  <div key={cat} className="flex items-center gap-1.5">
                    <div className={`w-2.5 h-2.5 rounded border ${st.fill} ${st.border}`} />
                    <span className="text-slate-400">{st.label}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
