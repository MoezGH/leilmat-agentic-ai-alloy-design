# Architecture

LeilMat is a FastAPI backend of physics and machine-learning modules behind one API, and a
Next.js front end that composes them on a canvas. Two design rules shape everything:

1. **Every number carries its provenance** — which model produced it (`source`), how uncertain it
   is, and, for simulations, how far it can be trusted (`calibration`).
2. **Refuse rather than extrapolate.** When an input is outside what a model or database can
   answer, the API returns a structured refusal instead of a plausible-looking number.

## Components

```
Next.js 15 (apps/web)        canvas · explorers · simulation cards · AI panel
        │  HTTP + SSE
FastAPI (apps/api)           routers → ml/ modules
        │
        ├─ ml/calphad          pycalphad equilibrium · Scheil · Fe-C TTT   (bundled open TDBs)
        ├─ ml/matgl_models     yield-strength routing + property orchestrator
        │    ├─ ml/ood.py             out-of-domain gates
        │    ├─ ml/calibration.py     conformal intervals
        │    ├─ ml/strengthening.py   physics features (solid solution, precipitation)
        │    └─ ml/temper/            temper vocabulary + encoding
        ├─ ml/m3gnet_predictor formation energy (matgl M3GNet) + Miedema fallback
        ├─ ml/precipitation    KWN precipitation kinetics
        ├─ ml/microstructure   Taichi phase-field dendrite · FiPy · grain tools
        ├─ ml/cost             hierarchical cost model
        ├─ ml/inverse*         BoTorch multi-objective inverse design
        ├─ compute/            Daytona cloud-sandbox jobs (Neper · SPPARKS · DAMASK)
        └─ middleware/ billing/ notify/   optional auth, credits, email
        │
PostgreSQL (jobs; sessions are stubs)     ChromaDB (optional literature retrieval)
```

