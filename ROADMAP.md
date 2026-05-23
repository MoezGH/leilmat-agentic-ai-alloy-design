# LeilMat — Implementation Roadmap

## Context

LeilMat is an AI-native alloy design canvas at **leil.xyz**. The MVP is live with:
real Materials Project phase diagrams, DeepSeek V4 Pro Local + Global AI with executable
actions, dynamic exploration trajectories, and a polished dark-mode canvas.

The audit on 2026-05-14 revealed that **property prediction and inverse design are still
placeholders** (linear elemental averaging + random search). The roadmap below moves the
tool from "great UX with stub science" to "great UX with defensible science."

---

## Phase 1 — Real Property Prediction *(in progress)*

**Goal:** Replace the placeholder elemental-average predictor with rigorous composition-based
predictions backed by published materials informatics methods.

**Approach (two tracks):**
- **Heuristic track** — matminer's Magpie composition featurizer (132 descriptors, peer-reviewed
  in Ward *et al.* 2016) for properties that admit a closed-form composition rule
  (density via rule-of-mixtures, melting point via mean elemental T_m, electronegativity, valence).
- **ML track** — Random Forest models trained on bundled `matbench` datasets:
  - `matbench_steels` (312 alloys) → yield strength
  - Custom MP-cached set → formation energy
  - Trees give free uncertainty estimates from tree-variance.

**Files:**
- `apps/api/ml/matgl_models.py` — rewrite `predict_properties`
- `apps/api/ml/featurizers.py` *(new)* — matminer wrappers, cached models
- `apps/api/ml/training.py` *(new)* — one-shot training script; pickles models to `models/`
- `apps/web/components/PropertyDashboard.tsx` — show uncertainty bands + `source` chip per property

**Output shape (additive — UI stays compatible):**
```json
{
  "density_g_cm3":    {"value": 2.57, "uncertainty": 0.04, "source": "rule_of_mixtures"},
  "melting_point_K":  {"value": 935,  "uncertainty": 18,   "source": "magpie_mean"},
  "formation_energy_eV_per_atom": {"value": -0.31, "uncertainty": 0.08, "source": "rf_trained_mp"}
}
```

**Verification:**
- Al pure should give density 2.70, T_m 933 K
- Al-4Cu (the canonical 2024 alloy backbone) should be within 10% of experimental values

---

## Phase 2 — Visual Ternary Composition Explorer

**Goal:** Wire up the existing `TernaryPlot.tsx` as a first-class canvas panel with a
property heatmap overlay sampled across the simplex.

**Approach:**
- Sample a 10×10 grid (55 ternary compositions for a 3-element system)
- Run `predict_properties` over the grid in parallel
- Render scatter ternary with colour = chosen property
- Click any point → composition fills the sliders, triggers Local AI

**Files:**
- `apps/web/app/canvas/page.tsx` — add Ternary panel above Phase Diagram
- `apps/web/components/TernaryPlot.tsx` — already exists, integrate with store
- `apps/api/routers/predict.py` — add `POST /predict/batch` endpoint

**Verification:** Al-Mg-Si ternary should show density gradient roughly toward Mg corner.

---

## Phase 3 — Real Bayesian Inverse Design

**Goal:** Replace random-Dirichlet search with proper multi-objective optimisation using
BoTorch's expected hypervolume improvement (qEHVI).

**Approach:**
- Initialise with Sobol sequence (24 points)
- Fit Gaussian Process surrogate per objective (uses Phase 1 predictor as oracle)
- Acquire next batch via qEHVI
- Return real Pareto front + dominated points

**Files:**
- `apps/api/ml/inverse.py` — full rewrite using BoTorch
- `apps/web/components/ParetoExplorer.tsx` — add Pareto-frontier line

**Verification:** Density-min vs T_m-max should produce a Pareto front, not a random scatter.

---

## Phase 4 — Periodic Table Element Picker *(done)*

**Goal:** Replace the text "El + %" inputs with a familiar visual periodic table.

**Approach:**
- 18-column SVG/CSS grid of all elements
- Click element → adds slider with default 5%
- Highlight elements already in the composition
- Disable noble gases / synthetic elements

**Files:**
- `apps/web/components/PeriodicTable.tsx` *(new)*
- `apps/web/app/canvas/page.tsx` — replace inline input with table opened as a popover

**Verification:** Clicking Cu adds it to composition with 5%; clicking again is a no-op.

---

## Out of scope (future)

- Authentication / multi-user
- Public session share URLs
- PDF report export
- Manufacturability scoring (castability, weldability, cost)
- M3GNet/CHGNet GNN integration (big lift — ~600MB model load)

---

## Sequence

1 → 2 → 3 built the **scientific spine** (each unblocked the next).
4 is independent polish.
Literature RAG explicitly skipped — the 4 papers were for inspiration, not training/grounding.
