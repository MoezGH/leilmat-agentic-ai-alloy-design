/**
 * In-canvas glossary data (UI/UX audit Tier B2).
 *
 * The canvas surfaces a lot of materials-science jargon raw (CPFEM, KWN,
 * Scheil, Orowan, θ′…).  This is the single source of truth for the
 * `GlossaryModal` quick-reference so a working engineer who isn't the
 * author can decode each term without leaving their session.  Definitions
 * are deliberately one or two sentences and are kept consistent with the
 * fuller /docs explainer.
 */

export type GlossaryCategory =
  | "Simulation methods"
  | "Strengthening physics"
  | "Thermodynamics & phases"
  | "ML & data"
  | "Statistics & honesty";

export interface GlossaryTerm {
  term: string;
  /** Extra strings to match on in search (symbols, full names, aliases). */
  aka?: string;
  category: GlossaryCategory;
  def: string;
}

export const GLOSSARY: GlossaryTerm[] = [
  // ── Simulation methods ───────────────────────────────────────────────
  {
    term: "CALPHAD",
    aka: "CALculation of PHAse Diagrams equilibrium pycalphad",
    category: "Simulation methods",
    def: "CALculation of PHAse Diagrams — computes the equilibrium phase assemblage of an alloy from assessed thermodynamic databases (TDBs). Drives the Phase Assemblage card.",
  },
  {
    term: "Scheil",
    aka: "Scheil-Gulliver solidification segregation freezing range",
    category: "Simulation methods",
    def: "Scheil–Gulliver non-equilibrium solidification: assumes no back-diffusion in the solid and perfect mixing in the liquid. Predicts microsegregation and the freezing range as the alloy solidifies.",
  },
  {
    term: "TTT",
    aka: "Time Temperature Transformation diagram",
    category: "Simulation methods",
    def: "Time–Temperature–Transformation diagram: how long the alloy must hold at each temperature before a phase transformation begins and finishes.",
  },
  {
    term: "KWN",
    aka: "Kampmann Wagner Numerical precipitation kinetics Robson aging",
    category: "Simulation methods",
    def: "Kampmann–Wagner Numerical model of precipitation: tracks nucleation, growth and coarsening over aging time, returning precipitate volume fraction and mean radius. Powers the Precipitation card and aging optimizer.",
  },
  {
    term: "CPFEM",
    aka: "crystal plasticity finite element FFT DAMASK stress strain flow curve",
    category: "Simulation methods",
    def: "Crystal-Plasticity FFT method (run via DAMASK on the cloud): simulates the stress–strain response of a polycrystal by resolving slip on each grain's crystal lattice. Produces the simulated flow curve.",
  },
  {
    term: "RVE",
    aka: "representative volume element microstructure box",
    category: "Simulation methods",
    def: "Representative Volume Element — the small periodic box of grains that is actually simulated, chosen to stand in for the bulk material.",
  },
  {
    term: "Neper",
    aka: "Voronoi tessellation polycrystal grain structure seeds tess",
    category: "Simulation methods",
    def: "Open-source tool that builds a synthetic polycrystal grain structure by Voronoi tessellation from seed points. Source of the Grain Structure card and the CPFEM RVE.",
  },
  {
    term: "Potts model",
    aka: "Monte Carlo grain growth SPPARKS coarsening MCS",
    category: "Simulation methods",
    def: "Monte-Carlo grain-growth model (run via SPPARKS) that coarsens a grain structure over Monte-Carlo steps. Qualitative only — MC steps are not physical time.",
  },
  {
    term: "Phase-field dendrite",
    aka: "KWC Kobayashi Warren Carter anisotropic solidification Taichi",
    category: "Simulation methods",
    def: "Kobayashi–Warren–Carter anisotropic phase-field model of dendritic solidification — grows a realistic dendrite from an undercooled melt.",
  },
  {
    term: "Fick diffusion",
    aka: "Crank Nicolson 1D solute concentration profile",
    category: "Simulation methods",
    def: "1-D solute diffusion solved with Fick's laws via an unconditionally-stable Crank–Nicolson scheme. Drives the Diffusion card.",
  },

  // ── Strengthening physics ────────────────────────────────────────────
  {
    term: "Hall–Petch",
    aka: "Hall Petch grain size strengthening yield",
    category: "Strengthening physics",
    def: "Yield strength rises as grain size falls (σ ∝ d^−½). The grain-size strengthening term — a simulated grain size feeds this contribution into Predict.",
  },
  {
    term: "Orowan looping",
    aka: "Orowan precipitate dislocation bowing volume fraction radius",
    category: "Strengthening physics",
    def: "Strengthening from non-shearable precipitates that dislocations bow around rather than cut. Scales as √(volume fraction)/radius; the precipitation contribution to yield strength.",
  },
  {
    term: "phenopowerlaw",
    aka: "phenomenological power law CRSS constitutive DAMASK slip",
    category: "Strengthening physics",
    def: "DAMASK's phenomenological power-law crystal-plasticity law (slip rate vs resolved shear stress). Its critical resolved shear stress (CRSS) constants are literature values, not fit to your exact alloy — so absolute CPFEM stress is a screening estimate.",
  },
  {
    term: "Cauchy stress",
    aka: "true stress force per current area flow curve y axis",
    category: "Strengthening physics",
    def: "True stress (force divided by the current cross-sectional area) — the y-axis of the CPFEM flow curve.",
  },
  {
    term: "VRH modulus",
    aka: "Voigt Reuss Hill Young elastic average polycrystal",
    category: "Strengthening physics",
    def: "Voigt–Reuss–Hill averaging of single-crystal stiffness to a polycrystal Young's modulus — the value behind the modulus card.",
  },
  {
    term: "Temper",
    aka: "T6 O H14 heat treatment work state designation",
    category: "Strengthening physics",
    def: "The heat-treatment / work-hardening state (e.g. T6, O, H14). The same composition in different tempers can differ 3–5× in yield strength (6061-O = 55 MPa vs 6061-T6 = 276 MPa).",
  },

  // ── Thermodynamics & phases ──────────────────────────────────────────
  {
    term: "β″ (Mg₂Si)",
    aka: "beta double prime Mg2Si 6xxx Al-Mg-Si",
    category: "Thermodynamics & phases",
    def: "The main strengthening precipitate in 6xxx Al–Mg–Si alloys. Needs both Mg and Si present to form.",
  },
  {
    term: "θ′ (Al₂Cu)",
    aka: "theta prime Al2Cu 2xxx Al-Cu",
    category: "Thermodynamics & phases",
    def: "Metastable strengthening precipitate in 2xxx Al–Cu alloys. Needs Cu present.",
  },
  {
    term: "η′ (MgZn₂)",
    aka: "eta prime MgZn2 7xxx Al-Zn-Mg",
    category: "Thermodynamics & phases",
    def: "Strengthening precipitate in 7xxx Al–Zn–Mg alloys.",
  },
  {
    term: "γ′ / γ″",
    aka: "gamma prime Ni3Al gamma double prime Ni3Nb superalloy",
    category: "Thermodynamics & phases",
    def: "Ni₃Al (γ′) and Ni₃Nb (γ″) — the ordered precipitates that strengthen nickel-base superalloys.",
  },
  {
    term: "E above hull",
    aka: "convex hull stability metastable DFT formation energy meV",
    category: "Thermodynamics & phases",
    def: "Energy above the DFT convex hull: 0 meV/atom = thermodynamically stable; larger values = metastable or unstable. Sourced from the Materials Project.",
  },

  // ── ML & data ────────────────────────────────────────────────────────
  {
    term: "M3GNet / MatGL",
    aka: "graph neural network formation energy DFT proxy",
    category: "ML & data",
    def: "A graph neural network that predicts DFT-like formation energy — a fast ML proxy for a full DFT calculation.",
  },
  {
    term: "Miedema",
    aka: "semi empirical formation enthalpy fallback",
    category: "ML & data",
    def: "A semi-empirical model for formation enthalpy. Used as the fallback for formation energy when the M3GNet model isn't loaded.",
  },
  {
    term: "Random Forest",
    aka: "scikit-learn yield strength per family Al Ti Ni steel",
    category: "ML & data",
    def: "Per-family (Al / Ti / Ni / Steel) machine-learning model for yield strength, trained on ~150 handbook-cited alloys with composition + temper features.",
  },
  {
    term: "BoTorch",
    aka: "Bayesian optimization multi objective inverse design Pareto",
    category: "ML & data",
    def: "Multi-objective Bayesian optimizer that powers inverse design — proposes compositions that best hit your property targets.",
  },
  {
    term: "OOD gate",
    aka: "out of domain Mahalanobis extrapolation flag",
    category: "ML & data",
    def: "Out-of-domain detector (Mahalanobis distance). Flags compositions far from the training data so you know a prediction is extrapolative.",
  },

  // ── Statistics & honesty ─────────────────────────────────────────────
  {
    term: "Conformal CI",
    aka: "conformal prediction confidence interval 95 calibration",
    category: "Statistics & honesty",
    def: "A distribution-free 95% confidence interval, calibrated on held-out data — the ± band shown on ML-predicted properties.",
  },
];

/** Tone-coded explanation of the calibration labels on every result. */
export interface CalibrationLabel {
  label: string;
  tone: "emerald" | "sky" | "amber" | "slate";
  meaning: string;
}

export const CALIBRATION_LABELS: CalibrationLabel[] = [
  {
    label: "deterministic-geometry",
    tone: "emerald",
    meaning: "Computed exactly from geometry / first principles (e.g. mean grain size from a tessellation). Trust it as geometry.",
  },
  {
    label: "quantitative-characterization",
    tone: "sky",
    meaning: "A quantitative, model-based measurement of the simulated structure — reliable for trends and comparisons.",
  },
  {
    label: "literature-correlation",
    tone: "amber",
    meaning: "Uses literature-parametrized correlations / constants not fit to your exact alloy. Treat absolute numbers as a screening estimate.",
  },
  {
    label: "qualitative",
    tone: "slate",
    meaning: "Directional / relative only — not an absolute physical value (e.g. Potts Monte-Carlo steps are not physical time).",
  },
];
