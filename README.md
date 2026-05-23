# LeilMat

**AI-native alloy design canvas** — predict properties, run Bayesian inverse design, score manufacturability, and explore composition spaces with a conversational AI copilot.

Live at **leil.xyz** (planned). Built for the STEM community: materials engineers, researchers, and product designers who want fast, scientifically defensible answers to "what alloy should I use?"

---

## What it does

| Feature | What it gives you |
|---|---|
| **Property prediction** | Composition → density, melting point, yield strength, formation energy, electronegativity, valence — each with `{value, uncertainty, source}` provenance |
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
└──┬───────────────┬───────────────┬────────────────┬────────────┘
   │               │               │                │
   ▼               ▼               ▼                ▼
matminer        BoTorch         pymatgen +        OpenRouter
+ sklearn       (qEHVI GP)      Materials         → DeepSeek
(Magpie         multi-obj.      Project API       V4 Pro
+ ROM           inverse         (real DFT data)   (reasoning
+ RF on         design)                           disabled)
matbench)

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
│   │   ├── main.py                app entry + CORS + lifespan
│   │   ├── config.py              env-driven settings
│   │   ├── routers/
│   │   │   ├── predict.py         POST /api/predict + /batch
│   │   │   ├── design.py          POST /api/design/inverse
│   │   │   ├── phase.py           GET /api/phase/diagram (MP API)
│   │   │   └── chat.py            Local/Global/Scan SSE streaming
│   │   ├── ml/
│   │   │   ├── featurizers.py     Magpie + rule-of-mixtures
│   │   │   ├── matgl_models.py    predict_properties orchestrator
│   │   │   ├── inverse.py         BoTorch qEHVI + random fallback
│   │   │   ├── manufacturability.py  Castability + Weldability + Cost
│   │   │   └── training.py        RF training on matbench_steels
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
| Yield strength | Random Forest trained on `matbench_steels` (312 alloys, 132 Magpie features) — gated to Fe ≥ 50 at% | `RF/Steels` (violet) | CV MAE 110 MPa over 400-2500 MPa range |
| Formation E | Miedema-inspired heuristic ΔH_f ≈ -0.4(Δχ)² + 0.05·ḠS | `Miedema` (amber) | ~30 % (placeholder) |
| Electronegativity / Valence | Magpie composition-weighted means | `Magpie` | descriptor, not approximation |
| **Phase Diagram** | Live query of Materials Project REST API → `pymatgen.analysis.phase_diagram.PhaseDiagram` convex hull | (real DFT data) | DFT-grade |
| **Castability** | Tm-based base + Al-Si / Fe-C / Zn-Al eutectic boosts + reactive-element penalties (ASM Handbook v.15) | heuristic | qualitative |
| **Weldability** | IIW Carbon Equivalent (Yurioka, ISIJ Int. 2001) for Fe alloys; Cu/Mg/Zn penalty rules for Al alloys; specialty flags for Ti, Cu | rule-based | industry-standard for steels |
| **Cost** | Mass-weighted spot prices (USD/kg, LME / USGS Mineral Commodity Summaries 2025) on log scale | `spot_prices_2025` | indicative |

### Verification scorecard

| Alloy | Real ρ | Predicted ρ | Real T_m | Predicted T_m |
|---|---|---|---|---|
| Pure Al | 2.70 | **2.70** | 933 K | **933 K** |
| Pure Fe | 7.87 | **7.87** | 1811 K | **1811 K** |
| AISI 304 (Fe-18Cr-8Ni) | 7.93 | 7.82 (-1.4 %) | ~1727 K | 1871 K (+8 %) |
| Al-4Cu | 2.78 | 2.88 (+3.6 %) | 929 K | 950 K (+2.3 %) |

Manufacturability scores on canonical alloys:

| Alloy | Cast | Weld | Cost | Overall | Engineering opinion |
|---|---|---|---|---|---|
| A356 cast Al | 100 | 90 | 91 | **93.5** | textbook castable |
| C36000 brass | 84 | 75 | 82 | **80.1** | classic free-machining |
| AISI 4140 | 44 | 75 | 100 | **72.9** | CE = 0.509, preheat zone |
| Ti-6Al-4V | 10 | 35 | 77 | **40.9** | reactive + inert-gas welding |
| Pt-10Rh | 32 | 65 | 0 | **32.3** | exotic, $44k/kg |

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
| ML — training | **scikit-learn** Random Forest | Bundled tree-variance uncertainty, fast inference |
| ML — inverse design | **BoTorch** + **GPyTorch** (qEHVI + GP surrogates) | State of the art multi-objective Bayesian optimisation |
| Materials DB | **mp-api** + **pymatgen** | First-party Materials Project client, DFT convex hulls |
| Infra | **Docker Compose** (PostgreSQL/pgvector + ChromaDB) | Reproducible local dev |

---

## API reference (brief)

| Endpoint | Description |
|---|---|
| `POST /api/predict` | Single composition → all properties + manufacturability |
| `POST /api/predict/batch` | List of compositions (max 500) → list of results |
| `POST /api/design/inverse` | BoTorch qEHVI run; returns ranked Pareto + dominated candidates |
| `GET /api/phase/diagram?elements=Al,Mg,Si` | Materials Project DFT convex hull |
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

- **Yield strength** is gated to Fe ≥ 50 at% (training set is steels only); non-ferrous predictions return null with an explanation.
- **Formation energy** still uses a Miedema-style heuristic (~30 % error) — real DFT would need M3GNet/CHGNet inference, which is installed but not wired yet.
- **Inverse design** assumes the predictor is well-calibrated. With density (ROM) and melting point (Magpie) as objectives, BoTorch finds real Pareto fronts; with the heuristic formation energy as an objective, results are less trustworthy.
- **Cost scores** use 2025 spot prices; they're indicative only — real procurement involves form factor, purity, and supplier.
- **Phase Diagram** depends on MP API availability and the user's API key quota.
- **Reference PDFs** in `/Alloys Design/` are inspiration only — they are NOT used to train, ground, or cite the AI.

---

## Roadmap

See [ROADMAP.md](ROADMAP.md). The original 4 phases are complete. Manufacturability scoring was added as a bonus phase.

Possible future work:
- M3GNet/CHGNet integration for DFT-grade formation energy
- Non-ferrous yield-strength models (Al, Ti, Ni datasets)
- Session persistence + share links
- Periodic table picker grouped views (lightweight, refractory, precious)
- PDF report export

---

## License & contributing

Not yet decided. The codebase is currently a single-author working repo.

---

## Acknowledgements

- The 4 reference PDFs in `Alloys Design/` (AlloyGPT, GNN+LLM multi-agent, aLLoyM, Skala) provided design inspiration for the canvas-first, AI-native paradigm.
- The Materials Project for providing free access to ~150k DFT-computed structures.
- The matminer team for the Magpie composition featurizer.
- BoTorch for production-grade Bayesian optimisation.
