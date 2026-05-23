"""
apps.api.ml.inverse_briefs
============================

Sprint 7 — engineering-grade inverse-design briefs.

The existing ``inverse.py`` runs BoTorch qEHVI on a flat list of property
targets.  Sprint 7 adds:

* **Hard constraints** that filter candidates *after* BO produces them:
    - OOD: at least one YS model must be in-domain for the composition.
    - CI width: conformal half-width on a chosen property must be ≤
      user tolerance (else the "Pareto" point is meaningless).
    - Phase-assemblage: e.g. "no σ-phase at 700 K" or
      "γ' fraction between 0.3 and 0.5" — calls Sprint 1's CALPHAD
      equilibrium endpoint.

* **Per-objective weights** so the aggregate score reflects what the
  engineer cares about.

* **Optional temper** passed through to predict_properties — the Sprint-4
  temper-aware models distinguish 6061-O from 6061-T6.

* **Canonical briefs** as validation fixtures (`canonical_briefs.py`).

This file holds the data classes + the brief-runner.  The BO core stays
in ``inverse.py`` — we wrap and post-filter rather than rewriting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence


# ─────────────────────────────────────────────────────────────────────────
# Objective / constraint data classes
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class EngineeringObjective:
    """One property objective in a design brief.

    ``property``  : the key in ``predict_properties`` output
                    (e.g. ``"yield_strength_MPa"``, ``"density_g_cm3"``).
    ``direction`` : ``"maximize"`` | ``"minimize"`` | ``"target"``.
    ``min_val`` / ``max_val`` : optional bounds for a "target" objective.
    ``weight``    : aggregate-score weight (BoTorch qEHVI uses these for
                    hypervolume scalarisation).
    """
    property:  str
    direction: str            # "maximize" | "minimize" | "target"
    min_val:   Optional[float] = None
    max_val:   Optional[float] = None
    weight:    float = 1.0


@dataclass
class OODConstraint:
    """Composition must be in-domain for *at least one* YS model.

    ``model = "any"`` (default) — the routed YS model must report a value
    (not a *_out_of_domain source).
    """
    kind:  str = "ood"
    model: str = "any"          # currently only "any" is supported


@dataclass
class CIWidthConstraint:
    """Conformal CI half-width on ``property`` must be ≤ ``max_half_width``."""
    property:        str
    max_half_width:  float
    kind: str = "ci_width"


@dataclass
class PhaseConstraint:
    """Phase-assemblage constraint at a given service temperature.

    Either ``phase_absent`` (fraction must be < ``tolerance``) or
    ``phase_present`` (fraction must be > ``tolerance``) or both with
    ``min_fraction`` / ``max_fraction`` bounds.
    """
    phase:         str
    at_T_K:        float
    require:       str             # "absent" | "present" | "range"
    min_fraction:  Optional[float] = None
    max_fraction:  Optional[float] = None
    tolerance:     float = 0.01    # threshold for absent/present
    kind: str = "phase"


Constraint = OODConstraint | CIWidthConstraint | PhaseConstraint


@dataclass
class DesignBrief:
    name:         str
    elements:     List[str]
    objectives:   List[EngineeringObjective]
    constraints:  List[Constraint] = field(default_factory=list)
    temper:       Optional[str] = None
    n_candidates: int = 12
    n_iterations: int = 5
    n_init:       int = 16
    batch_size:   int = 4
    seed:         int = 42
    element_bounds: Optional[dict] = None


@dataclass
class BriefCandidate:
    composition:           dict
    properties:            dict
    aggregate_score:       float
    pareto_rank:           int = 0
    is_pareto:             bool = False
    is_feasible:           bool = True
    feasibility_violations: List[str] = field(default_factory=list)
    method:                str = "bo_qehvi"


# ─────────────────────────────────────────────────────────────────────────
# Constraint evaluation
# ─────────────────────────────────────────────────────────────────────────

def _check_ood(props: dict) -> Optional[str]:
    """None if a non-OOD YS prediction exists, else a violation message."""
    ys = props.get("_details", {}).get("yield_strength_MPa", {})
    source = ys.get("source", "")
    if "out_of_domain" in source or "no_match" in source or ys.get("value") is None:
        return f"OOD: YS prediction unavailable (source={source!r})"
    return None


def _check_ci_width(props: dict, c: CIWidthConstraint) -> Optional[str]:
    detail = props.get("_details", {}).get(c.property, {})
    lo, hi = detail.get("ci_low"), detail.get("ci_high")
    if lo is None or hi is None:
        return f"CI unavailable for {c.property}"
    half = (hi - lo) / 2.0
    if half > c.max_half_width:
        return (f"CI half-width on {c.property} = {half:.1f} "
                f"exceeds tolerance {c.max_half_width:.1f}")
    return None


def _check_phase_constraint(composition: dict, c: PhaseConstraint) -> Optional[str]:
    """Run CALPHAD equilibrium at the constraint's T and check the phase.

    Returns None when satisfied or when CALPHAD has no TDB for this
    chemsys (we don't fail-closed on missing-data; document instead).
    """
    try:
        from apps.api.ml.calphad.equilibrium import phase_assemblage_sync
        out = phase_assemblage_sync(composition, c.at_T_K)
    except Exception as exc:
        return f"phase check failed: {exc}"
    if out.get("source") == "calphad_no_tdb":
        return None      # don't refuse for missing TDB; just skip check
    phases = out.get("phases", {}) or {}
    frac = float(phases.get(c.phase, 0.0))
    if c.require == "absent":
        if frac > c.tolerance:
            return f"{c.phase} present at {frac:.3f} > {c.tolerance:.3f}"
        return None
    if c.require == "present":
        if frac < c.tolerance:
            return f"{c.phase} absent (fraction {frac:.3f} < {c.tolerance:.3f})"
        return None
    if c.require == "range":
        lo = c.min_fraction or 0.0
        hi = c.max_fraction or 1.0
        if not (lo <= frac <= hi):
            return f"{c.phase} fraction {frac:.3f} outside [{lo}, {hi}]"
        return None
    return None


def evaluate_feasibility(
    composition: dict,
    properties:  dict,
    constraints: Sequence[Constraint],
    *,
    skip_expensive: bool = False,
) -> List[str]:
    """Evaluate all constraints and return list of violations (empty = feasible).

    ``skip_expensive``: skip CALPHAD-based phase checks (used inside the
    BO loop, where we don't want a ~2 s phase calc on every candidate).
    """
    violations: List[str] = []
    for c in constraints:
        if isinstance(c, OODConstraint):
            v = _check_ood(properties)
            if v: violations.append(v)
        elif isinstance(c, CIWidthConstraint):
            v = _check_ci_width(properties, c)
            if v: violations.append(v)
        elif isinstance(c, PhaseConstraint):
            if skip_expensive:
                continue
            v = _check_phase_constraint(composition, c)
            if v: violations.append(v)
    return violations


# ─────────────────────────────────────────────────────────────────────────
# Aggregate scoring (weighted)
# ─────────────────────────────────────────────────────────────────────────

def aggregate_score(props: dict, objectives: Sequence[EngineeringObjective]) -> float:
    """Weighted sum of per-objective scaled scores.

    Each objective contributes a positive score for "good" outcomes:
    * maximize       → (v − min_val) / (typical span)   (positive = good)
    * minimize       → (max_val − v) / (typical span)
    * target         → 1 − |v − mid| / half_width       (1 = on target)
    """
    total = 0.0
    for o in objectives:
        v = props.get(o.property)
        if v is None and "_details" in props:
            v = props["_details"].get(o.property, {}).get("value")
        if v is None:
            continue
        v = float(v)
        if o.direction == "maximize":
            lo = o.min_val if o.min_val is not None else 0.0
            span = max(abs(v) + 1.0, 1.0)
            score = (v - lo) / span
        elif o.direction == "minimize":
            hi = o.max_val if o.max_val is not None else 1e6
            span = max(abs(hi) + 1.0, 1.0)
            score = (hi - v) / span
        elif o.direction == "target":
            if o.min_val is None or o.max_val is None:
                score = -abs(v)
            else:
                mid = (o.min_val + o.max_val) / 2.0
                half_w = max((o.max_val - o.min_val) / 2.0, 1e-6)
                score = 1.0 - abs(v - mid) / half_w
        else:
            score = 0.0
        total += o.weight * score
    return total


# ─────────────────────────────────────────────────────────────────────────
# Brief runner — wraps the existing BO + applies post-filter
# ─────────────────────────────────────────────────────────────────────────

def run_brief(brief: DesignBrief) -> List[BriefCandidate]:
    """Run a full engineering brief.

    Pipeline:
      1. Translate to legacy ``InverseDesignRequest`` and run BO.
      2. For each returned candidate, re-evaluate feasibility against
         the brief's constraints (including the expensive phase checks).
      3. Sort: feasible-first, then by Pareto rank, then aggregate score.
    """
    from apps.api.ml.inverse import (
        InverseDesignRequest, PropertyTarget, run_inverse_design,
    )
    from apps.api.ml.matgl_models import predict_properties

    # Translate engineering objectives → legacy property targets.
    legacy_targets = [
        PropertyTarget(
            name=o.property,
            min_val=o.min_val,
            max_val=o.max_val,
            optimize=("range" if o.direction == "target" else o.direction),
        )
        for o in brief.objectives
    ]
    req = InverseDesignRequest(
        elements=brief.elements,
        targets=legacy_targets,
        n_candidates=brief.n_candidates,
        n_iterations=brief.n_iterations,
        n_init=brief.n_init,
        batch_size=brief.batch_size,
        seed=brief.seed,
        element_bounds=brief.element_bounds,
    )

    raw = run_inverse_design(req)

    # Re-evaluate with the brief's temper (the legacy BO uses default).
    out: List[BriefCandidate] = []
    for r in raw:
        # Re-predict with the brief's chosen temper so YS reflects the
        # design heat treatment.
        if brief.temper is not None:
            props = predict_properties(r.composition, temper=brief.temper)
        else:
            props = r.properties
        violations = evaluate_feasibility(
            r.composition, props, brief.constraints,
            skip_expensive=False,
        )
        out.append(BriefCandidate(
            composition=r.composition,
            properties=props,
            aggregate_score=aggregate_score(props, brief.objectives),
            pareto_rank=r.pareto_rank,
            is_pareto=r.is_pareto,
            is_feasible=not violations,
            feasibility_violations=violations,
            method=r.method,
        ))

    # Sort: feasible first, then Pareto, then by score
    out.sort(key=lambda c: (not c.is_feasible, c.pareto_rank, -c.aggregate_score))
    return out
