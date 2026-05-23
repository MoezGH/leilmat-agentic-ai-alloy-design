# LeilMat

**AI-native alloy design canvas** — predict properties, run Bayesian inverse design, score manufacturability, and explore composition spaces with a conversational AI copilot.

Live at **leil.xyz** (planned). Built for the STEM community: materials engineers, researchers, and product designers who want fast, scientifically defensible answers to "what alloy should I use?"

---

## What it does

| Feature | What it gives you |
|---|---|
| **Property prediction** | Composition → density, melting point, yield strength (family-routed), formation energy (M3GNet), elastic modulus, hardness, fatigue, corrosion — each with `{value, ci_low, ci_high, coverage, source}` provenance. Yield strength + formation energy carry 90% conformal intervals. |
| **Out-of-distribution gating** | KNN-distance check refuses compositions outside each model's training envelope (e.g. AISI 304 stainless gets refused by the high-strength steel model with a clear "21× threshold" explanation rather than predicting 2331 MPa) |
| **Phase Diagram** | Real DFT-grounded stable phases from the Materials Project (e.g. 791 entries → 8 stable phases for Al-Mg-Si) |
| **Ternary Explorer** | 66-point simplex heatmap of any property across an A-B-C system; click a cell to design from there |
| **Bayesian Inverse Design** | BoTorch qEHVI multi-objective optimisation returning a real Pareto front (Sobol seed → GP surrogates → q-Expected Hypervolume Improvement) |
| **Exploration Sweeps** | AI-triggered parameter sweeps with live-streaming property curves |
| **Manufacturability** | Castability + Weldability (IIW Carbon Equivalent) + Cost scores on a 0-100 scale |
| **Periodic Table picker** | Visual element picker with auto-renormalisation, category color coding, and disabled cells for noble gases / synthetics |
| **Local AI** | Click any element on the canvas → DeepSeek V4 Pro suggests 2-3 actionable changes with one-click "Apply" buttons |
| **Global AI** | Side panel chat over the full design session + "Global Scan" for proactive insights |

---

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                  Next.js 15 (TypeScript) — port 4000           │
│  Canvas page · Periodic Table modal · Property/Phase/Ternary   │
│  Pareto/Sweep panels · Local-AI popover · Global-AI side panel │
└──────────────────────────┬─────────────────────────────────────┘
                           │ HTTP + SSE
┌──────────────────────────▼─────────────────────────────────────┐
│                FastAPI 0.136 (Python 3.12) — port 8000          │
│                                                                │
│  /api/predict       /api/predict/batch    /api/phase/diagram   │
│  /api/design/inverse  /api/chat/{local,global,scan}            │
│  /api/health/models  /api/phase/hull                            │
└──┬───────────────┬───────────────┬────────────────┬────────────┘
   │               │               │                │
   ▼               ▼               ▼                ▼
matminer +      BoTorch         pymatgen +        OpenRouter
sklearn RFs     (qEHVI GP)      Materials         → DeepSeek
+ matgl/        multi-obj.      Project API       V4 Pro
M3GNet          inverse         (real DFT data)   (reasoning
+ KNN-OOD +     design)                           disabled)
split-conformal
calibrators

  ┌──────────────────────────────────────────────────────────┐
  │  PostgreSQL + pgvector (Docker)   ChromaDB (Docker)      │
  │  session persistence (planned)    RAG vector store        │
  └──────────────────────────────────────────────────────────┘
