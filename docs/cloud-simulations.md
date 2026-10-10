# Cloud simulations

Three simulations are too heavy for a web request, so they run as **jobs in isolated
[Daytona](https://www.daytona.io/) sandboxes**:

| Job kind | Tool | What it does | Endpoint |
|---|---|---|---|
| `grain_tessellate` | [Neper](https://neper.info) | Generates a synthetic polycrystal (grain structure) | `POST /api/compute/grain/tessellate` |
| `grain_grow` | [SPPARKS](https://spparks.github.io) | Monte-Carlo (Potts) grain growth | `POST /api/compute/grain/grow` |
| `cpfem_stress_strain` | [DAMASK](https://damask-multiphysics.org) | Crystal-plasticity uniaxial tension: a stress-strain curve | `POST /api/compute/microstructure/stress_strain` |

The tools are run as separate processes inside sandboxes; they are not bundled with, or linked into,
this repository (see [`NOTICE.md`](../NOTICE.md) for their licences).

**Cloud simulations are off unless you configure them.** With no `DAYTONA_API_KEY` the submit
endpoints return `503`, and `GET /api/compute/health` reports `cloud_enabled: false`.

## How a job runs

```
POST …submit  →  orchestrator checks the guardrails  →  job row (status "queued")
              →  sandbox created from a prebuilt snapshot, script started
              →  status "running", polled until the script writes its exit code
              →  artifacts downloaded and parsed  →  result validated  →  "done" | "failed" | "timeout"
              →  sandbox deleted · cost metered · optional completion email
```

Clients poll `GET /api/compute/jobs/{job_id}`; `GET /api/compute/jobs/mine` lists the caller's
recent jobs. Submissions return `429` when a guardrail is hit and `503` when the tier is not
configured. DAMASK is limited to **FCC** compositions (Al, Ni, Cu bases); other crystal structures
are refused with `422` rather than simulated with the wrong physics.

A background reaper runs every five minutes. It times out jobs whose driver has died and deletes any
sandbox no live job references, as a backstop against runaway cost.

## Cost guardrails

These are enforced in the orchestrator regardless of any billing integration:

| Setting | Default | Meaning |
|---|---|---|
| `DAYTONA_MAX_CONCURRENT_JOBS` | `2` | Parallel sandbox cap |
| `DAYTONA_DAILY_BUDGET_USD` | `10.0` | Hard daily spend ceiling |
| `DAYTONA_JOB_WALL_CAP_S` | `900` | Default per-job kill time (15 min) |
| `DAYTONA_GROW_WALL_CAP_S` | `7200` | Kill time for long jobs (SPPARKS, DAMASK): 2 h |
| `DAYTONA_USD_PER_VCPU_HOUR` | `0.1` | Rate used to estimate and meter cost |
| `SPPARKS_MPI_RANKS` | `4` | MPI ranks for SPPARKS |

Full list: [Configuration reference](reference/configuration.md).

## Setting it up

1. Create a Daytona account and put the key in `.env`: `DAYTONA_API_KEY=…`.
2. Build the snapshots once. Each bakes the tool into an image so jobs start in seconds:

   ```bash
   python -m apps.api.compute.snapshots.neper
   python -m apps.api.compute.snapshots.spparks
   python -m apps.api.compute.snapshots.damask
   ```

   Each prints a snapshot name (for example `leilmat-damask-v1`). `--check` lists existing snapshots.
3. Record the names:

   ```
   DAYTONA_SNAPSHOT_NEPER=leilmat-neper-v1
   DAYTONA_SNAPSHOT_SPPARKS=leilmat-spparks-mpi-v3
   DAYTONA_SNAPSHOT_DAMASK=leilmat-damask-v1
   ```

   Neper and SPPARKS can bootstrap themselves at job start if their snapshot is missing; **DAMASK
   cannot** (its environment is too large to install per job), so its snapshot is required.
4. Make sure PostgreSQL is running — jobs are tracked in it.

## Trusting the results: the `calibration` label

Every simulation result is tagged with how far it can be trusted, and the orchestrator **rejects a
result with an unknown tag** before marking the job done, so a new feature cannot quietly overclaim:

| `calibration` | Meaning | Used by |
|---|---|---|
| `deterministic-geometry` | Exact geometry and statistics | Neper |
| `quantitative-characterization` | Exact characterisation of given data | — |
| `qualitative` | Topology and trends only | SPPARKS grain growth |
| `literature-correlation` | Screening using published correlations; absolute values are not fitted to your alloy | DAMASK |
| `validated` | **Forbidden** unless the result is thermally coupled *and* carries an experimentally grounded source | nothing today |

For example, the DAMASK stress-strain curve's *shape*, hardening trend and elastic modulus are
meaningful; its *absolute stress* depends on literature critical resolved shear stresses and is not
validated against your alloy and temper. Results carry explicit `warnings` saying so, and the AI
interpretation is instructed to repeat those limits.
