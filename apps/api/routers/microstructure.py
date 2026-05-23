"""
POST /api/microstructure/simulate     — run a phase-field dendrite simulation
GET  /api/microstructure/health       — quick sanity ping (verifies FiPy import)
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter()


class DendriteRequest(BaseModel):
    composition:         dict[str, float] | None = Field(
        default=None, description="Carried through to metadata; not used by the KWC PDE."
    )
    T_C:                 float | None = Field(
        default=None, description="Composition temperature (°C). Provenance only."
    )
    crystal_symmetry:    int   = Field(default=6, ge=2, le=12,
        description="N-fold symmetry of dendrite tips. 6 = FCC/HCP, 4 = BCC, 3 = trigonal.")
    orientation_deg:     float = Field(default=0.0, ge=-180, le=180,
        description="Crystallographic axis rotation (degrees).")
    undercooling_factor: float = Field(default=1.0, ge=0.3, le=2.5,
        description="Driving-force scaling (proxy for ΔT/ΔT_eq).")
    grid:                int   = Field(default=100, ge=40, le=200,
        description="Square-grid resolution (NxN cells).")
    n_steps:             int   = Field(default=800, ge=100, le=4000,
        description="Total time steps to simulate.")
    n_frames:            int   = Field(default=12, ge=3, le=20,
        description="Snapshots to return.")


@router.get("/health")
async def microstructure_health():
    """Confirm FiPy is importable and the phase-field model can construct a mesh."""
    try:
        import fipy
        return {"status": "ok", "fipy_version": fipy.__version__}
    except Exception as exc:
        raise HTTPException(503, f"FiPy unavailable: {exc}")


@router.post("/simulate")
async def microstructure_simulate(req: DendriteRequest):
    """Run the KWC phase-field dendrite simulator (Sprint 2.5).

    Returns 12 PNG frames plus metadata.  Typical elapsed time: 10–30 s
    depending on grid size and step count.  Results are cached in-process
    by ``(crystal_symmetry, orientation, undercooling, grid, n_steps, n_frames)``.

    Honest framing: the simulation is **schematic** — pure substance,
    2D, no solute coupling, dimensionless time.  Source field reports
    ``"phase_field_kwc"`` and ``calibration: "schematic"``.
    """
    try:
        from apps.api.ml.microstructure.solidification import simulate_dendrite
        return await simulate_dendrite(
            composition=req.composition,
            T_C=req.T_C,
            crystal_symmetry=req.crystal_symmetry,
            orientation_deg=req.orientation_deg,
            undercooling_factor=req.undercooling_factor,
            grid=req.grid,
            n_steps=req.n_steps,
            n_frames=req.n_frames,
        )
    except Exception as exc:
        raise HTTPException(500, f"Phase-field simulation failed: {exc}")
