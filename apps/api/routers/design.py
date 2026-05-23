"""
POST /api/design/inverse   — run inverse design
GET  /api/design/session/{id}  — retrieve a design session
POST /api/design/session   — create a design session
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class PropertyTargetSchema(BaseModel):
    name: str
    min_val: float | None = None
    max_val: float | None = None
    optimize: str = "maximize"   # "maximize" | "minimize" | "range"


class InverseDesignSchema(BaseModel):
    elements: list[str]
    targets: list[PropertyTargetSchema]
    n_candidates: int = 10
    n_iterations: int = 30
    session_id: str | None = None


class CandidateSchema(BaseModel):
    composition: dict[str, float]
    properties: dict
    pareto_rank: int
    score: float
    is_pareto: bool = False
    method: str = "bo_qehvi"


@router.post("/inverse", response_model=list[CandidateSchema])
async def inverse_design(req: InverseDesignSchema):
    if not req.elements:
        raise HTTPException(400, "elements list is required")
    try:
        from apps.api.ml.inverse import (
            run_inverse_design,
            InverseDesignRequest,
            PropertyTarget,
        )
        targets = [PropertyTarget(**t.model_dump()) for t in req.targets]
        result = run_inverse_design(
            InverseDesignRequest(
                elements=req.elements,
                targets=targets,
                n_candidates=req.n_candidates,
                n_iterations=req.n_iterations,
            )
        )
        return [
            CandidateSchema(
                composition=c.composition,
                properties=c.properties,
                pareto_rank=c.pareto_rank,
                score=c.score,
                is_pareto=c.is_pareto,
                method=c.method,
            )
            for c in result
        ]
    except Exception as exc:
        raise HTTPException(500, str(exc))


class SessionCreate(BaseModel):
    name: str = "Untitled session"
    goals: dict = {}
    constraints: dict = {}


@router.post("/session")
async def create_session(body: SessionCreate):
    import uuid
    return {"id": str(uuid.uuid4()), **body.model_dump()}


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    # Stub — replace with DB lookup once DB is wired
    return {"id": session_id, "compositions": [], "messages": []}
