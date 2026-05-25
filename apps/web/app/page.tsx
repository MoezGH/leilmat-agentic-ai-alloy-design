"use client";

/**
 * LeilMat landing page.
 *
 * Visual brief
 * ────────────
 *   Inspired by the leil.xyz portfolio page (numbered cards, brand-
 *   coloured accents, constellation-style backdrop) but materials-themed:
 *
 *   * Animated crystal-lattice backdrop covers the whole viewport at
 *     low opacity (``LatticeBackdrop``).
 *   * Left/main column: LeilMat wordmark, tagline, primary CTA, and a
 *     2×2 grid of four numbered feature cards (Property Prediction,
 *     Inverse Design, Phase Diagrams, AI Copilot).
 *   * Right rail: ``SignInPanel`` (Google sign-in or welcome-back).
 *     On narrow viewports it stacks below the hero.
 *
 * Routing assumptions
 * ───────────────────
 *   * /canvas is the actual app; this page is the marketing / entry door.
 *   * The header's signed-out "Sign in with Google" button is suppressed
 *     specifically on this route — see ``LeilHeader.tsx``.
 */
import { motion } from "framer-motion";

import { LatticeBackdrop }       from "@/components/landing/LatticeBackdrop";
import {
  FeatureCard,
  LatticeOrnament,
  ParetoOrnament,
  PhaseDiagramOrnament,
  CopilotOrnament,
} from "@/components/landing/FeatureCard";
import { SignInPanel }            from "@/components/landing/SignInPanel";


// LeilMat brand accent — warm gold, matches LeilHeader and leil.xyz card.
const ACCENT_HSL = "38 96% 60%";


export default function Home() {
  return (
    <main
      // Set --accent on the page root so every descendant component
      // (cards, sign-in panel, backdrop) reads the same value.
      style={{
        ["--accent" as keyof React.CSSProperties as string]: ACCENT_HSL,
      } as React.CSSProperties}
      className="relative min-h-[calc(100vh-3.5rem)] overflow-hidden"
    >
      {/* Animated atomic-lattice constellation, behind everything */}
      <LatticeBackdrop />

      {/* Vertical accent line on the far left — a small leil.xyz tell */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-0 top-0 h-full w-px"
        style={{
          background: "linear-gradient(to bottom, transparent, hsl(var(--accent) / 0.3) 30%, hsl(var(--accent) / 0.3) 70%, transparent)",
        }}
      />

      <div className="relative mx-auto grid w-full max-w-[1400px] grid-cols-1 gap-12 px-6 pb-24 pt-12 lg:grid-cols-[1fr_400px] lg:gap-16 lg:px-12 lg:pt-20">

        {/* ───── Left / main column ───── */}
        <section className="space-y-16">

          {/* Hero block */}
          <header className="space-y-6">
            <motion.p
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="font-mono text-[11px] tracking-[0.22em] uppercase"
              style={{ color: "hsl(var(--accent))" }}
            >
              Alloy &amp; Materials Design · 03
            </motion.p>

            <motion.h1
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.05 }}
              className="text-6xl font-semibold tracking-tight text-white sm:text-7xl"
            >
              Leil<span style={{ color: "hsl(var(--accent))" }}>Mat</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.12 }}
              className="max-w-2xl text-lg leading-relaxed text-slate-400 sm:text-xl"
            >
              AI-native canvas for alloy design. Periodic-table spatial
              editor, validated property prediction, and{" "}
              <span className="text-slate-200">
                click-to-trace provenance on every number.
              </span>
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="flex flex-wrap items-center gap-4 pt-2"
            >
              <a
                href="/canvas"
                className="inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-[13px] font-semibold transition-all hover:brightness-110"
                style={{
                  background: "hsl(var(--accent) / 0.18)",
                  color:      "hsl(var(--accent))",
                  border:     "1px solid hsl(var(--accent) / 0.4)",
                }}
              >
                Open Design Canvas
                <span aria-hidden>→</span>
              </a>
              <a
                href="/api/backend/docs"
                target="_blank"
                rel="noopener"
                className="inline-flex items-center gap-2 rounded-lg border border-white/[0.1] px-5 py-2.5 text-[13px] font-medium text-slate-300 transition-colors hover:border-white/20 hover:text-white"
              >
                API Docs
              </a>
            </motion.div>
          </header>

          {/* Numbered feature cards */}
          <div>
            <motion.h2
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
              className="mb-6 font-mono text-[11px] tracking-[0.22em] uppercase text-slate-500"
            >
              What lives inside
            </motion.h2>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {FEATURES.map((f, i) => (
                <FeatureCard
                  key={f.title}
                  index={i + 1}
                  category={f.category}
                  title={f.title}
                  href={f.href}
                  description={f.description}
                  ornament={f.ornament}
                />
              ))}
            </div>
          </div>

          {/* Footnote — provenance / scientific posture */}
          <motion.p
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="max-w-2xl pt-2 text-[12px] leading-relaxed text-slate-500"
          >
            Built on a 287-test scientific harness — pycalphad equilibrium,
            Scheil-Gulliver + Fe-C TTT, KWN precipitation kinetics, a Taichi-JIT
            anisotropic phase-field dendrite simulator, and conformal-calibrated
            ML models for mechanical properties. Every prediction carries its
            source and uncertainty.
          </motion.p>
        </section>

        {/* ───── Right rail ───── */}
        <SignInPanel />
      </div>
    </main>
  );
}


// ──────────────────────────────────────────────────────────────────────
// Feature catalogue
// ──────────────────────────────────────────────────────────────────────

const FEATURES = [
  {
    category:    "ML · Conformal",
    title:       "Property Prediction",
    href:        "/canvas",
    description:
      "Mechanical and thermal properties from composition — RF + physics features, family-specific calibration, conformal confidence intervals.",
    ornament:    <LatticeOrnament />,
  },
  {
    category:    "BoTorch · Pareto",
    title:       "Inverse Design",
    href:        "/canvas",
    description:
      "Target a property envelope, get Pareto-optimal alloy candidates. Engineering briefs explain the why for each suggestion.",
    ornament:    <ParetoOrnament />,
  },
  {
    category:    "CALPHAD · MP",
    title:       "Phase Diagrams",
    href:        "/canvas",
    description:
      "Binary and ternary phase stability via pycalphad and Materials Project. Equilibrium fractions, Scheil solidification, Fe-C TTT.",
    ornament:    <PhaseDiagramOrnament />,
  },
  {
    category:    "Local + Global",
    title:       "AI Copilot",
    href:        "/canvas",
    description:
      "LLM-narrated interpretation on every score, plus a session-wide design copilot that ties composition, phases, and properties together.",
    ornament:    <CopilotOrnament />,
  },
];