```

### Repo layout

```
LeilMat/
├── apps/
│   ├── api/                       FastAPI backend
│   │   ├── main.py                app entry + CORS + lifespan (preloads M3GNet)
│   │   ├── config.py              env-driven settings
│   │   ├── routers/
│   │   │   ├── predict.py         POST /api/predict + /batch
│   │   │   ├── design.py          POST /api/design/inverse
│   │   │   ├── phase.py           GET /api/phase/diagram + /hull (MP API)
│   │   │   ├── chat.py            Local/Global/Scan SSE streaming
│   │   │   └── health.py          GET /api/health/models (load state)
│   │   ├── ml/
│   │   │   ├── featurizers.py     Magpie + ROM + VRH + Miedema fallback
│   │   │   ├── matgl_models.py    predict_properties orchestrator + YS routing
│   │   │   ├── m3gnet_predictor.py  M3GNet path: L12 ordering, N=6 replicas, mean
│   │   │   ├── secondary_properties.py  hardness, fatigue, corrosion rules
│   │   │   ├── manufacturability.py     Castability + Weldability + Cost
│   │   │   ├── ood.py             KNN-distance out-of-distribution gate
│   │   │   ├── calibration.py     SplitConformalPredictor (heteroscedastic)
│   │   │   ├── alloy_datasets.py  Hand-curated Al/Ti/Ni alloys for training
│   │   │   ├── training.py        RF training + OOD + conformal fitting
│   │   │   ├── inverse.py         BoTorch qEHVI + random fallback
│   │   │   └── eval/              ← validation harness (see "Verification scorecard")
│   │   │       ├── holdout_alloys.py     curated test alloys
│   │   │       ├── canonical_phases.py   MP-cited ΔH_f references
│   │   │       ├── holdout_runner.py     production-model exerciser
│   │   │       ├── formation_energy_runner.py  same for M3GNet
│   │   │       ├── loo_validation.py     leave-one-out CV
│   │   │       ├── scorecard.py          Markdown report CLI
│   │   │       └── test_*.py             50 pytest regression tests
│   │   ├── data/
│   │   │   ├── database.py        async SQLAlchemy engine
│   │   │   ├── models.py          DesignSession, SavedComposition, ChatMessage
│   │   │   └── optimade.py        OPTIMADE-compatible queries
│   │   └── rag/pipeline.py        ChromaDB ingestion (not currently active)
│   └── web/                       Next.js 15 frontend
│       ├── app/
│       │   ├── layout.tsx         RootLayout + Toaster
│       │   ├── page.tsx           landing
│       │   └── canvas/page.tsx    main design canvas
│       ├── components/
│       │   ├── LocalAISuggestion.tsx   selection-anchored popover
│       │   ├── GlobalAIPanel.tsx       side chat panel
│       │   ├── PropertyDashboard.tsx   radar + property cards
│       │   ├── PhaseDiagram.tsx        stable-phases bar chart
│       │   ├── TernaryExplorer.tsx     simplex-grid heatmap
│       │   ├── ParetoExplorer.tsx      qEHVI results scatter
│       │   ├── ExplorationTrajectory.tsx  sweep results line
│       │   ├── ManufacturabilityPanel.tsx  3-bar scorecard
│       │   └── PeriodicTable.tsx       element picker modal
│       ├── data/elements.ts       all 118 elements w/ grid positions
│       └── lib/
│           ├── store.ts           Zustand canvas state + applyAction
│           └── api.ts             typed fetch + SSE streaming helpers
├── models/
│   └── yield_strength_rf.pkl      RF trained on matbench_steels
├── Alloys Design/                 reference PDFs (inspiration only)
├── docker-compose.yml             db + chromadb + api + web
├── ROADMAP.md                     5-phase plan
└── CHANGELOG.md                   build history
```

---

## Quick start

### Prerequisites

- Docker Desktop (for PostgreSQL + ChromaDB containers)
- Python 3.11+ and Node 22+ for local dev
- An [OpenRouter](https://openrouter.ai/keys) API key (for DeepSeek V4 Pro)
- A [Materials Project](https://next-gen.materialsproject.org/api) API key (for real phase diagrams)

### Configure environment

```bash
cp .env.example .env
# Fill in OPENROUTER_API_KEY, MP_API_KEY
```

### Run (local dev)

Bring up the infra containers (PostgreSQL + ChromaDB):

```bash
docker compose up db chromadb -d
```

Backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
pip install python-multipart greenlet scikit-learn  # extras
python -m apps.api.ml.training yield                # one-time RF training
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir apps
```

Frontend:

