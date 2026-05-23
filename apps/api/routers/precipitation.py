"""
Sprint 5 — Precipitation kinetics endpoints.

POST /api/precipitation/simulate
GET  /api/precipitation/phases    — list available precipitate phases
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

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
