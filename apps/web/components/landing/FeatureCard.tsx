"use client";

/**
 * FeatureCard — numbered feature card matching the leil.xyz portfolio
 * card spirit (numbered top-left, category label top-right, big title,
 * sub-URL, description, "Learn more" link, subtle SVG ornament in the
 * lower-right corner).
 *
 * Differs from leil.xyz on two intentional axes:
 *   * The ornament SVG is per-card (each feature picks its own glyph)
 *     instead of one shared constellation.  Easier to make each card
 *     feel material-specific.
 *   * Hover glow is in the brand accent (warm gold) — already inherited
 *     from the parent's ``--accent`` CSS var.
 */
import { motion } from "framer-motion";
import { type ReactNode } from "react";

export interface FeatureCardProps {
  index: number;                // 1-based number that renders as "01", "02" …
  category: string;             // top-right small caps label
  title: string;
  href: string;                 // anchor link or in-app deeplink
  description: string;
  ornament: ReactNode;          // SVG element (positioned absolute bottom-right)
}

export function FeatureCard({
  index,
  category,
  title,
  href,
  description,
  ornament,
}: FeatureCardProps) {
  const label = String(index).padStart(2, "0");

  return (
    <motion.a
      href={href}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut", delay: index * 0.06 }}
      viewport={{ once: true, margin: "-80px" }}
      whileHover={{ y: -2 }}
      className="group relative overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.015] p-6 transition-colors hover:border-[hsl(var(--accent)/0.5)] hover:bg-[hsl(var(--accent)/0.04)]"
      style={{
        // Soft gold glow on hover; sits ABOVE the lattice backdrop but
        // BELOW the inner content via the pseudo-pattern below.
        boxShadow: "0 0 0 transparent",
      }}
    >
      {/* Glow on hover — separate layer so it can fade independently of border. */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          boxShadow: "0 0 32px -8px hsl(var(--accent) / 0.35), inset 0 0 32px -16px hsl(var(--accent) / 0.18)",
        }}
      />

      {/* Top row: number + category */}
      <div className="flex items-baseline justify-between mb-6">
        <span className="font-mono text-[11px] tracking-widest text-slate-500">
          {label}
        </span>
        <span
          className="font-mono text-[10px] tracking-[0.18em] uppercase text-[hsl(var(--accent)/0.8)]"
        >
          {category}
        </span>
      </div>

      {/* Title + description */}
      <div className="relative z-10 space-y-2 max-w-[26ch]">
        <h3 className="text-2xl font-semibold tracking-tight text-white">
          {title}
        </h3>
        <p className="text-sm leading-relaxed text-slate-400">
          {description}
        </p>
      </div>

      {/* "Open →" link */}
      <div className="relative z-10 mt-6 inline-flex items-center gap-1.5 text-[12px] font-medium text-[hsl(var(--accent))] opacity-80 transition-opacity group-hover:opacity-100">
        Open
        <span aria-hidden className="transition-transform group-hover:translate-x-0.5">
          →
        </span>
      </div>

      {/* Ornament — bottom-right, very low opacity so it never competes */}
      <div
        aria-hidden
        className="pointer-events-none absolute right-3 bottom-3 h-24 w-24 opacity-[0.08] transition-opacity duration-300 group-hover:opacity-[0.18]"
        style={{ color: "hsl(var(--accent))" }}
      >
        {ornament}
      </div>
    </motion.a>
  );
}


// ──────────────────────────────────────────────────────────────────────
// Per-card SVG ornaments — small, monochrome, materials-themed.
// Sized 100×100 in viewBox so they scale cleanly into the 96×96 box.
// ──────────────────────────────────────────────────────────────────────