```bash
cd apps/web
npm install
npm run dev      # → http://localhost:4000
```

Open **http://localhost:4000/canvas**.

### Run (Docker, future)

Once images are built end-to-end:

```bash
docker compose up --build
```

---

## Scientific basis

Every prediction LeilMat shows comes with a `source` tag the UI surfaces as a coloured badge. **No silent black boxes.**

| Property | Method | Source tag | Typical accuracy |
|---|---|---|---|
| Density | Mass-weighted rule of mixtures: 1/ρ = Σ wᵢ/ρᵢ | `ROM` (green) | 1–4 % vs experimental |
| Melting point | Magpie mean elemental T_m (Ward *et al.*, npj Comput. Mater. 2016) | `Magpie` (blue) | 5–10 % (overestimates for eutectics) |
| Yield strength | Family-routed Random Forest with fall-through: Fe ≥ 50% tries `matbench_steels` (n=312, ultra-high-strength only) first, then `general_steel` (n=35, mild/low-alloy/stainless/PH) if OOD; Al/Ti/Ni use single curated sets (n=20–35, 80%/50%/40% thresholds). Each prediction routed through a KNN out-of-distribution gate and wrapped in a 90% split-conformal interval. | `RF/Steels` `RF/GenSteel` `RF/Al` `RF/Ti` `RF/Ni` | CV MAE 58–219 MPa per family; **75–100% empirical coverage** on held-out alloys |
| **Formation E** | **M3GNet (Chen & Ong, Nat. Comput. Sci. 2022)** — `M3GNet-Eform-MP-2018.6.1` on a 32-atom supercell. L12 ordering for FCC 75:25 compositions, plus N=6 random replicas; mean over candidates is the prediction. Wrapped in a 90% conformal interval calibrated against MP-PBE references. | `M3GNet` (fuchsia) | **80 meV/atom MAE** over 18 canonical phases; 110 meV/atom on intermetallics (Ni3Al 14 meV, Ti3Al 310 meV — see scorecard) |
| Elastic modulus | Voigt-Reuss-Hill volume-fraction averaging (Voigt 1889 / Reuss 1929 / Hill 1952) on Ashby elemental moduli | `VRH` (blue) | ~10-15 % for solid solutions; reports Voigt + Reuss bounds |
| Hardness | Tabor's rule: HV ≈ YS_MPa / 3 with family corrections | `Tabor` (teal) | empirical, depends on YS accuracy |
| Fatigue endurance | Empirical σₑ/UTS ratio (0.4-0.5) with family-specific corrections | `σ_e/UTS` (pink) | indicative |
| Corrosion resistance | Multi-rule: PREN for Fe-Cr-Mo-N stainless; passive-film flags for Ti/Zn/Al; galvanic electrochemistry for the rest | `PREN` / `TiO₂ film` / `Electrochem` | qualitative (Excellent/Good/Fair/Poor) |
| Electronegativity / Valence | Magpie composition-weighted means | `Magpie` | descriptor, not approximation |
| **Phase Diagram** | Live query of Materials Project REST API → `pymatgen.analysis.phase_diagram.PhaseDiagram` convex hull | (real DFT data) | DFT-grade |
| **Castability** | Tm-based base + Al-Si / Fe-C / Zn-Al eutectic boosts + reactive-element penalties (ASM Handbook v.15) | heuristic | qualitative |
| **Weldability** | IIW Carbon Equivalent (Yurioka, ISIJ Int. 2001) for Fe alloys; Cu/Mg/Zn penalty rules for Al alloys; specialty flags for Ti, Cu | rule-based | industry-standard for steels |
| **Cost** | Mass-weighted spot prices (USD/kg, LME / USGS Mineral Commodity Summaries 2025) on log scale | `spot_prices_2025` | indicative |

### Verification scorecard

**Density / melting point** — closed-form predictors hit pure elements exactly and stay within 4 % on common alloys:

