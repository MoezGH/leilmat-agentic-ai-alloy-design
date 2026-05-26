"use client";

/**
 * /docs — "How LeilMat works" explainer page.
 *
 * Scope (intentionally narrow): describe what the tool does and the
 * open-source stack underneath it.  This is NOT integration
 * documentation (no code samples, no API recipes) — the Swagger UI at
 * /api/docs serves as the REST API reference.  Subsequent versions
 * may add Mintlify/Docusaurus-style docs if customer demand appears.
 *
 * Visual language: lattice backdrop + warm-gold accent + JetBrains-Mono
 * eyebrow micro-labels to match the landing page.  Reuses
 * ``LatticeBackdrop`` so users navigating from /landing → /docs feel
 * the same product surface.
 */
import { motion } from "framer-motion";
import Link from "next/link";

import { LatticeBackdrop } from "@/components/landing/LatticeBackdrop";


const ACCENT_HSL = "38 96% 60%";


export default function DocsPage() {
  return (
    <main
      style={{
        ["--accent" as keyof React.CSSProperties as string]: ACCENT_HSL,
      } as React.CSSProperties}
      className="relative min-h-[calc(100vh-3.5rem)] overflow-hidden"
    >
      <LatticeBackdrop />

      {/* Left vertical accent rule */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-0 top-0 h-full w-px"
        style={{
          background: "linear-gradient(to bottom, transparent, hsl(var(--accent) / 0.3) 30%, hsl(var(--accent) / 0.3) 70%, transparent)",
        }}
      />

      <div className="relative mx-auto w-full max-w-3xl px-6 pb-32 pt-12 lg:px-0 lg:pt-20">

        {/* ─── Hero ──────────────────────────────────────────── */}
        <header className="space-y-5 mb-16">
          <motion.p
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="font-mono text-[11px] tracking-[0.22em] uppercase"
            style={{ color: "hsl(var(--accent))" }}
          >
            How it works
          </motion.p>
          <motion.h1
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.05 }}
            className="text-5xl font-semibold tracking-tight text-white sm:text-6xl"
          >
            LeilMat under the hood
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.12 }}
            className="max-w-2xl text-base leading-relaxed text-slate-400 sm:text-lg"
          >
            A short, honest tour of the tool: what each surface actually
            does, which open-source projects make it possible, and where
            the numbers come from. Built for working metallurgists who
            want to know what they&rsquo;re trusting.
          </motion.p>
          <div className="flex flex-wrap items-center gap-4 pt-2">
            <Link
              href="/canvas"
              className="inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-[13px] font-semibold transition-all hover:brightness-110"
              style={{
                background: "hsl(var(--accent) / 0.18)",
                color:      "hsl(var(--accent))",
                border:     "1px solid hsl(var(--accent) / 0.4)",
              }}
            >
              Open the design canvas
              <span aria-hidden>→</span>
            </Link>
            <a
              href="/api/docs"
              className="inline-flex items-center gap-2 rounded-lg border border-white/[0.1] px-5 py-2.5 text-[13px] font-medium text-slate-300 transition-colors hover:border-white/20 hover:text-white"
            >
              REST API reference (Swagger)
            </a>
          </div>
        </header>

        {/* ─── 1 · What the tool does ──────────────────────── */}
        <Section eyebrow="01 · What it does" title="An AI-native canvas for alloy design">
          <p>
            LeilMat sits in the space between a CALPHAD tool (Thermo-Calc,
            JMatPro) and an ML platform (Citrine). The canvas is one
            spatial editor where you drag composition sliders, pick a
            temper, and see live property predictions with calibrated
            uncertainty. From there you can run physical simulations
            (CALPHAD equilibrium, Scheil solidification, KWN
            precipitation, 1-D Fick diffusion, anisotropic phase-field
            dendrites) without leaving the page.
          </p>
          <p>
            An agentic AI copilot reads the full session — composition,
            goals, constraints, what you&rsquo;ve explored — and emits
            <em> clickable action pills</em> rather than just narrating
            advice. &ldquo;Set Mg to 4 %, cap density at 2.7, run
            Predict&rdquo; — three taps, three slider mutations, one
            prediction. The whole design exports as a multi-page PDF
            with provenance footnotes on every number.
          </p>
        </Section>

        {/* ─── 2 · Architecture ──────────────────────────── */}
        <Section eyebrow="02 · Architecture" title="Three layers, one canvas">
          <ArchDiagram />
          <p>
            The fast statistical layer (top) gives instant feedback while
            you slide. The physics layer (middle) runs the deterministic
            simulators the predictions are validated against. The data
            layer (bottom) is what makes any of it credible — bundled
            CALPHAD thermodynamic databases, the Materials Project DFT
            corpus, handbook-grade experimental measurements with full
            citations.
          </p>
        </Section>

        {/* ─── 3 · Open-source stack ─────────────────────── */}
        <Section eyebrow="03 · Open-source stack" title="What's underneath">
          <p className="mb-8">
            LeilMat is built on a stack of mature open-source projects.
            Where a paid tool was an option we picked the open one,
            partly for cost but mostly because users in regulated
            industries need to inspect what they&rsquo;re running.
          </p>

          <StackGroup title="Scientific simulation">
            <StackItem name="pycalphad"  notes="CALPHAD equilibrium + Scheil-Gulliver solidification. BSD-licensed; bundled with 7 TDB databases (COST507, mc_fecocrnbti, alcrni, alni, alzn, alcocrni, Fe-C binaries)." />
            <StackItem name="pymatgen"   notes="Materials genomics — structure handling, Materials Project I/O, composition arithmetic." />
            <StackItem name="matminer"   notes="Featurisers for ML on materials (Magpie, composition descriptors)." />
            <StackItem name="mp-api"     notes="Materials Project REST client — DFT-computed properties for ~150k inorganic compounds." />
            <StackItem name="Taichi"     notes="JIT-compiled GPU-friendly phase-field solver. Drives the anisotropic KWC dendrite simulator (~3.6 min for a 6-arm dendrite at 400² on CPU)." />
            <StackItem name="FiPy"       notes="Finite-volume PDE solver used in the simpler phase-field path." />
            <StackItem name="NumPy / SciPy" notes="Crank-Nicolson tridiagonal solver for the 1-D Fick diffusion mini-sim; numerical backbone throughout." />
          </StackGroup>

          <StackGroup title="ML & optimization">
            <StackItem name="scikit-learn" notes="Random Forest models per alloy family (Al / Ti / Ni / Steel). Temper-aware one-hot + strength-index features." />
            <StackItem name="BoTorch"      notes="Multi-objective Bayesian optimisation for inverse design. Conformal-CI-aware acquisition function." />
            <StackItem name="PyTorch"      notes="ML framework under BoTorch and MatGL." />
            <StackItem name="MatGL / M3GNet" notes="Graph neural network for formation-energy predictions; ML proxy for DFT." />
          </StackGroup>

          <StackGroup title="Web platform">
            <StackItem name="FastAPI + Uvicorn"  notes="Async Python API. Pydantic v2 for request/response validation. ~30 endpoints across predict, design, phase, microstructure, precipitation, diffusion, chat, report." />
            <StackItem name="Next.js 15"         notes="React framework. App-router, standalone build, server components for SSR. The design canvas is one big client component." />
            <StackItem name="Tailwind CSS"       notes="Utility-first styling; no component library — the visual language is hand-built." />
            <StackItem name="framer-motion"      notes="Stagger animations on the landing page; spring physics on the right-rail Global AI panel." />
            <StackItem name="Plotly + D3"        notes="Interactive charts (radar, ternary, Pareto). Lighter Plotly subset where possible." />
            <StackItem name="Zustand + Immer"    notes="State management for the canvas — composition, simulation results, AI conversation history. Immer makes the reducer ergonomic." />
            <StackItem name="Supabase (auth + Postgres + pgvector)" notes="Email/Google sign-in, design-session persistence with row-level security, vector storage for the eventual literature RAG." />
            <StackItem name="ChromaDB"           notes="Vector index for the RAG layer (currently deferred — no licensed corpus yet)." />
            <StackItem name="ReportLab"          notes="Audit-grade PDF report generation. Matplotlib charts rendered server-side at 150 dpi and embedded." />
          </StackGroup>

          <StackGroup title="Infrastructure & ops">
            <StackItem name="Docker + docker-compose" notes="Two-service stack: leilmat-api (FastAPI) and leilmat-web (Next.js standalone). Postgres + ChromaDB as siblings." />
            <StackItem name="Traefik"   notes="Reverse proxy + automatic Let's Encrypt SSL. Path-based routing splits /api/* → backend, everything else → frontend." />
            <StackItem name="Hetzner Cloud" notes="CX23 VPS in Helsinki. 4 GB RAM, 2 vCPU, 40 GB NVMe — runs the whole stack at ~$5/month." />
            <StackItem name="OpenRouter"    notes="LLM gateway. Lets us swap between DeepSeek V4 Pro / Claude / GPT / Gemini without touching client code." />
            <StackItem name="slowapi"   notes="Per-IP rate limiting on cost-bearing endpoints (LLM 10/min, heavy compute 4/min)." />
            <StackItem name="python-jose" notes="Supabase JWT validation; ES256 via JWKS, HS256 fallback for legacy projects." />
          </StackGroup>
        </Section>

        {/* ─── 4 · Data sources ─────────────────────────── */}
        <Section eyebrow="04 · Data sources" title="Where the numbers come from">
          <StackGroup title="Thermodynamic databases (bundled, BSD)">
            <StackItem name="COST507"         notes="Light-metal binary + ternary assessments. Reference for Al-Mg, Al-Si, Al-Cu, Al-Zn." />
            <StackItem name="mc_fecocrnbti"   notes="Multi-component Fe-Co-Cr-Ni-Nb-Ti — covers most stainless + superalloy ranges." />
            <StackItem name="alcrni / alni / alzn / alcocrni" notes="Smaller targeted assessments for specific Al-X systems." />
          </StackGroup>

          <StackGroup title="Experimental measurements">
            <StackItem name="LeilMat alloy dataset (Sprint 3)" notes="~150 entries across Al / Ti / Ni / Steel with composition + temper + yield strength + density + hardness. Every row has a handbook citation (ASM, MIL-HDBK-5J, Boyer, Donachie, Reed). Defence-in-depth holdout filter prevents the model from learning a row it's about to be tested on." />
            <StackItem name="Smithells Metals Reference Book (7e)" notes="Source for diffusivity D₀ / Q in the 1-D Fick mini-sim (Al-Mg, Al-Cu, Al-Zn, Fe-Mn, Fe-C, Ni-Cr, Ni-Al pairs)." />
            <StackItem name="Shewmon — Diffusion in Solids" notes="Cross-reference + auxiliary D-coefficients." />
          </StackGroup>

          <StackGroup title="External APIs">
            <StackItem name="Materials Project" notes="DFT-computed formation energies, convex-hull stability, ~150k inorganic structures. Accessed via mp-api with the user&rsquo;s own MP_API_KEY." />
            <StackItem name="NIMS MatNavi (planned)" notes="Free Japanese national materials database — adding ~3k entries via responsible scraping is the next data-ingest sprint (Sprint 3.5, deferred)." />
          </StackGroup>

          <StackGroup title="Models we trained">
            <StackItem name="Random Forest yield strength (per family)" notes="scikit-learn RF. Features: ~50 composition descriptors + temper one-hot + strength index. CV MAE: Al 41 MPa, Ti 101 MPa, Ni 73 MPa, Steel 92 MPa. Conformal calibration on held-out folds gives 95 % CIs." />
            <StackItem name="OOD detector" notes="Per-family Mahalanobis-distance gate. Compositions far from training data get an out-of-domain flag in the UI so the user knows the prediction is extrapolative." />
            <StackItem name="Hierarchical cost model (Sprint 8)" notes="49-test scientific harness; 17/17 quoted alloys within factor-of-2 of supplier prices." />
          </StackGroup>
        </Section>

        {/* ─── 5 · References ──────────────────────────────── */}
        <Section eyebrow="05 · Scientific references" title="What the math is based on">
          <ul className="space-y-2.5 text-[13.5px] leading-relaxed text-slate-400">
            <li><strong className="text-slate-200">Kampmann &amp; Wagner (1984) → Robson (2004)</strong> — numerical precipitation kinetics. Drives the KWN solver and the aging-playback scrubber.</li>
            <li><strong className="text-slate-200">Scheil-Gulliver model</strong> — non-equilibrium solidification microsegregation. Implemented on top of pycalphad.</li>
            <li><strong className="text-slate-200">Crank (1975) — The Mathematics of Diffusion</strong> — Crank-Nicolson finite-difference scheme used by the 1-D Fick mini-sim. Unconditionally stable + second-order accurate.</li>
            <li><strong className="text-slate-200">Hall-Petch + Hollomon</strong> — yield-strength + work-hardening contributions in the Sprint 6 physics-aware feature set.</li>
            <li><strong className="text-slate-200">Voigt-Reuss-Hill averaging</strong> — elastic moduli; gives the YOUNGS_MODULUS card its VRH-branded value.</li>
            <li><strong className="text-slate-200">Karma &amp; Rappel (1998) anisotropic phase-field</strong> — the KWC dendrite simulator&rsquo;s formulation.</li>
            <li><strong className="text-slate-200">Smithells Metals Reference Book (7e), 1992</strong> — diffusivity tables + interfacial energies + reference alloys.</li>
            <li><strong className="text-slate-200">Shewmon, P. G. (1989) Diffusion in Solids</strong> — auxiliary D coefficients + theoretical framing.</li>
          </ul>
        </Section>

        {/* ─── 6 · For developers ───────────────────────── */}
        <Section eyebrow="06 · For developers" title="REST API + source">
          <p>
            Every endpoint in the LeilMat backend is documented as an
            OpenAPI 3 schema with try-it-out support — Swagger UI lives
            at <a href="/api/docs" className="text-[hsl(var(--accent))] underline decoration-dotted underline-offset-2">/api/docs</a>{" "}
            and the raw schema at{" "}
            <a href="/api/openapi.json" className="text-[hsl(var(--accent))] underline decoration-dotted underline-offset-2">/api/openapi.json</a>.
            All cost-bearing endpoints (the LLM ones and the heavy
            simulators) require a Supabase JWT in the Authorization
            header.
          </p>
          <p>
            Source: <a href="https://github.com/MoezGH/LeilMat" target="_blank" rel="noopener noreferrer" className="text-[hsl(var(--accent))] underline decoration-dotted underline-offset-2">github.com/MoezGH/LeilMat</a>{" "}
            (private — request access via the Leil team).
          </p>
        </Section>

        <footer className="mt-24 border-t border-white/[0.06] pt-6 text-[11.5px] text-slate-500 leading-relaxed">
          <p>
            LeilMat is part of the{" "}
            <a href="https://leil.xyz" target="_blank" rel="noopener noreferrer" className="text-slate-300 hover:text-white transition-colors">Leil family</a>{" "}
            of AI-native engineering tools. Validate predictions against
            experiment before production.
          </p>
        </footer>
      </div>
    </main>
  );
}


