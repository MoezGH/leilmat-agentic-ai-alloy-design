# Getting started

This page takes you from a fresh clone to a running API and web app. Every command here was run
against the code before it was written down.

## What you need

| | Required for | Notes |
|---|---|---|
| Python **3.11 or 3.12** | everything | The Docker image uses 3.11; the test suite is run on 3.12. |
| Node **22** | the web app only | The web image uses `node:22-alpine`. |
| Docker + Compose | optional | Only for the containerised stack (below). |
| PostgreSQL, ChromaDB | **optional** | The API starts without them; see [what works without what](#what-works-without-what). |

## 1. Install

```bash
git clone https://github.com/MoezGH/leilmat-agentic-ai-alloy-design.git
cd leilmat-agentic-ai-alloy-design
python3 -m venv .venv && source .venv/bin/activate
pip install -r apps/api/requirements.txt
```

The first install is large (it includes PyTorch and `matgl`). `matgl` supplies the M3GNet
formation-energy model; if it is missing the rest of the stack still works and formation energy
falls back to a Miedema heuristic, reported honestly in the response (`source: "miedema_heuristic"`).

## 2. Train the models (one time)

```bash
python -m apps.api.ml.training
```

This fits the yield-strength models: the matbench steels model plus the aluminium, titanium,
nickel and general-steel families. It takes a few minutes and downloads the matbench dataset
through `matminer`, so it needs network access. To retrain one family only:
`python -m apps.api.ml.training nickel` (also `aluminum`, `titanium`, `general_steel`, `steels`).

> **Why you must do this.** Trained models are *not* stored in git: they are Python pickles, and
> loading a pickle executes code. Until you train, yield-strength predictions return
> `"model file missing — run training first"`.

## 3. Try it without a server

```bash
python scripts/demo_6061_t6.py
```

This walks one alloy (6061-T6) through CALPHAD, precipitation, yield strength, cost and inverse
design, printing a narrated trace in a few seconds. Add `--include-slow` for Scheil and the
microstructure simulation (5–15 minutes) or `--json` for machine-readable output.

## 4. Run the API

```bash
uvicorn apps.api.main:app --reload --port 8000
```

- Endpoint list: [docs/reference/api.md](reference/api.md). The interactive Swagger page is switched off in `apps/api/main.py`; the comment there says how to enable it for local work.
- Liveness: `GET /health` (no dependencies) and `GET /api/health`

Make a prediction. **`composition` is in atomic percent** (it is normalised, so any scale that
sums consistently works):

```bash
curl -s localhost:8000/api/predict -H 'content-type: application/json' -d '{
  "composition": {"Al": 98.09, "Mg": 1.11, "Si": 0.58, "Cu": 0.12, "Cr": 0.10},
  "temper": "T6"
}'
```

That is 6061 converted from weight to atomic percent. If you have weight percent, convert it first
with `apps.api.ml.alloy_datasets.weight_to_atomic`. Passing weight percent as-is is accepted but is
then *read* as atomic percent: for 6061 the difference is about 5 MPa, and it grows for mixes of
heavy and light elements.

The response has flat values under `properties`, and the provenance of each under
`properties._details`:

```jsonc
"yield_strength_MPa": 273.0,                        // flat value
"_details": {
  "yield_strength_MPa": {
    "value": 273.0, "source": "rf_aluminum",
    "uncertainty": 44.0, "ci_low": 229.0, "ci_high": 316.0,   // conformal interval
    "coverage": 0.9, "ood_ratio": 0.06, "temper_used": "T6"
  },
  "formation_energy_eV_per_atom": { "source": "m3gnet_dft", ... }
}
```

(Literature value for 6061-T6 is about 276 MPa.) When an input is outside what a model can
answer, you get a **refusal, not a number**:

```jsonc
"yield_strength_MPa": null,
"_details": { "yield_strength_MPa": {
  "value": null, "source": "rf_general_steel_out_of_domain",
  "ood_reason": "missing_expected_elements", "missing_elements": {"C": 0.18, "Si": 0.45},
  "error": "Composition is outside the training domain ... omits Si, C ..." } }
```

See [Architecture](architecture.md#refusals) for every refusal reason.

## 5. Run the web app

```bash
cd apps/web
npm install
npm run dev          # http://localhost:4000/canvas
```

It talks to the API at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

## 6. Or use Docker

```bash
cp .env.example .env
python -m apps.api.ml.training      # train on the host first — see the note below
docker compose up --build
```

| Service | URL |
|---|---|
| API | <http://localhost:8000> |
| Web | <http://localhost:3000> (the Docker web service; `npm run dev` uses 4000) |
| PostgreSQL | `localhost:5432` (development credentials) |
| ChromaDB | `localhost:8001` |

> **Models and Docker.** The image build does not train models. The compose file mounts the
> repository into the API container (`.:/app`), so models trained on the host are visible inside
> it. You can also train inside the container: `docker compose run --rm api python -m apps.api.ml.training`.
>
> **The development credentials** (`leilmat` / `leilmat`) are for local use only — see
> [Deployment](deployment.md#security-checklist) before exposing anything.

## What works without what

| You have | You get |
|---|---|
| Nothing but Python deps + trained models | CALPHAD equilibrium, Scheil, TTT, precipitation, yield strength, cost, inverse design, reports |
| + `matgl` installed | M3GNet formation energy (otherwise Miedema fallback) |
| + PostgreSQL | **Required for cloud simulations** (jobs are tracked in the database). Core predictions don't need it: without it the API logs `DB init skipped` and carries on. Session storage endpoints are stubs today. |
| + `OPENROUTER_API_KEY` | The AI chat panels, and LLM-written narrative in simulation interpretations. Without it chat reports that no key is configured and interpretations fall back to a deterministic numeric summary; nothing else is affected. |
| + `MP_API_KEY` | Live Materials Project lookups (phase-diagram explorer, formation-energy stress tests) |
| + ChromaDB | Literature retrieval for chat. Retrieval is skipped quickly when it is unreachable. |
| + `DAYTONA_API_KEY` + snapshots | [Cloud simulations](cloud-simulations.md) |
| + Supabase variables | User authentication. **Without them the API is open.** |

All settings: [Configuration reference](reference/configuration.md).

## Tests and the scorecard

```bash
python -m pytest apps/api -q          # about 3 minutes; a few M3GNet tests skip without matgl
python -m apps.api.ml.eval.unified_scorecard     # regenerate docs/SCORECARD.md
```

See [Validation](validation.md) for what the scorecard measures and how to extend it.

## Troubleshooting

| You see | It means | Do this |
|---|---|---|
| `model file missing — run training first` | No trained model for that family | `python -m apps.api.ml.training` |
| `value: null`, `source: …_out_of_domain` | A deliberate refusal, not an error | Read `ood_reason` and `error`; add any missing trace elements it lists |
| `No CALPHAD database covers CR-FE-NI` | No bundled open database models that system (stainless steels, multicomponent Ni superalloys) | Add a validated TDB — see [`models/calphad_tdbs/README.md`](../models/calphad_tdbs/README.md) |
| Formation energy `source: "miedema_heuristic"` | `matgl` or its weights are unavailable | `pip install matgl`, or accept the heuristic |
| `503` from `/api/compute/*` | Cloud simulations are not configured | See [Cloud simulations](cloud-simulations.md) |
| `[startup] DB init skipped` | PostgreSQL is unreachable | Fine for core predictions; start the database before using cloud simulations |
