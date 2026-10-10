"""
POST /api/predict
Forward prediction: composition → properties.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

router = APIRouter()


class PredictRequest(BaseModel):
    composition: dict[str, float]    # {"Al": 90.0, "Mg": 5.0, "Si": 5.0}
    # Sprint 4: temper as a model input.  ``None`` → family-default
    # (T6 for Al, STA for Ti, Aged for Ni, Annealed for steel).
    temper: str | None = None
    # Optional physical mean grain size (µm) from a Neper/SPPARKS sim that was
    # given a domain_um.  When present, a differential Hall-Petch overlay
    # shifts yield strength (and the hardness/fatigue derived from it).  When
    # None, prediction is unchanged — dimensionless sims never set this.
    grain_size_um: float | None = None
    # Optional precipitate state {vf, r_nm} from a KWN sim. When present, a
    # differential Orowan overlay shifts yield strength to reflect the actual
    # aging schedule (vs the canonical temper the baseline assumes). None →
    # prediction unchanged.
    precipitate_state: dict[str, float] | None = None
    session_id: str | None = None

    @field_validator("grain_size_um")
    @classmethod
    def check_grain_size(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("grain_size_um must be positive")
        return v

    @field_validator("precipitate_state")
    @classmethod
    def check_precip(cls, v: dict | None) -> dict | None:
        if v is None:
            return None
        vf = v.get("vf")
        r_nm = v.get("r_nm")
        if not isinstance(vf, (int, float)) or not isinstance(r_nm, (int, float)):
            return None                          # ignore malformed → no overlay
        if not (0 < vf <= 1) or r_nm <= 0:
            return None                          # non-physical → no overlay
        return {"vf": float(vf), "r_nm": float(r_nm)}

    @field_validator("composition")
    @classmethod
    def check_composition(cls, v: dict[str, float]) -> dict[str, float]:
        if not v:
            raise ValueError("composition must not be empty")
        if len(v) > 12:
            raise ValueError("maximum 12 elements supported")
        if any(f < 0 for f in v.values()):
            raise ValueError("fractions must be non-negative")
        return v


class PredictResponse(BaseModel):
    composition: dict[str, float]
    properties: dict
    source: str = "ml_prediction"


@router.post("", response_model=PredictResponse)
async def predict(req: PredictRequest):
    """Predict material properties for a composition: yield strength with a conformal interval, density, melting point, formation energy, hardness, fatigue, corrosion, elastic modulus and manufacturability. Each value carries its source and uncertainty; out-of-domain compositions are refused rather than extrapolated."""
    try:
        from apps.api.ml.matgl_models import predict_properties
        props = predict_properties(req.composition, temper=req.temper,
                                   grain_size_um=req.grain_size_um,
                                   precipitate_state=req.precipitate_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return PredictResponse(composition=req.composition, properties=props)


# ── Temper vocabulary endpoint (Sprint 4) ────────────────────────

@router.get("/tempers")
async def list_tempers(family: str | None = None):
    """List canonical tempers for a family, or all families if none given.

    The frontend uses this to populate the temper dropdown — the available
    options depend on the detected alloy family (Al-T6 vs Steel-Q&T etc.).
    """
    from apps.api.ml.temper.encoding import (
        TEMPER_VOCABULARY, DEFAULT_TEMPER,
    )
    if family is None:
        return {
            "families": {
                f: {
                    "default": DEFAULT_TEMPER[f],
                    "options": list(TEMPER_VOCABULARY[f]),
                }
                for f in TEMPER_VOCABULARY
            }
        }
    if family not in TEMPER_VOCABULARY:
        raise HTTPException(404, f"Unknown family: {family}.  Valid: {list(TEMPER_VOCABULARY)}")
    return {
        "family": family,
        "default": DEFAULT_TEMPER[family],
        "options": list(TEMPER_VOCABULARY[family]),
    }


# ── Batch prediction ──────────────────────────────────────────────

class BatchPredictRequest(BaseModel):
    compositions: list[dict[str, float]]

    @field_validator("compositions")
    @classmethod
    def check_compositions(cls, v: list[dict[str, float]]) -> list[dict[str, float]]:
        if not v:
            raise ValueError("compositions must not be empty")
        if len(v) > 500:
            raise ValueError("max 500 compositions per batch")
        return v


class BatchPredictResponse(BaseModel):
    results: list[dict]


@router.post("/batch", response_model=BatchPredictResponse)
async def predict_batch(req: BatchPredictRequest):
    """
    Predict properties for many compositions in one call.
    Used by the Ternary Explorer to sample the simplex (~66 compositions for a 3-element grid).
    """
    try:
        from apps.api.ml.matgl_models import predict_properties
        results = [predict_properties(c) for c in req.compositions]
        return BatchPredictResponse(results=results)
    except Exception as exc:
        raise HTTPException(500, str(exc))
