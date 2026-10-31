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

// Colour means status in the cockpit, so the families are NOT ten hues: three tonal steps carry the one distinction that
// matters when choosing alloying elements — metal, metalloid / non-metal, or an element no alloy uses — and the family's
// name is in the hover card.
type Tone = { fill: string; text: string; border: string };
const METAL: Tone = { fill: "bg-fg/[0.08] hover:bg-fg/[0.16]", text: "text-fg", border: "border-fg/30" };
const SEMI: Tone = { fill: "bg-fg/[0.04] hover:bg-fg/[0.10]", text: "text-muted", border: "border-line" };
const INERT: Tone = { fill: "bg-fg/[0.02]", text: "text-subtle", border: "border-line" };
const CATEGORY_STYLE: Record<ElementCategory, Tone & { label: string }> = {
  "alkali":          { ...METAL, label: "Alkali"          },
  "alkaline":        { ...METAL, label: "Alkaline earth"  },
  "transition":      { ...METAL, label: "Transition"      },
  "post-transition": { ...METAL, label: "Post-transition" },
  "metalloid":       { ...SEMI,  label: "Metalloid"       },
  "nonmetal":        { ...SEMI,  label: "Non-metal"       },
  "halogen":         { ...INERT, label: "Halogen"         },
  "noble":           { ...INERT, label: "Noble gas"       },
  "lanthanide":      { ...METAL, label: "Lanthanide"      },
  "actinide":        { ...METAL, label: "Actinide"        },
};
const LEGEND: { tone: Tone; label: string }[] = [
  { tone: METAL, label: "Metal" },
  { tone: SEMI, label: "Metalloid · non-metal" },
  { tone: INERT, label: "Halogen · noble gas" },
];

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
            className="rounded-2xl bg-surface/95 border border-line shadow-2xl shadow-black/60 p-6 max-w-[860px] w-full"
          >
            {/* Header */}
            <div className="flex items-start justify-between mb-5">
              <div>
                <h2 className="text-[15px] font-semibold text-fg tracking-tight">Periodic Table</h2>
                <p className="text-[11px] text-subtle mt-0.5">
                  Click any element to add to the composition · already-selected elements glow
                </p>
              </div>
              <button
                onClick={onClose}
                aria-label="Close periodic table"
                title="Close"
                className="p-1.5 rounded-md text-subtle hover:text-fg hover:bg-fg/5 transition-all"
              >
                <X size={16} />
              </button>
            </div>

            {/* Hover detail card */}
            <div className="h-16 mb-3 flex items-center justify-center">
              {hovered ? (
                <div className="flex items-center gap-4 px-4 py-2 rounded-lg bg-fg/[0.03] border border-line">
                  <div className={`w-12 h-12 rounded-md border ${CATEGORY_STYLE[hovered.category].fill} ${CATEGORY_STYLE[hovered.category].border} flex flex-col items-center justify-center`}>
                    <span className={`text-[8px] ${CATEGORY_STYLE[hovered.category].text} opacity-70`}>{hovered.number}</span>
                    <span className={`text-base font-bold ${CATEGORY_STYLE[hovered.category].text} leading-none`}>{hovered.symbol}</span>
                  </div>
                  <div>
                    <div className="text-[13px] font-semibold text-fg">{hovered.name}</div>
                    <div className="text-[10px] text-subtle uppercase tracking-wider font-medium">
                      Z = {hovered.number} · {CATEGORY_STYLE[hovered.category].label}
                      {isElementDisabled(hovered.symbol) && <span className="ml-2 text-warn">· not alloyable</span>}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-[11px] text-subtle">Hover over an element to see details</div>
              )}
            </div>

            {/* Grid */}
            <div
              className="grid gap-[3px]"
              style={{ gridTemplateColumns: "repeat(18, minmax(0, 1fr))", gridTemplateRows: "repeat(7, minmax(0, 1fr)) 12px repeat(2, minmax(0, 1fr))" }}
            >
              {/* Placeholder for La/Ac series links */}
              <div style={{ gridColumn: 3, gridRow: 6 }} className="rounded-md bg-fg/10 border border-line text-[8px] flex items-center justify-center text-fg font-mono">57-71</div>
              <div style={{ gridColumn: 3, gridRow: 7 }} className="rounded-md bg-fg/10 border border-line text-[8px] flex items-center justify-center text-fg font-mono">89-103</div>

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
                      ${inComp ? "ring-2 ring-fg shadow-md shadow-black/40" : ""}
                    `}
                  >
                    <div className={`absolute top-[2px] right-[3px] text-[7px] ${cat.text} opacity-60 font-mono leading-none`}>
                      {el.number}
                    </div>
                    <div className={`text-[11px] font-bold ${cat.text} leading-none mt-[8px]`}>
                      {el.symbol}
                    </div>
                    {inComp && (
                      <div className="absolute bottom-[2px] left-1/2 -translate-x-1/2 text-[8px] font-mono text-fg leading-none">
                        {composition[el.symbol].toFixed(0)}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Legend */}
            <div className="mt-5 pt-4 border-t border-line">
              <div className="flex flex-wrap gap-2 text-[10px]">
                {LEGEND.map(({ tone, label }) => (
                  <div key={label} className="flex items-center gap-1.5">
                    <div className={`w-2.5 h-2.5 rounded border ${tone.fill} ${tone.border}`} />
                    <span className="text-muted">{label}</span>
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
