"""
Regression tests for Sprint 7 — engineering inverse-design briefs.

Validates:
1. Brief schema + constraint dataclasses load and serialise.
2. Feasibility evaluation works on stub candidates (without running BO).
3. Aggregate scoring follows the documented direction conventions.
4. End-to-end briefs return the expected alloy *family* in the top-5
   (the only deterministic check; exact compositions are stochastic).
5. Hard constraints actually filter: a brief with an unreachable
   constraint returns zero feasible candidates.
6. Performance: a 5-objective, 3-constraint brief completes in < 60 s.

Run:
    pytest apps/api/ml/eval/test_inverse_briefs.py -v
"""
from __future__ import annotations

import time
import pytest

from apps.api.ml.inverse_briefs import (
    DesignBrief, EngineeringObjective,
    OODConstraint, CIWidthConstraint, PhaseConstraint,
    evaluate_feasibility, aggregate_score, run_brief,
)
from apps.api.ml.eval.canonical_briefs import (
    CANONICAL_BRIEFS, EXPECTED_RESULT_FAMILIES,
)


# ── 1. Data classes ─────────────────────────────────────────────────────────

def test_engineering_objective_constructs():
    o = EngineeringObjective("yield_strength_MPa", "maximize",
                              min_val=200, weight=0.5)
    assert o.property == "yield_strength_MPa"
    assert o.direction == "maximize"
    assert o.weight == 0.5


def test_ood_constraint_default():
    c = OODConstraint()
    assert c.kind == "ood"
    assert c.model == "any"


def test_ci_width_constraint_requires_property_and_threshold():
    c = CIWidthConstraint(property="yield_strength_MPa", max_half_width=100)
    assert c.property == "yield_strength_MPa"
    assert c.max_half_width == 100
    assert c.kind == "ci_width"


def test_phase_constraint_round_trips():
    c = PhaseConstraint(phase="SIGMA", at_T_K=973, require="absent")
    assert c.phase == "SIGMA"
    assert c.at_T_K == 973
    assert c.require == "absent"


# ── 2. Feasibility evaluation on stubs ──────────────────────────────────────

def test_ood_constraint_passes_when_value_present():
    props = {"_details": {
        "yield_strength_MPa": {"value": 300, "source": "rf_aluminum"}
    }}
    violations = evaluate_feasibility({"Al": 99}, props, [OODConstraint()])
    assert violations == []


def test_ood_constraint_violated_when_value_missing():
    props = {"_details": {
        "yield_strength_MPa": {"value": None, "source": "rf_no_match"}
    }}
    violations = evaluate_feasibility({"Cu": 65, "Zn": 35}, props,
                                       [OODConstraint()])
    assert len(violations) == 1
    assert "OOD" in violations[0]


def test_ood_constraint_violated_when_source_is_out_of_domain():
    props = {"_details": {
        "yield_strength_MPa": {"value": None, "source": "rf_aluminum_out_of_domain"}
    }}
    violations = evaluate_feasibility({"Al": 95}, props, [OODConstraint()])
    assert len(violations) == 1


def test_ci_width_constraint_pass_and_fail():
    props_narrow = {"_details": {
        "yield_strength_MPa": {"value": 300, "ci_low": 250, "ci_high": 350,
                                "source": "rf_aluminum"}
    }}
    props_wide = {"_details": {
        "yield_strength_MPa": {"value": 300, "ci_low": 100, "ci_high": 500,
                                "source": "rf_aluminum"}
    }}
    c = CIWidthConstraint(property="yield_strength_MPa", max_half_width=100)
    assert evaluate_feasibility({"Al": 99}, props_narrow, [c]) == []
    v = evaluate_feasibility({"Al": 99}, props_wide, [c])
    assert len(v) == 1
    assert "CI half-width" in v[0]


def test_ci_width_constraint_missing_ci_reports_violation():
    """If a property has no CI (legacy model), report a violation —
    the user explicitly asked for an uncertainty bound."""
    props = {"_details": {"yield_strength_MPa": {"value": 300}}}
    c = CIWidthConstraint(property="yield_strength_MPa", max_half_width=100)
    v = evaluate_feasibility({"Al": 99}, props, [c])
    assert len(v) == 1
    assert "CI unavailable" in v[0]


