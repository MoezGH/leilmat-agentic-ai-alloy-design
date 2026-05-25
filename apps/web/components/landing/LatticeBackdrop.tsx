"use client";

/**
 * LatticeBackdrop — animated crystal-lattice / constellation backdrop
 * for the landing page.
 *
 * Spirit-cousin to leil.xyz's constellation cards, but materials-themed:
 * dots are positioned on a perturbed FCC-ish 2D lattice and connected
 * to their nearest neighbours with hair-thin lines.  A subset of nodes
 * pulse on staggered delays so the whole thing feels alive without
 * pulling attention from the hero copy.
 *
 * Implementation notes
 * ────────────────────
 *   * Pure CSS @keyframes for the pulse — no per-frame React work.
 *   * Lattice is computed once on first mount with a deterministic seed
 *     so server- and client-rendered HTML match (no SSR hydration
 *     mismatch warning).  The "perturbation" uses a tiny seeded LCG.
 *   * Radial mask fades edges so the lattice never crowds the cards or
 *     sign-in panel.
 *   * pointer-events: none — never intercepts clicks on the content
 *     above it.
 *   * Colour is driven by the parent's ``--accent`` CSS variable so the
 *     same backdrop can be reused if other Leil sub-apps adopt the
 *     pattern (each just sets a different accent).
 */
import { useMemo } from "react";

interface Node {
  cx: number;
  cy: number;
  r: number;
  pulse: boolean;
  delay: number;
}

interface Edge {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  opacity: number;
}

// Seeded RNG so SSR + client agree on positions / pulses / delays.
function seededRng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0xffffffff;
  };
}

function buildLattice(): { nodes: Node[]; edges: Edge[] } {
  const rand = seededRng(20260525);
  const W = 1600;  // viewBox width
  const H = 1000;  // viewBox height
  const STEP = 90; // base lattice spacing
  const JITTER = 22;
  const COLS = Math.ceil(W / STEP) + 1;
  const ROWS = Math.ceil(H / STEP) + 1;

  const nodes: Node[] = [];
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      // FCC-ish: shift every other row by half a step
      const x = c * STEP + (r % 2 === 0 ? 0 : STEP / 2) + (rand() - 0.5) * JITTER;
      const y = r * STEP + (rand() - 0.5) * JITTER;
      nodes.push({
        cx: x,
        cy: y,
        r: 1.2 + rand() * 0.8,
        pulse: rand() < 0.18,           // ~18 % of dots animate
        delay: rand() * 6,
      });
    }
  }

  // Nearest-neighbour edges (k = 3 per node, dedup'd by undirected pair key).
  const edges: Edge[] = [];
  const pairKey = (a: number, b: number) => (a < b ? `${a}_${b}` : `${b}_${a}`);
  const seen = new Set<string>();
  for (let i = 0; i < nodes.length; i++) {
    const a = nodes[i];
    // Find 3 closest within a reasonable cutoff
    const cands: Array<{ j: number; d: number }> = [];
    for (let j = 0; j < nodes.length; j++) {
      if (i === j) continue;
      const dx = a.cx - nodes[j].cx;
      const dy = a.cy - nodes[j].cy;
      const d = Math.hypot(dx, dy);
      if (d < STEP * 1.35) cands.push({ j, d });
    }
    cands.sort((a, b) => a.d - b.d);
    for (const { j, d } of cands.slice(0, 3)) {
      const k = pairKey(i, j);
      if (seen.has(k)) continue;
      seen.add(k);
      // Opacity falls off with distance — far edges are basically invisible
      const opacity = Math.max(0, 0.16 - (d / STEP) * 0.05);
      edges.push({ x1: a.cx, y1: a.cy, x2: nodes[j].cx, y2: nodes[j].cy, opacity });
    }
  }

  return { nodes, edges };
}

export function LatticeBackdrop() {
  const { nodes, edges } = useMemo(buildLattice, []);

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
      style={{
        // Radial mask: full opacity at centre, fades to 0 by viewport edge.
        maskImage:        "radial-gradient(ellipse 70% 70% at 50% 50%, black 30%, transparent 100%)",
        WebkitMaskImage:  "radial-gradient(ellipse 70% 70% at 50% 50%, black 30%, transparent 100%)",
      }}
    >
      <svg
        viewBox="0 0 1600 1000"
        preserveAspectRatio="xMidYMid slice"
        className="w-full h-full"
      >
        {/* Edges first (under the nodes). */}
        <g stroke="hsl(var(--accent))" strokeWidth="0.4">
          {edges.map((e, i) => (
            <line
              key={i}
              x1={e.x1}
              y1={e.y1}
              x2={e.x2}
              y2={e.y2}
              strokeOpacity={e.opacity}
            />
          ))}
        </g>
        {/* Nodes — pulsing ones get the animation class. */}
        <g fill="hsl(var(--accent))">
          {nodes.map((n, i) => (
            <circle
              key={i}
              cx={n.cx}
              cy={n.cy}
              r={n.r}
              opacity={n.pulse ? undefined : 0.32}
              className={n.pulse ? "lattice-pulse" : undefined}
              style={n.pulse ? { animationDelay: `${n.delay}s` } : undefined}
            />
          ))}
        </g>
      </svg>

      {/* Pulse animation — defined inline so we don't pollute globals.css for
          a single landing-only component. */}
      <style jsx>{`
        :global(.lattice-pulse) {
          animation: lattice-pulse 5.4s ease-in-out infinite;
          transform-origin: center;
          transform-box: fill-box;
        }
        @keyframes lattice-pulse {
          0%, 100% { opacity: 0.20; transform: scale(1); }
          50%      { opacity: 0.85; transform: scale(1.6); }
        }
      `}</style>
    </div>
  );
}
