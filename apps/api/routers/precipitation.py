"""
Sprint 5 — Precipitation kinetics endpoints.

POST /api/precipitation/simulate
GET  /api/precipitation/phases    — list available precipitate phases
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

from apps.api.rate_limit import limiter, LLM_LIMIT, HEAVY_COMPUTE_LIMIT

router = APIRouter()


class PrecipitationRequest(BaseModel):
    composition: dict   # weight percent
    phase:       str    = Field(..., description="Precipitate phase key (see /phases endpoint)")
    aging_T_C:   float  = Field(..., gt=-273.0, le=1500.0,
                                description="Isothermal aging temperature in Celsius.")
    aging_time_s: float = Field(..., gt=0, le=1e8,
                                description="Total aging time in seconds.")


@router.get("/phases")
async def list_phases():
    """List the precipitate phases the KWN model can simulate."""
    from apps.api.ml.precipitation.interfacial_energy import PRECIPITATE_DATA
    return {
        "phases": {
            key: {
                "matrix":      p["matrix"],
                "solute":      p["solute"],
                "morphology":  p["morphology"],
                "gamma_J_m2":  p["gamma_J_m2"],
                "notes":       p.get("notes", ""),
            }
            for key, p in PRECIPITATE_DATA.items()
        }
    }


@router.post("/simulate")
async def simulate(req: PrecipitationRequest):
    """Run the KWN precipitation-kinetics solver.

    Returns the time-resolved vf(t) and r̄(t) trajectory plus final
    (volume_fraction, mean_radius_nm, number_density_per_m3).  Typical
    elapsed time: <100 ms (the inner loop is ~400 timesteps of cheap
    arithmetic).
    """
    try:
        from apps.api.ml.precipitation.kwn import simulate_precipitation
        out = await simulate_precipitation(
            req.composition, req.phase, req.aging_T_C, req.aging_time_s,
        )
        return out
    except Exception as exc:
        raise HTTPException(500, f"KWN simulation failed: {exc}")


class AgingOptimizeRequest(BaseModel):
    composition: dict
    phase:       str    = Field(..., description="Precipitate phase key (see /phases).")
    t_min_C:     Optional[float] = Field(default=None, description="Aging-window min (°C); family default if unset.")
    t_max_C:     Optional[float] = Field(default=None, description="Aging-window max (°C); family default if unset.")
    max_time_h:  Optional[float] = Field(default=None, gt=0, le=2000, description="Max aging time (h); family default if unset.")
    n_temps:     int    = Field(default=6, ge=3, le=10, description="Number of temperatures swept.")


@router.post("/optimize_aging")
@limiter.limit(HEAVY_COMPUTE_LIMIT)
async def optimize_aging_endpoint(request: Request, req: AgingOptimizeRequest):
    """Heat-treatment optimizer: sweep aging T×t through KWN → Orowan Δσ, find
    the peak-age schedule.  Returns a family of Δσ-vs-time curves, the global
    peak (T*, t*), a schedule recommendation, and a plot.

    calibration="literature-correlation" — ranks schedules + shows the peak-age
    trend honestly; absolute Δσ is a screening estimate.  v1: Al/Ni/Ti-base.
    """
    from apps.api.ml.precipitation.aging_optimizer import optimize_aging, family_for_aging
    if family_for_aging(req.composition) is None:
        raise HTTPException(
            422, "Aging optimizer v1 supports precipitation-hardened Al / Ni / Ti "
                 "base alloys.")
    try:
        return optimize_aging(
            req.composition, req.phase,
            t_min_C=req.t_min_C, t_max_C=req.t_max_C,
            max_time_h=req.max_time_h, n_temps=req.n_temps,
        )
    except Exception as exc:
        raise HTTPException(500, f"Aging optimization failed: {exc}")


class PrecipitationInterpretRequest(BaseModel):
    composition:  dict | None = Field(default=None)
    kwn_result:   dict        = Field(..., description="Raw result from /simulate.")
    sim_metadata: dict | None = Field(default=None)


@router.post("/interpret")
@limiter.limit(LLM_LIMIT)
async def interpret(request: Request, req: PrecipitationInterpretRequest):
    """Turn a KWN simulation into a metallurgist-readable interpretation +
    actionable recommendations (aging-curve regime, Δσ_Orowan, etc.).

    Layer-1 numerics (regime classification, peak-age comparison, Orowan
    estimate) are returned in the ``analysis`` block alongside the LLM
    narrative.  Falls back to a deterministic numeric-only path when
    the LLM is unavailable.
    """
    try:
        from apps.api.ml.precipitation.interpret import (
            interpret_precipitation, analyse_precipitation,
        )
        analysis = analyse_precipitation(req.kwn_result, req.composition)
        out = await interpret_precipitation(
            composition=req.composition,
            kwn_result=req.kwn_result,
            analysis=analysis,
            sim_metadata=req.sim_metadata,
        )
        out["analysis"] = analysis
        return out
    except Exception as exc:
        raise HTTPException(500, f"Precipitation interpretation failed: {exc}")
