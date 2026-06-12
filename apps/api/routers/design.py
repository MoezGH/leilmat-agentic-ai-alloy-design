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
    # Present (non-null) only when BoTorch was skipped and this is a
    # random-search result — surfaced so the UI can label it honestly.
    fallback_reason: str | None = None


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


# ─────────────────────────────────────────────────────────────────────────
# Sprint 7 — engineering inverse-design briefs
# ─────────────────────────────────────────────────────────────────────────

class EngineeringObjectiveSchema(BaseModel):
    property:  str
    direction: str            # "maximize" | "minimize" | "target"
    min_val:   float | None = None
    max_val:   float | None = None
    weight:    float = 1.0


class DesignBriefSchema(BaseModel):
    name:         str
    elements:     list[str]
    objectives:   list[EngineeringObjectiveSchema]
    constraints:  list[dict] = []   # tagged union via "kind"
    temper:       str | None = None
    n_candidates: int = 8
    n_iterations: int = 2
    n_init:       int = 10
    batch_size:   int = 3
    seed:         int = 42
    element_bounds: dict | None = None


def _parse_constraint(d: dict):
    """Turn a tagged-union dict into the right dataclass."""
    from apps.api.ml.inverse_briefs import (
        OODConstraint, CIWidthConstraint, PhaseConstraint,
    )
    kind = d.get("kind", "ood")
    if kind == "ood":
        return OODConstraint(model=d.get("model", "any"))
    if kind == "ci_width":
        return CIWidthConstraint(
            property=d["property"],
            max_half_width=float(d["max_half_width"]),
        )
    if kind == "phase":
        return PhaseConstraint(
            phase=d["phase"],
            at_T_K=float(d["at_T_K"]),
            require=d["require"],
            min_fraction=d.get("min_fraction"),
            max_fraction=d.get("max_fraction"),
            tolerance=float(d.get("tolerance", 0.01)),
        )
    raise ValueError(f"Unknown constraint kind: {kind!r}")


@router.post("/brief")
async def design_brief(req: DesignBriefSchema):
    """Run a Sprint-7 engineering design brief.

    Constraints are tagged-union dicts:

      ``{"kind": "ood"}`` — composition must be in-domain for some YS model.
      ``{"kind": "ci_width", "property": "yield_strength_MPa", "max_half_width": 100}``
      ``{"kind": "phase", "phase": "SIGMA", "at_T_K": 973, "require": "absent"}``

    Returns the ranked candidate list (feasible-first, then Pareto rank,
    then aggregate score) with per-candidate violations.
    """
    from apps.api.ml.inverse_briefs import (
        DesignBrief, EngineeringObjective, run_brief,
    )

    try:
        constraints = [_parse_constraint(c) for c in req.constraints]
    except Exception as exc:
        raise HTTPException(400, f"Bad constraint: {exc}")

    brief = DesignBrief(
        name=req.name,
        elements=req.elements,
        objectives=[
            EngineeringObjective(
                property=o.property, direction=o.direction,
                min_val=o.min_val, max_val=o.max_val, weight=o.weight,
            ) for o in req.objectives
        ],
        constraints=constraints,
        temper=req.temper,
        n_candidates=req.n_candidates,
        n_iterations=req.n_iterations,
        n_init=req.n_init,
        batch_size=req.batch_size,
        seed=req.seed,
        element_bounds=(
            {k: tuple(v) for k, v in req.element_bounds.items()}
            if req.element_bounds else None
        ),
    )

    try:
        results = run_brief(brief)
    except Exception as exc:
        raise HTTPException(500, f"Brief failed: {exc}")

    return {
        "name": brief.name,
        "n_returned": len(results),
        "n_feasible": sum(c.is_feasible for c in results),
        "candidates": [
            {
                "composition":            c.composition,
                "properties":             c.properties,
                "aggregate_score":        c.aggregate_score,
                "pareto_rank":            c.pareto_rank,
                "is_pareto":              c.is_pareto,
                "is_feasible":            c.is_feasible,
                "feasibility_violations": c.feasibility_violations,
                "method":                 c.method,
            }
            for c in results
        ],
    }


@router.get("/briefs/canonical")
async def list_canonical_briefs():
    """Return the canonical brief library for the UI dropdown."""
    from apps.api.ml.eval.canonical_briefs import (
        CANONICAL_BRIEFS, EXPECTED_RESULT_FAMILIES,
    )
    return {
        "briefs": [
            {
                "name":          b.name,
                "elements":      b.elements,
                "temper":        b.temper,
                "n_objectives":  len(b.objectives),
                "n_constraints": len(b.constraints),
                "expected":      EXPECTED_RESULT_FAMILIES.get(b.name, {}),
            }
            for b in CANONICAL_BRIEFS
        ]
    }
