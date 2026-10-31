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
  ReportOrnament,
  UncertaintyOrnament,
} from "@/components/landing/FeatureCard";
import { SignInPanel }            from "@/components/landing/SignInPanel";
import { Bloom }                  from "@/components/brand/Bloom";




export default function Home() {
  return (
    <main
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
              className="label text-[11px] text-muted"
            >
              Alloy &amp; Materials Design · 03
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.05 }}
              className="flex items-center gap-5 sm:gap-7"
            >
              <Bloom decorative size={96} className="shrink-0" />
              <h1 className="headline whitespace-nowrap text-7xl text-fg sm:text-9xl">Leil-Mat</h1>
            </motion.div>

            <motion.p
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.12 }}
              className="max-w-2xl text-lg leading-relaxed text-muted sm:text-xl"
            >
              AI-native canvas for alloy design. Periodic-table spatial
              editor, validated property prediction, and{" "}
              <span className="text-fg">
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
                className="inline-flex items-center gap-2 rounded-lg bg-brand px-5 py-2.5 text-[13px] font-semibold text-white transition-colors hover:bg-brand/90"
              >
                Open Design Canvas
                <span aria-hidden>→</span>
              </a>
              <a
                href="/docs"
                className="inline-flex items-center gap-2 rounded-lg border border-line px-5 py-2.5 text-[13px] font-medium text-muted transition-colors hover:border-fg/30 hover:text-fg"
              >
                How it works
              </a>
            </motion.div>
          </header>

          {/* The flow — a one-line orientation of how the canvas is used,
              so a first-time visitor knows the shape before diving in. */}
          <div>
            <motion.h2
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
              className="label mb-4 text-[11px] text-subtle"
            >
              How it flows
            </motion.h2>
            <WorkflowFlow />
          </div>

          {/* Numbered feature cards */}
          <div>
            <motion.h2
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
              className="mb-6 font-mono text-[11px] tracking-[0.22em] uppercase text-subtle"
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
            className="max-w-2xl pt-2 text-[12px] leading-relaxed text-subtle"
          >
            Built on a broad scientific harness — pycalphad equilibrium,
            Scheil-Gulliver + Fe-C TTT, KWN precipitation kinetics with an
            interactive aging-playback scrubber, a 1-D Fick diffusion
            mini-sim, a Taichi-JIT anisotropic phase-field dendrite
            simulator, Neper grain structures with Potts grain growth,
            DAMASK crystal-plasticity (CPFEM) stress–strain, a
            heat-treatment aging optimizer, and conformal-calibrated ML
            models for mechanical properties. An agentic AI copilot
            proposes concrete design steps you apply with one click; the
            canvas exports as an audit-grade PDF report.&nbsp;
            <a href="/docs" className="underline decoration-dotted underline-offset-2 hover:text-muted transition-colors">
              See how it works →
            </a>
          </motion.p>
        </section>

        {/* ───── Right rail ───── */}
        <SignInPanel />
      </div>
    </main>
  );
}


// ──────────────────────────────────────────────────────────────────────
// Workflow flow strip — the compose → … → export shape of a session.
// ──────────────────────────────────────────────────────────────────────

const FLOW_STEPS = ["Compose", "Predict", "Simulate", "Optimize", "Export PDF"];

function WorkflowFlow() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.5 }}
      className="flex flex-wrap items-center gap-2 font-mono text-[11px]"
    >
      {FLOW_STEPS.map((s, i) => (
        <span key={s} className="flex items-center gap-2">
          <span
            className="rounded-md border px-2.5 py-1"
            style={{
              borderColor: "hsl(var(--accent) / 0.25)",
              background:  "hsl(var(--accent) / 0.06)",
              color:       "hsl(var(--accent))",
            }}
          >
            {s}
          </span>
          {i < FLOW_STEPS.length - 1 && (
            <span className="text-subtle" aria-hidden>→</span>
          )}
        </span>
      ))}
    </motion.div>
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
      "Mechanical and thermal properties from composition — RF + physics features, family-specific calibration, temper-aware encoding.",
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
    category:    "10 modules",
    title:       "Process Simulation",
    href:        "/canvas",
    description:
      "CALPHAD equilibrium · Scheil solidification · Fe-C TTT · microstructure · KWN precipitation with aging-playback scrubber · 1-D Fick diffusion · Neper grain structure · Potts grain growth · DAMASK CPFEM stress–strain · heat-treatment aging optimizer.",
    ornament:    <PhaseDiagramOrnament />,
  },
  {
    category:    "Click → apply",
    title:       "Agentic AI Copilot",
    href:        "/canvas",
    description:
      "The AI doesn't just narrate — it emits clickable action pills that mutate the canvas. \"Set Mg to 4 %\" / \"Cap density at 2.7\" / \"Run Predict\" — design steps you accept with one tap.",
    ornament:    <CopilotOrnament />,
  },
  {
    category:    "One-click PDF",
    title:       "Audit-grade Reports",
    href:        "/canvas",
    description:
      "Every design exports as a multi-page PDF: composition, property table with ±CI, radar chart, phase + KWN trajectories, AI rationale, full provenance bibliography. Ready for a design-review packet.",
    ornament:    <ReportOrnament />,
  },
  {
    category:    "± CI everywhere",
    title:       "Conformal Uncertainty",
    href:        "/docs",
    description:
      "Every ML prediction carries a calibrated 95 % confidence interval plus an out-of-domain flag. No black-box numbers — provenance and uncertainty travel with the value into the report.",
    ornament:    <UncertaintyOrnament />,
  },
];