// ─── Section primitives ──────────────────────────────────────────────

function Section({
  eyebrow,
  title,
  children,
}: {
  eyebrow:  string;
  title:    string;
  children: React.ReactNode;
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.55, ease: "easeOut" }}
      className="mb-16 space-y-4"
    >
      <p
        className="font-mono text-[10px] tracking-[0.22em] uppercase"
        style={{ color: "hsl(var(--accent))" }}
      >
        {eyebrow}
      </p>
      <h2 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
        {title}
      </h2>
      <div className="space-y-4 text-[14px] leading-relaxed text-slate-300">
        {children}
      </div>
    </motion.section>
  );
}


function StackGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-8">
      <h3 className="mb-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        {title}
      </h3>
      <ul className="space-y-2">
        {children}
      </ul>
    </div>
  );
}


function StackItem({ name, notes }: { name: string; notes: string }) {
  return (
    <li className="rounded-lg border border-white/[0.06] bg-white/[0.015] px-4 py-2.5 transition-colors hover:border-[hsl(var(--accent)/0.3)] hover:bg-[hsl(var(--accent)/0.04)]">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="text-[13.5px] font-semibold text-slate-100">{name}</span>
        <span className="text-[12px] leading-snug text-slate-400">— {notes}</span>
      </div>
    </li>
  );
}