| Alloy | Real ρ | Predicted ρ | Real T_m | Predicted T_m |
|---|---|---|---|---|
| Pure Al | 2.70 | **2.70** | 933 K | **933 K** |
| Pure Fe | 7.87 | **7.87** | 1811 K | **1811 K** |
| AISI 304 (Fe-18Cr-8Ni) | 7.93 | 7.82 (-1.4 %) | ~1727 K | 1871 K (+8 %) |
| Al-4Cu | 2.78 | 2.88 (+3.6 %) | 929 K | 950 K (+2.3 %) |

**Yield strength** — output of `python -m apps.api.ml.eval.scorecard`:

| Family | n train | CV MAE | Hold-out MAE | Conformal q | Hold-out CI coverage | OOD correct | False-positive |
|---|---:|---:|---:|---:|---:|---:|---:|
| aluminum | 29 | 58 | 19 | 1.95 | **100 %** (4/4) | 1 | 0 |
| titanium | 20 | 125 | 153 | 2.17 | **100 %** (4/4) | 1 | 0 |
| nickel | 23 | 151 | 219 | 2.36 | **100 %** (4/4) | 1 | 0 |
| steel | 312 + 35 | 110 / 219 | 280 (general_steel fall-through) | 1.77 / 2.10 | **75 %** (3/4) | 2 (Maraging / AerMet — edge of both models) | 0 |

The two steel models work as a fall-through chain. Fe-rich compositions first hit `matbench_steels` (ultra-high-strength martensitic/maraging/AHSS, 1006-2510 MPa); if its OOD gate refuses (mild structural steel, stainless, PH), the predictor falls through to `general_steel` (n=35 hand-curated mild/low-alloy/stainless/PH alloys, 170-1900 MPa). Worked example: **AISI 304 stainless was returning a nonsense 2331 MPa from `matbench_steels`; the OOD gate now refuses that path; `general_steel` predicts 236 MPa (real value 215, error 21).** AISI 1018 mild and AISI 4140 follow the same pattern (errors 11 and 32 MPa respectively).

**Formation energy** — M3GNet on canonical phases vs MP-PBE references:

| Class | n | MAE (meV/atom) | Median | Worst |
|---|---:|---:|---:|---:|
| Pure elements (Eform = 0 by def.) | 5 | 0 | 0 | 0 |
| Stoichiometric intermetallics | 13 | **110** | 92 | 310 (α2-Ti3Al, HCP-D019 — random supercell can't represent it) |
| Overall | 18 | **80** | 49 | 310 |

Notable per-phase residuals: γ'-Ni3Al **14 meV** (L12 ordering kicks in), Ni3Ti **12 meV**, β-NiAl 49, θ-Al2Cu 48. The worst cases (Ti3Al, Mg2Si, NiTi) are non-L12 orderings on lattices we don't yet build deterministically — MP-structure lookup is the queued next step.

**Manufacturability** — same as before:

| Alloy | Cast | Weld | Cost | Overall | Engineering opinion |
|---|---|---|---|---|---|
| A356 cast Al | 100 | 90 | 91 | **93.5** | textbook castable |
| C36000 brass | 84 | 75 | 82 | **80.1** | classic free-machining |
| AISI 4140 | 44 | 75 | 100 | **72.9** | CE = 0.509, preheat zone |
| Ti-6Al-4V | 10 | 35 | 77 | **40.9** | reactive + inert-gas welding |
| Pt-10Rh | 32 | 65 | 0 | **32.3** | exotic, $44k/kg |

### Validation harness

The scorecard above is regenerated from a regression-gate test suite:

```bash
# Full scorecard (Markdown to stdout)
python -m apps.api.ml.eval.scorecard

# Pytest suite — 50 tests covering OOD, hold-out MAE, conformal coverage, M3GNet
pytest apps/api/ml/eval/
```

Layout under `apps/api/ml/eval/`:

| File | Purpose |
|---|---|
| `holdout_alloys.py` | 20 canonical alloys (5 per family) with literature YS values, none in training data. Each tagged `expected_in_domain: True/False` for the OOD gate. |
| `canonical_phases.py` | 13 stoichiometric intermetallics with live-fetchable MP-PBE references (`--verify` to refresh from MP). Plus 5 pure-element controls. |
| `loo_validation.py` | Leave-one-out CV for the small non-ferrous YS families. |
| `holdout_runner.py` | Exercises the *production* `yield_strength_MPa` predictor including OOD routing and conformal intervals. |
| `formation_energy_runner.py` | Same for `formation_energy_eV_per_atom` (M3GNet path). |
| `scorecard.py` | CLI that ties everything together into a Markdown report. |
| `test_yield_strength.py`, `test_formation_energy.py`, `test_conformal_coverage.py` | 50 pytest regression tests. |

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | **Next.js 15** + TypeScript + Tailwind | SSR, AI SDK integration, type safety |
| Charts | **Plotly.js** + **D3** | Ternary diagrams, phase diagrams, scatter, radar |
| State | **Zustand** + Immer | Lightweight reactive store, immutable updates |
| Animations | **Framer Motion** | Popover and panel transitions |
| Backend | **FastAPI** (Python 3.12) | Async + native ML interop + OpenAPI docs |
| LLM | **DeepSeek V4 Pro** via OpenRouter | 1M context, reasoning disabled for low-latency streaming |
| ML — featurization | **matminer** (Magpie preset, 132 descriptors) | Peer-reviewed materials informatics features |
| ML — training | **scikit-learn** Random Forest + custom **split-conformal** wrapper | Tree-variance heteroscedastic estimate scaled by a conformal quantile → 90 % marginal coverage guarantee |
| ML — formation E | **M3GNet** (`M3GNet-Eform-MP-2018.6.1`) via `matgl` | DFT-grade pretrained on Materials Project; reproducible via fixed torch seed + deterministic algorithms |
| ML — OOD detection | KNN distance in standardized Magpie space | Refuses out-of-distribution compositions cleanly (e.g. AISI 304 vs the matbench_steels ultra-high-strength domain) |
| ML — inverse design | **BoTorch** + **GPyTorch** (qEHVI + GP surrogates) | State of the art multi-objective Bayesian optimisation |
| Materials DB | **mp-api** + **pymatgen** | First-party Materials Project client, DFT convex hulls |
| Infra | **Docker Compose** (PostgreSQL/pgvector + ChromaDB) | Reproducible local dev |

---

## API reference (brief)

| Endpoint | Description |
|---|---|
| `POST /api/predict` | Single composition → all properties + manufacturability. Each property carries a `{value, ci_low, ci_high, coverage, calibration, source}` block. |
| `POST /api/predict/batch` | List of compositions (max 500) → list of results |
| `POST /api/design/inverse` | BoTorch qEHVI run; returns ranked Pareto + dominated candidates |
| `GET /api/phase/diagram?elements=Al,Mg,Si` | Materials Project DFT convex hull |
| `GET /api/phase/hull?composition=...&formation_energy=...` | Distance above the MP convex hull for a (composition, ΔH_f) pair |
| `GET /api/health/models` | Live load state of M3GNet + its conformal calibrator + metadata on the four YS bundles (used by the frontend to show a loading badge during cold start) |
| `POST /api/chat/local` | SSE: structured suggestions for selected canvas element |
| `POST /api/chat/global` | SSE: chat over full session (RAG-ready, currently off) |
| `POST /api/chat/scan` | SSE: proactive insights across the session |

Auto-generated OpenAPI docs at **http://localhost:8000/docs**.

---

## Local + Global AI

LeilMat distinguishes two AI scopes — **not** local vs cloud inference; both run on DeepSeek V4 Pro via OpenRouter.

- **Local AI** = selection-aware popover. User clicks any canvas element → the AI sees just that element + a compact canvas summary → returns 2-3 suggestions, each with an `executable` action (`set_element`, `delta_element`, `set_target`, `sweep`). One-click **Apply** mutates the composition, auto-re-predicts, and (for sweeps) generates a live trajectory.
- **Global AI** = side panel chat with the full design session as context. Includes a **Global Scan** button that proactively flags patterns, contradictions, or unexplored regions.

Both stream via Server-Sent Events. The `reasoning: {exclude: true}` flag is set on the OpenRouter call so DeepSeek V4 Pro's reasoning tokens don't consume the budget — content streams immediately.

---

## Limitations & honest caveats

- **Yield strength** routes by majority element: Fe ≥ 50 % → matbench_steels (ultra-high-strength only, 1006-2510 MPa); Al ≥ 80 % → curated Al set; Ti ≥ 50 %, Ni ≥ 40 % → curated Ti/Ni sets. Compositions outside the per-family training envelope are refused by a KNN out-of-distribution gate with a clear error rather than silently extrapolated. *Mild and stainless steels are correctly OOD — they need a separate dataset to predict at all (queued).*
- **Formation energy** uses M3GNet (Chen & Ong, 2022) on a 32-atom supercell — L12 ordering when the composition matches, plus N=6 random replicas. Predictions wrapped in a 90 % conformal interval calibrated against MP-PBE on 13 canonical phases. Ordered non-L12 phases (Ti3Al D019, Mg2Si antifluorite, NiTi B2) sit at the wide end of the interval because our supercell builder can't represent their exact ground-state ordering — MP-structure lookup is the queued fix.
- **Uncertainty bands** are conformal (90 % marginal coverage) for yield strength + formation energy, heuristic for everything else. The `_details` block surfaces `calibration: "conformal"` vs `"tree_std_heuristic"` per-property so the UI can be honest.
- **Inverse design** assumes the predictor is well-calibrated. With density (ROM), melting point (Magpie), and the new conformal-bounded yield strength + M3GNet formation energy as objectives, BoTorch finds defensible Pareto fronts.
- **Cost scores** use 2025 spot prices; they're indicative only — real procurement involves form factor, purity, and supplier.
- **Phase Diagram** depends on MP API availability and the user's API key quota.
- **Reference PDFs** in `/Alloys Design/` are inspiration only — they are NOT used to train, ground, or cite the AI.

---

## Roadmap

See [ROADMAP.md](ROADMAP.md). The original 4 phases are complete. Manufacturability scoring was added as a bonus phase.

**Shipped (post-roadmap):**
- ✅ Family-routed non-ferrous yield strength (Al, Ti, Ni datasets)
- ✅ KNN out-of-distribution gate per family (refuses AISI 304 cleanly instead of predicting 2331 MPa)
- ✅ M3GNet integration for DFT-grade formation energy (80 meV/atom MAE on canonical phases)
- ✅ Split-conformal prediction intervals on every predicted property (90 % marginal coverage)
- ✅ Validation harness: 50 pytest tests + Markdown scorecard CLI
- ✅ Model-health endpoint + UI loading indicator during M3GNet cold-start

**Shipped (since the last README update):**
- ✅ MP-structure lookup as an additional M3GNet candidate (modest aggregate win; θ-Al2Cu residual collapsed from 48 to 1 meV/atom)
- ✅ `general_steel` model + fall-through routing for mild/structural/stainless/PH steels — AISI 304, 1018, 4140 now predict instead of OOD-refusing

**Queued next:**
- Session persistence + share links (DB schema is already in `data/models.py`)
- PDF report export
- Periodic table picker grouped views (lightweight, refractory, precious)
- Auth + rate limiting before public launch
- Stretch: M3GNet alternatives (CHGNet, ALIGNN) for the phases where M3GNet's intrinsic accuracy floors at ~300 meV (Ti3Al D019, Mg2Si antifluorite)

---

## License & contributing

Not yet decided. The codebase is currently a single-author working repo.

---

## Acknowledgements

- The 4 reference PDFs in `Alloys Design/` (AlloyGPT, GNN+LLM multi-agent, aLLoyM, Skala) provided design inspiration for the canvas-first, AI-native paradigm.
- The Materials Project for providing free access to ~150k DFT-computed structures.
- The matminer team for the Magpie composition featurizer.
- BoTorch for production-grade Bayesian optimisation.