/** Atomic lattice with a highlighted "designed" atom in the centre. */
export function LatticeOrnament() {
  const dots: Array<[number, number]> = [];
  for (let i = 0; i < 4; i++) {
    for (let j = 0; j < 4; j++) {
      dots.push([20 + i * 20, 20 + j * 20]);
    }
  }
  return (
    <svg viewBox="0 0 100 100" fill="none" stroke="currentColor" strokeWidth="0.6">
      {/* Lines between near neighbours (within ~22 units = grid step + diagonal). */}
      {dots.map(([x, y], i) =>
        dots.map(([x2, y2], j) => {
          if (i >= j) return null;
          const d = Math.hypot(x - x2, y - y2);
          if (d > 22) return null;
          return <line key={`${i}-${j}`} x1={x} y1={y} x2={x2} y2={y2} opacity={0.5} />;
        }),
      )}
      {/* Dots */}
      {dots.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={1.6} fill="currentColor" stroke="none" />
      ))}
      {/* Highlighted central designed atom */}
      <circle cx={50} cy={50} r={3.4} fill="currentColor" />
      <circle cx={50} cy={50} r={6.5} stroke="currentColor" strokeWidth="0.7" opacity={0.5} />
    </svg>
  );
}

/** Pareto front sweep — three lines converging to an optimum. */
export function ParetoOrnament() {
  return (
    <svg viewBox="0 0 100 100" fill="none" stroke="currentColor" strokeWidth="0.8">
      <path d="M 10 80 Q 30 60, 50 50 T 90 22" />
      <path d="M 10 88 Q 32 72, 54 60 T 90 32" opacity={0.55} />
      <path d="M 10 95 Q 34 84, 58 70 T 90 42" opacity={0.35} />
      {/* Pareto-optimal dot */}
      <circle cx={50} cy={50} r={2.6} fill="currentColor" stroke="none" />
      {/* Target marker */}
      <circle cx={88} cy={20} r={1.6} fill="currentColor" stroke="none" />
      <line x1={50} y1={50} x2={88} y2={20} strokeDasharray="2 3" opacity={0.5} />
    </svg>
  );
}

/** Phase diagram triangle (ternary simplex). */
export function PhaseDiagramOrnament() {
  return (
    <svg viewBox="0 0 100 100" fill="none" stroke="currentColor" strokeWidth="0.7">
      {/* Outer triangle */}
      <polygon points="50,12 88,82 12,82" />
      {/* Interior gridlines */}
      {[0.25, 0.5, 0.75].map((t, i) => (
        <g key={i} opacity={0.45}>
          <line x1={50 + (88 - 50) * t} y1={12 + (82 - 12) * t} x2={50 + (12 - 50) * t} y2={12 + (82 - 12) * t} />
          <line x1={88 - (88 - 12) * t} y1={82} x2={50 + (88 - 50) * (1 - t)} y2={12 + (82 - 12) * (1 - t)} />
          <line x1={12 + (88 - 12) * t} y1={82} x2={50 + (12 - 50) * (1 - t)} y2={12 + (82 - 12) * (1 - t)} />
        </g>
      ))}
      {/* A representative phase point */}
      <circle cx={55} cy={58} r={2.4} fill="currentColor" stroke="none" />
    </svg>
  );
}

/** AI copilot glyph — a small "thinking" graph with a highlighted node. */
export function CopilotOrnament() {
  return (
    <svg viewBox="0 0 100 100" fill="none" stroke="currentColor" strokeWidth="0.7">
      {/* Hub-and-spoke "agent" graph */}
      <circle cx={50} cy={50} r={4} fill="currentColor" stroke="none" />
      {[
        [22, 22], [78, 22], [88, 50], [78, 78], [22, 78], [12, 50],
      ].map(([x, y], i) => (
        <g key={i}>
          <line x1={50} y1={50} x2={x} y2={y} opacity={0.4} />
          <circle cx={x} cy={y} r={2} fill="currentColor" stroke="none" />
        </g>
      ))}
      {/* Pulse ring */}
      <circle cx={50} cy={50} r={10} opacity={0.4} />
      <circle cx={50} cy={50} r={16} opacity={0.18} />
    </svg>
  );
}
