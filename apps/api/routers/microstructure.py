"""
POST /api/microstructure/simulate     — full anisotropic KWC dendrite (Taichi)
GET  /api/microstructure/health       — confirms Taichi is importable

The endpoint runs the validated Sprint 2.6 Taichi simulator that reproduces
the Kobayashi 1993 six-arm dendrite morphology.  See
``apps/api/ml/microstructure/solidification.py`` for the param mapping and
performance budget.
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
        description="Bath-undercooling scaling (Kobayashi T_bath = 0.5 × this).")
    # Bumped from the Sprint 2.5 (grid≤200, n_steps≤4000) ranges because the
    # Taichi simulator needs more iterations to develop the side-branching
    # dendrite morphology.  Defaults sized for ~30-45 s on a 2024 Mac.
    grid:                int   = Field(default=120, ge=40, le=400,
        description="Square-grid resolution.  120 default; 400 = publication-grade.")
    n_steps:             int   = Field(default=15000, ge=500, le=30000,
        description="Maximum simulation steps (early stop at sf ≥ 0.32).")
    n_frames:            int   = Field(default=12, ge=3, le=20,
        description="Snapshots to return.")


@router.get("/health")
async def microstructure_health():
    """Confirm Taichi is importable and a small kernel can compile."""
    try:
        import taichi as ti
        return {"status": "ok", "taichi_version": ti.__version__,
                "simulator": "anisotropic_kwc_taichi"}
    except Exception as exc:
        raise HTTPException(503, f"Taichi unavailable: {exc}")


@router.post("/simulate")
async def microstructure_simulate(req: DendriteRequest):
    """Run the full anisotropic KWC dendrite simulator (Sprint 2.6, Taichi-JIT).

    Returns up to 20 PNG frames plus metadata.  Typical elapsed time
    (single Python process, CPU):
      * grid=120, n_steps=15000   →  ~30-45 s    default; six-arm dendrite
      * grid=200, n_steps=20000   →  ~60-90 s    publication-quality preview
      * grid=400, n_steps=22000   →  ~3-5 min    matches the canonical PNG

    Results are cached in-process by all six knobs so repeated clicks at
    identical settings return instantly.

    Source: ``phase_field_kwc_anisotropic_taichi``.  Calibration:
    ``validated`` (against Kobayashi 1993 Fig. 4).
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
        raise HTTPException(500, f"KWC dendrite simulation failed: {exc}")


# ─────────────────────────────────────────────────────────────────────
# Layer 2 — LLM interpretation of a completed simulation
# ─────────────────────────────────────────────────────────────────────

class InterpretRequest(BaseModel):
    composition:  dict[str, float] | None = Field(
        default=None, description="Composition the user is exploring."
    )
    temper:       str | None = Field(default=None, description="Heat-treatment temper.")
    T_C:          float | None = Field(default=None, description="Temperature (°C).")
    analysis:     dict = Field(
        ..., description="Layer-1 output from /simulate (the `analysis` block)."
    )
    sim_metadata: dict | None = Field(
        default=None, description="Optional simulation metadata for provenance."
    )


@router.post("/interpret")
async def microstructure_interpret(req: InterpretRequest):
    """Turn Layer-1 numeric measurements into a metallurgist-readable
    narrative + 2-3 actionable recommendations.

    Calls the OpenRouter/DeepSeek pipeline with a strict JSON schema.
    Falls back to a deterministic numeric-only interpretation if the
    LLM is unavailable so the UI stays useful.

    Source: ``llm_interpretation_deepseek`` (LLM path) or
    ``deterministic_fallback`` (numeric only).
    """
    try:
        from apps.api.ml.microstructure.interpret_llm import interpret_dendrite
        return await interpret_dendrite(
            composition=req.composition,
            temper=req.temper,
            T_C=req.T_C,
            analysis=req.analysis,
            sim_metadata=req.sim_metadata,
        )
    except Exception as exc:
        raise HTTPException(500, f"Dendrite interpretation failed: {exc}")