The repository layout, with the sprint that introduced each module, is in the
[README](../README.md#repo-layout-essential-files).

## Request pipeline

Middleware runs outside-in in this order, so that a rejection still carries CORS headers:

1. **CORS** — allowed origins come from `CORS_ORIGINS` (default: localhost only).
2. **Authentication** — validates a Supabase JWT, but **only on cost-bearing prefixes**:
   `/api/chat/`, `/api/design/`, `/api/phase/scheil`, `/api/phase/interpret`,
   `/api/microstructure/{simulate,interpret}`, `/api/precipitation/{simulate,optimize_aging,interpret}`,
   and the *submit* paths `/api/compute/grain` and `/api/compute/microstructure`. Everything else —
   including `/api/predict`, equilibrium, cost and reports — is open, and so is polling a cloud job
   (`/api/compute/jobs/{id}`; job ids are unguessable UUIDs).
   **If neither `SUPABASE_JWT_SECRET` nor a Supabase URL (`SUPABASE_URL` or `NEXT_PUBLIC_SUPABASE_URL`) is set, enforcement is skipped entirely**
   ("soft mode", logged) so local development works without Supabase.
3. **Credits** — if a billing backend is configured (`LEIL_AGENT_URL`), checks the caller's wallet
   before heavy routes. Flat costs: Scheil 5, precipitation 8, microstructure 15, inverse design 25.
   Cloud jobs are not flat-priced: they are metered by CPU and wall time when they finish. With no
   backend configured the check is skipped.

LLM endpoints are additionally rate-limited (`slowapi`) and counted against a daily
spend budget (`GET /api/health/budget`).

## Yield-strength prediction

`POST /api/predict` calls `predict_properties`, which fans out to the individual property models.
Yield strength is the most elaborate path:

1. **Family routing.** A composition is matched to a model by its dominant element:

   | Family | Rule | Model |
   |---|---|---|
   | Steel, ultra-high-strength | Fe ≥ 50 % | `matbench_steels` (312 alloys), tried first |
   | Steel, general | Fe ≥ 50 % | falls through here when the first model refuses (mild, stainless, PH) |
   | Aluminium | Al ≥ 80 % | per-family model |
   | Titanium | Ti ≥ 50 % | per-family model |
   | Nickel | Ni ≥ 40 % | per-family model |

   Anything else returns `source: "no_match"`.

2. **Features.** 132 Magpie composition descriptors; a temper one-hot plus a strength index
   (`ml/temper/`); and three physics features (`ml/strengthening.py`): Labusch solid-solution
   strengthening, Orowan precipitation strengthening, and their sum. For nickel, the precipitate
   volume fraction is derived from composition (γ′ = Ni₃(Al,Ti,Nb,Ta)) and, when an aging schedule
   is on record (`ml/datasets/aging_schedules.py`), the precipitate radius from Lifshitz-Slyozov-Wagner
   coarsening.

3. **Refusal gates** (see [below](#refusals)), checked before the model runs.

4. **Prediction and interval.** A random-forest ensemble gives the value and a tree-variance
   spread; a **conformal calibrator** turns that into an interval with a stated coverage target of
   **90 %** (`ci_low`, `ci_high`, `coverage`).

5. **Overlays.** Optional grain size (Hall-Petch) and a simulated precipitate state (Orowan) shift
   the result and are reported as differential overlays.

Hardness, fatigue and the other properties derive from yield strength or use closed-form rules
(rule of mixtures, Magpie means, Voigt-Reuss-Hill modulus). Each carries its own `source`.

## Refusals

A refusal looks like `value: null` with a `source` ending in `_out_of_domain` and an
`ood_reason`. They are checked in this order:

| `ood_reason` | Meaning |
|---|---|
| `element_absent` | An element in the input never appears in this family's training alloys. |
| `element_extrapolation` | An element's content is more than **8×** the maximum seen in training for that family. Catches single-element blow-ups that aggregate statistics smear out (a Ti alloy with 20 % Cu scored as in-domain before this check existed). |
| `missing_expected_elements` | The KNN distance is large *because the composition omits an element that almost every training alloy has* (e.g. carbon in steel). `missing_elements` lists them with typical levels. The refusal is protective, not a quirk: dropping C and Si from AISI 316 moves the steel model's output from ~218 MPa to ~831 MPa. |
| `knn_distance` | The composition is far from the training cloud in standardised Magpie space. |

CALPHAD has its own refusal: if no registered database covers the composition, the response says
`No CALPHAD database covers <elements>` (see below).

## CALPHAD routing

`ml/calphad/databases.py` chooses a thermodynamic database for a composition:

1. User or commercial databases (priority ≥ 10) win outright.
2. Otherwise, among bundled databases that **cover** the elements **and are valid** for the
   composition, an exact-match database beats a generalist, and priority breaks ties.
3. If none qualify, the request is refused.

Two details keep this honest. A database is only credited with elements it has parameters for
(declaring an element in the file does not count), enforced by a contract test. And the COST507
light-metal database is excluded for compositions that are mostly Fe, Ni or Co, because it is an
aluminium-alloy assessment. As a result, stainless steels and multicomponent Ni superalloys are
refused until a validated database is added. Details, provenance and licences:
[`models/calphad_tdbs/README.md`](../models/calphad_tdbs/README.md).

## Formation energy

`ml/m3gnet_predictor.py` runs the **M3GNet** graph network (via `matgl`) on a representative
supercell and reports `source: "m3gnet_dft"`. If `matgl` or its weights are unavailable it falls
back to a Miedema-style heuristic and says so (`source: "miedema_heuristic"`) — a response is never
mislabelled. The value is on the DFT (PBE) scale, which over-binds intermetallics relative to
calorimetry. Where the real model ran, an additive `experimental_estimate` is attached: a linear
correction fitted to experimental ΔHf values. Its reference set has not been independently verified;
see [Validation](validation.md#data-quality).

## Cloud simulations

Heavy simulations (Neper, SPPARKS, DAMASK) run in isolated Daytona sandboxes and are tracked as
jobs in PostgreSQL. See [Cloud simulations](cloud-simulations.md).

## Frontend

The canvas keeps its state in a Zustand store. Simulation cards persist results to the store so a
reload does not re-run paid simulations. The AI panel can trigger actions, but only from an
**allow-list with bounded parameters** (`apps/web/lib/ai/actions.ts`), so a hallucinated value cannot
launch an expensive job.

## Persistence

PostgreSQL (with the pgvector image) stores cloud-job records. The design-session endpoints
(`/api/design/session`) are stubs and persist nothing yet. ChromaDB holds the optional literature
index used by the chat panel; no papers ship with the repository.
