"""
POST /api/predict
Forward prediction: composition → properties.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

router = APIRouter()


class PredictRequest(BaseModel):
    composition: dict[str, float]    # {"Al": 90.0, "Mg": 5.0, "Si": 5.0}
    session_id: str | None = None

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
    try:
        from apps.api.ml.matgl_models import predict_properties
        props = predict_properties(req.composition)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return PredictResponse(composition=req.composition, properties=props)


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