// ─── Architecture diagram (ASCII-ish text panel) ───────────────────

function ArchDiagram() {
  const layers: Array<{ label: string; modules: string[]; tone: "gold" | "slate" | "dim" }> = [
    {
      label:   "Fast statistical layer",
      modules: ["Random-Forest yield-strength", "Magpie / VRH / ROM property heuristics", "Conformal-CI calibrator", "OOD-gate"],
      tone:    "gold",
    },
    {
      label:   "Physics simulators",
      modules: [
        "pycalphad equilibrium",
        "Scheil-Gulliver solidification",
        "Fe-C TTT",
        "KWN precipitation",
        "1-D Fick diffusion",
        "Taichi-JIT anisotropic phase-field dendrite",
        "BoTorch inverse design",
      ],
      tone: "slate",
    },
    {
      label:   "Data layer",
      modules: ["CALPHAD TDB databases (BSD)", "Materials Project (MP)", "LeilMat alloy dataset (handbook citations)", "Smithells diffusivities"],
      tone: "dim",
    },
  ];

  return (
    <div className="my-4 space-y-2.5 font-mono text-[11.5px]">
      {layers.map((layer, i) => (
        <div
          key={i}
          className="rounded-md border px-4 py-3"
          style={{
            background:
              layer.tone === "gold"  ? "hsl(var(--accent) / 0.06)" :
              layer.tone === "slate" ? "rgba(255,255,255,0.03)"    :
                                       "rgba(255,255,255,0.015)",
            borderColor:
              layer.tone === "gold"  ? "hsl(var(--accent) / 0.3)"  :
                                       "rgba(255,255,255,0.08)",
          }}
        >
          <div
            className="mb-1.5 text-[10px] uppercase tracking-[0.15em]"
            style={{
              color: layer.tone === "gold" ? "hsl(var(--accent))" : "rgb(148 163 184)",
            }}
          >
            {layer.label}
          </div>
          <div className="flex flex-wrap gap-x-2 gap-y-1 text-slate-300">
            {layer.modules.map((m, j) => (
              <span key={j} className="text-[11.5px]">
                {m}{j < layer.modules.length - 1 && <span className="text-slate-600 ml-2">·</span>}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