def test_evaluate_feasibility_skips_expensive_when_requested():
    """Phase constraints are CALPHAD calls; the BO loop should skip them."""
    c = PhaseConstraint(phase="LIQUID", at_T_K=900, require="absent")
    # With skip_expensive=True, phase check is ignored entirely
    props = {"_details": {"yield_strength_MPa": {"value": 300, "source": "rf_aluminum"}}}
    v = evaluate_feasibility({"Al": 99}, props, [c], skip_expensive=True)
    assert v == []


# ── 3. Aggregate scoring direction conventions ──────────────────────────────

def test_aggregate_score_maximize_rewards_high():
    props_low  = {"yield_strength_MPa": 100}
    props_high = {"yield_strength_MPa": 500}
    obj = [EngineeringObjective("yield_strength_MPa", "maximize", min_val=100)]
    assert aggregate_score(props_high, obj) > aggregate_score(props_low, obj)


def test_aggregate_score_minimize_rewards_low():
    props_low  = {"density_g_cm3": 2.7}
    props_high = {"density_g_cm3": 8.0}
    obj = [EngineeringObjective("density_g_cm3", "minimize", max_val=10)]
    assert aggregate_score(props_low, obj) > aggregate_score(props_high, obj)


def test_aggregate_score_target_peaks_at_midpoint():
    obj = [EngineeringObjective("density_g_cm3", "target",
                                  min_val=7.5, max_val=8.0)]
    s_mid = aggregate_score({"density_g_cm3": 7.75}, obj)
    s_off = aggregate_score({"density_g_cm3": 6.0}, obj)
    assert s_mid > s_off


# ── 4. End-to-end briefs return correct family ──────────────────────────────

@pytest.mark.parametrize("brief_name", [
    "Aerospace Al wing skin",
    "Ti orthopaedic implant",
    "Ni-base turbine disc",
    "Low-cost structural steel",
    "Marine Al 5xxx",
])
def test_brief_returns_correct_family(brief_name):
    """Top-5 candidates of every canonical brief must include at least
    one from the expected family.  This is the *family-match* gate —
    novel compositions in the right family are acceptable; whole-wrong-
    family results are not."""
    from apps.api.ml.eval.brief_runner import _evaluate

    brief = next(b for b in CANONICAL_BRIEFS if b.name == brief_name)
    result = _evaluate(brief, top_n=5)
    expected_family = result["expected_family"]
    if expected_family is None:
        pytest.skip(f"{brief_name}: no expected family declared")
    # At least 1 of top-5 should land in the expected family.
    # (Boundary-pushing BO may explore just-out-of-domain compositions
    # that fall on the wrong side of the OOD threshold.)
    matches = [c for c in result["candidates"]
               if c["family_detected"] == expected_family]
    assert len(matches) >= 1, (
        f"{brief_name}: zero / 5 candidates in family "
        f"{expected_family} — BO is exploring the wrong region."
    )


# ── 5. Hard constraints actually filter ─────────────────────────────────────

def test_unreachable_ci_constraint_yields_no_feasible_candidates():
    """A 1-MPa CI tolerance is below the noise floor of all our models;
    no candidate should pass."""
    brief = DesignBrief(
        name="Impossibly tight CI",
        elements=["Al", "Mg", "Si", "Cu"],
        objectives=[EngineeringObjective("yield_strength_MPa", "maximize")],
        constraints=[CIWidthConstraint(property="yield_strength_MPa",
                                        max_half_width=1.0)],
        n_candidates=4, n_iterations=1, n_init=6, batch_size=2, seed=1,
        element_bounds={"Al": (5.0, 10.0)},
    )
    results = run_brief(brief)
    assert all(not c.is_feasible for c in results), (
        "Expected ALL candidates infeasible under 1 MPa CI tolerance"
    )


def test_brief_marks_violations_per_candidate():
    """Every infeasible candidate must report at least one violation."""
    brief = next(b for b in CANONICAL_BRIEFS if b.name == "Ti orthopaedic implant")
    results = run_brief(brief)
    for c in results:
        if not c.is_feasible:
            assert c.feasibility_violations, (
                f"Candidate {c.composition} marked infeasible but no violations recorded"
            )


# ── 6. Performance gate ─────────────────────────────────────────────────────

def test_brief_runtime_under_60_seconds():
    """Acceptance criterion from the roadmap: full brief in < 60 s."""
    brief = next(b for b in CANONICAL_BRIEFS if b.name == "Aerospace Al wing skin")
    t0 = time.perf_counter()
    _ = run_brief(brief)
    elapsed = time.perf_counter() - t0
    assert elapsed < 60.0, f"Brief took {elapsed:.1f}s, exceeded 60 s budget"
