"""
1-D diffusion mini-simulator endpoints.

``GET /api/diffusion/systems`` — catalogue of solute-matrix pairs the
solver knows about (D₀ / Q from literature), keyed for the frontend
dropdown.

``POST /api/diffusion/simulate`` — run a Crank-Nicolson diffusion-
couple solve at the requested T and return the full time-resolved
``c(x, t)`` for animation in the frontend playback scrubber.

Rate-limited at the heavy-compute tier (4 / min / IP).  Crank-Nicolson
on 101 × 400 grid completes in ~20 ms on a CX23 box, so the limit is
defensive against scripted abuse rather than reflective of real cost.
"""
import logging

from fastapi          import APIRouter, Body, Request
from pydantic         import BaseModel, Field

from apps.api.ml.diffusion.solver import list_systems, simulate_diffusion_curve
from apps.api.rate_limit          import limiter, HEAVY_COMPUTE_LIMIT


logger = logging.getLogger(__name__)
router = APIRouter()


class DiffusionRequest(BaseModel):
    system:       str   = Field(..., description="Key from /api/diffusion/systems")
    T_C:          float = Field(..., gt=-273.15, lt=2000)
    L_um:         float = Field(default=200.0, gt=0.1, lt=10_000)
    c_left:       float = Field(default=5.0,   ge=0.0, le=100.0)
    c_right:      float = Field(default=0.0,   ge=0.0, le=100.0)
    total_time_s: float = Field(default=14_400.0, gt=0.0, lt=1e8)


@router.get("/systems")
async def systems():
    """Solute-matrix catalogue with literature D₀ / Q references."""
    return {"systems": list_systems()}


@router.post("/simulate")
@limiter.limit(HEAVY_COMPUTE_LIMIT)
async def simulate(
    request: Request,
    req:     DiffusionRequest = Body(...),
):
    """Run a 1-D diffusion couple and return the c(x, t) trajectory."""
    try:
        result = simulate_diffusion_curve(
            system       = req.system,
            T_C          = req.T_C,
            L_um         = req.L_um,
            c_left       = req.c_left,
            c_right      = req.c_right,
            total_time_s = req.total_time_s,
        )
    except Exception as exc:                                          # noqa: BLE001
        logger.exception("Diffusion simulate failed: %s", exc)
        return {"error": str(exc), "source": "fick_1d_crank_nicolson"}
    return result
