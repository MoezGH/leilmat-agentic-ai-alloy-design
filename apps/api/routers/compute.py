"""Async cloud-compute endpoints (Daytona-backed heavy simulations).

  POST /api/compute/grain/tessellate  — submit a Neper polycrystal job → {job_id}
  GET  /api/compute/jobs/{job_id}     — poll job status + result
  GET  /api/compute/health            — is the cloud tier enabled?

Submit returns immediately with a ``job_id``; the frontend polls the job
endpoint until ``status`` is ``done`` / ``failed`` / ``timeout``.  When
``DAYTONA_API_KEY`` is unset the whole tier is dark and submit returns 503.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from apps.api.config import settings
from apps.api.rate_limit import limiter, HEAVY_COMPUTE_LIMIT, LLM_LIMIT

router = APIRouter()

_VALID_MORPHO = {"voronoi", "graingrowth", "gg"}


class GrainTessellateRequest(BaseModel):
    n_grains: int = Field(default=100, ge=8, le=2000,
        description="Number of grains in the synthetic polycrystal.")
    morpho: str = Field(default="voronoi",
        description="Tessellation morphology: 'voronoi' (fast) or 'graingrowth'.")
    domain_um: float | None = Field(default=None, gt=0, le=1e5,
        description="Optional physical cube edge length (µm). When given, "
                    "results include absolute grain size + ASTM number; "
                    "otherwise sizes are dimensionless (unit-cube edge).")


@router.get("/health")
async def compute_health():
    """Report whether the cloud-compute tier is enabled (key configured)."""
    from apps.api.compute.runner import get_runner
    return {
        "status": "ok",
        "cloud_enabled": get_runner() is not None,
        "snapshot_configured": bool(settings.daytona_snapshot_neper),
    }


@router.post("/grain/tessellate")
@limiter.limit(HEAVY_COMPUTE_LIMIT)
async def grain_tessellate(request: Request, req: GrainTessellateRequest):
    """Submit a Neper synthetic-polycrystal generation job.

    Ships ``calibration="deterministic-geometry"`` — Neper is a geometry
    engine, so cell counts and the normalized size distribution are exact;
    absolute µm sizes/ASTM appear only when ``domain_um`` is supplied.
    """
    if req.morpho.lower() not in _VALID_MORPHO:
        raise HTTPException(400, f"morpho must be one of {sorted(_VALID_MORPHO)}")

    from apps.api.ml.microstructure.grain_tessellation import make_tessellation_job
    from apps.api.compute.orchestrator import (
        submit_job, CloudDisabledError, CapExceeded,
    )

    params = req.model_dump()
    body, artifacts, parse = make_tessellation_job(params)
    try:
        job = await submit_job(
            kind="grain_tessellate",
            params=params,
            user_id=getattr(request.state, "user_id", None),
            user_email=getattr(request.state, "user_email", None),
            body=body,
            artifacts=artifacts,
            parse=parse,
            snapshot=settings.daytona_snapshot_neper or None,
            est_cost_usd=0.05,
        )
    except CloudDisabledError as exc:
        raise HTTPException(503, str(exc))
    except CapExceeded as exc:
        raise HTTPException(429, exc.detail)
    except Exception as exc:
        raise HTTPException(500, f"Failed to submit grain job: {exc}")
    return {"job_id": job.id, "status": job.status}


class GrainGrowRequest(BaseModel):
    grid: int = Field(default=32, ge=16, le=64,
        description="3D lattice edge (grid^3 sites). Bigger = longer run (64³ ≈ 1.5 h).")
    sweeps: int = Field(default=150, ge=50, le=2000,
        description="Monte-Carlo sweeps — more = more coarsening. NOT physical time.")
    domain_um: float | None = Field(default=None, gt=0, le=1e5,
        description="Optional physical cube edge (µm) for indicative grain size. "
                    "The coarsening STATE stays uncalibrated regardless.")


@router.post("/grain/grow")
@limiter.limit(HEAVY_COMPUTE_LIMIT)
async def grain_grow(request: Request, req: GrainGrowRequest):
    """Submit a SPPARKS Monte-Carlo Potts grain-GROWTH job.

    Ships ``calibration="qualitative"`` — this simulates grains coarsening over
    Monte-Carlo time. MC sweeps are not physical seconds and the lattice is
    dimensionless, so it reports statistical morphology, grain count and size-
    distribution shape — never a physical anneal time or calibrated µm/ASTM.
    """
    from apps.api.ml.microstructure.grain_growth import make_grain_growth_job
    from apps.api.compute.orchestrator import (
        submit_job, CloudDisabledError, CapExceeded,
    )

    params = req.model_dump()
    body, artifacts, parse = make_grain_growth_job(params)
    try:
        job = await submit_job(
            kind="grain_grow",
            params=params,
            user_id=getattr(request.state, "user_id", None),
            user_email=getattr(request.state, "user_email", None),
            body=body,
            artifacts=artifacts,
            parse=parse,
            # Launch from the pre-baked SPPARKS snapshot (fast start); the job
            # body self-bootstraps SPPARKS if the snapshot is unset/unavailable.
            snapshot=settings.daytona_snapshot_spparks or None,
            est_cost_usd=0.10,
            # A legitimately long Monte-Carlo run — give it the 45-min cap.
            wall_cap_s=settings.daytona_grow_wall_cap_s,
        )
    except CloudDisabledError as exc:
        raise HTTPException(503, str(exc))
    except CapExceeded as exc:
        raise HTTPException(429, exc.detail)
    except Exception as exc:
        raise HTTPException(500, f"Failed to submit grain-growth job: {exc}")
    return {"job_id": job.id, "status": job.status}


class GrainInterpretRequest(BaseModel):
    kind: str = Field(description="'grain_grow' (Potts) or 'grain_tessellate' (Neper).")
    result: dict = Field(description="The parsed sim result block to interpret.")
    composition: dict[str, float] | None = Field(
        default=None, description="Optional alloy composition (wt %) for context.")


@router.post("/grain/interpret")
@limiter.limit(LLM_LIMIT)
async def grain_interpret(request: Request, req: GrainInterpretRequest):
    """Post-simulation 'local AI' analysis of a grain result.

    Returns the shared interpretation envelope ``{interpretation, regime_call,
    recommendations, honest_limitations, source, calibration}`` whose
    ``recommendations[].executable`` blocks drive the frontend action pills.
    Routes through the daily LLM budget gate; serves a deterministic fallback
    when the key/budget is unavailable.  Honesty contract is baked into the
    prompts (Potts = no physical time; Neper = geometry/stats, not physics).
    """
    from apps.api.ml.microstructure.interpret_grains import (
        interpret_grain_growth, interpret_grain_structure, interpret_stress_strain,
    )

    kind = (req.kind or "").strip()
    if kind == "grain_grow":
        return await interpret_grain_growth(req.composition, req.result)
    if kind in ("grain_tessellate", "grain_structure"):
        return await interpret_grain_structure(req.composition, req.result)
    if kind in ("cpfem_stress_strain", "stress_strain"):
        return await interpret_stress_strain(req.composition, req.result)
    raise HTTPException(400, "kind must be 'grain_grow', 'grain_tessellate', or 'cpfem_stress_strain'")


class StressStrainRequest(BaseModel):
    composition: dict[str, float] = Field(
        description="Alloy composition (wt %). Determines the crystal family.")
    cells: int = Field(default=16, ge=8, le=32,
        description="RVE edge in voxels (cells³). Bigger = longer solve.")
    n_grains: int = Field(default=20, ge=4, le=64,
        description="Number of grains in the synthetic Voronoi RVE.")
    max_strain: float = Field(default=0.02, gt=0.004, le=0.10,
        description="Total uniaxial engineering strain.")
    n_increments: int = Field(default=30, ge=10, le=60,
        description="Load increments — more = finer flow curve.")
    seeds: list[list[float]] | None = Field(default=None,
        description="Optional Voronoi seed coords (unit cube) from a Neper grain "
                    "structure — rebuilds that exact RVE instead of a random one.")


@router.post("/microstructure/stress_strain")
@limiter.limit(HEAVY_COMPUTE_LIMIT)
async def cpfem_stress_strain(request: Request, req: StressStrainRequest):
    """Submit a DAMASK crystal-plasticity (CPFEM) uniaxial-tension job.

    Generates a synthetic Voronoi polycrystal RVE, deforms it with a
    phenomenological power-law crystal-plasticity phase (literature slip
    parameters), and returns the homogenized stress-strain flow curve.

    Ships ``calibration="literature-correlation"`` — the flow-curve shape and
    hardening trend are physical, but the absolute stress is literature-
    parametrized (CRSS not fit to the exact alloy), so it's a screening
    estimate, not a validated curve.  v1 supports FCC alloys (Al/Ni/Cu base).
    """
    from apps.api.ml.microstructure.cpfem import family_for_composition, make_cpfem_job
    from apps.api.compute.orchestrator import (
        submit_job, CloudDisabledError, CapExceeded,
    )

    if family_for_composition(req.composition) != "fcc":
        raise HTTPException(
            422,
            "CPFEM stress-strain v1 supports FCC alloys (Al / Ni / Cu base). "
            "BCC (steel) and HCP (Ti) crystal-plasticity models are coming soon.",
        )

    params = req.model_dump()
    body, artifacts, parse = make_cpfem_job(params)
    try:
        job = await submit_job(
            kind="cpfem_stress_strain",
            params=params,
            user_id=getattr(request.state, "user_id", None),
            user_email=getattr(request.state, "user_email", None),
            body=body,
            artifacts=artifacts,
            parse=parse,
            snapshot=settings.daytona_snapshot_damask or None,
            est_cost_usd=0.20,
            # A legitimately long FFT crystal-plasticity solve — 2 h cap.
            wall_cap_s=settings.daytona_grow_wall_cap_s,
        )
    except CloudDisabledError as exc:
        raise HTTPException(503, str(exc))
    except CapExceeded as exc:
        raise HTTPException(429, exc.detail)
    except Exception as exc:
        raise HTTPException(500, f"Failed to submit CPFEM job: {exc}")
    return {"job_id": job.id, "status": job.status}


@router.get("/jobs/mine")
async def my_compute_jobs(request: Request):
    """The caller's recent jobs (running + finished, newest first) — powers the
    header Jobs tray and the on-load re-attach so a long job survives a reload."""
    from apps.api.compute.jobs import list_recent_jobs
    uid = getattr(request.state, "user_id", None)
    if not uid:
        return {"jobs": []}   # never leak other users' jobs to an anonymous caller
    rows = await list_recent_jobs(uid, limit=20)
    return {"jobs": [r.to_public_dict() for r in rows]}


@router.get("/jobs/{job_id}")
async def get_compute_job(request: Request, job_id: str):
    """Poll a compute job.  Frontend calls this every few seconds."""
    from apps.api.compute.jobs import get_job
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    # Soft ownership check: when both sides are authenticated, a job may
    # only be read by its owner.  (Job ids are unguessable uuids anyway.)
    uid = getattr(request.state, "user_id", None)
    if job.user_id and uid and job.user_id != uid:
        raise HTTPException(403, "not your job")
    return job.to_public_dict()
