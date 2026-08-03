"""
Tests for the per-element extrapolation guard (apps/api/ml/ood.py).

Why this guard exists — the KNN detector scores 132 *aggregate* Magpie
statistics, so substituting one element for a chemically similar one barely
moves the score.  Measured before the fix: Ti-20Cu (40x the training max Cu)
sat at 0.98x the KNN threshold and returned a confident 903 MPa.

The most important test in this file is ``test_no_legitimate_alloy_refused`` —
a guard that refuses real alloys is worse than the hole it plugs.
"""
from __future__ import annotations

import pytest

from apps.api.ml.alloy_datasets import weight_to_atomic
from apps.api.ml.ood import check_element_bounds, fit_element_bounds


# ── 1. fit_element_bounds ──────────────────────────────────────────────

def test_bounds_are_atomic_not_weight():
    """Bounds must be in at% — the inference path passes at%, so wt% would mis-scale."""
    alloys = [{"composition_wt": {"Ti": 90.0, "Al": 6.0, "V": 4.0}}]
    bounds = fit_element_bounds(alloys)
    expected = weight_to_atomic({"Ti": 90.0, "Al": 6.0, "V": 4.0})
    # Al is much lighter than Ti, so at% >> wt% — this is the discriminating check.
    assert bounds["Al"] == pytest.approx(expected["Al"], rel=1e-6)
    assert bounds["Al"] > 6.0


def test_bounds_take_maximum_across_rows():
    alloys = [
        {"composition_wt": {"Ti": 99.0, "Cu": 1.0}},
        {"composition_wt": {"Ti": 95.0, "Cu": 5.0}},
    ]
    bounds = fit_element_bounds(alloys)
    high = weight_to_atomic({"Ti": 95.0, "Cu": 5.0})
    assert bounds["Cu"] == pytest.approx(high["Cu"], rel=1e-6)


def test_malformed_row_does_not_kill_fitting():
    alloys = [
        {"composition_wt": {"Ti": 90.0, "Al": 10.0}},
        {"composition_wt": {}},
        {},
    ]
    assert fit_element_bounds(alloys)  # non-empty, no exception


# ── 2. check_element_bounds ────────────────────────────────────────────

def test_absent_element_is_infinite_ratio():
    is_ood, ratio, el = check_element_bounds({"Ti": 95.0}, {"Ti": 90.0, "W": 10.0})
    assert is_ood and el == "W" and ratio == float("inf")


def test_extrapolation_beyond_threshold_refused():
    is_ood, ratio, el = check_element_bounds(
        {"Ti": 95.0, "Cu": 1.0}, {"Ti": 80.0, "Cu": 20.0})
    assert is_ood and el == "Cu" and ratio == pytest.approx(20.0)


def test_modest_extrapolation_allowed():
    """5x must pass — Ti-2.5Cu sits here and the model predicts it well."""
    is_ood, ratio, _ = check_element_bounds(
        {"Ti": 95.0, "Cu": 1.0}, {"Ti": 95.0, "Cu": 5.0})
    assert not is_ood and ratio == pytest.approx(5.0)


def test_trace_impurity_ignored():
    """A 0.01 at% impurity absent from training must not trigger a refusal."""
    is_ood, _, _ = check_element_bounds({"Ti": 95.0}, {"Ti": 99.9, "C": 0.01})
    assert not is_ood


def test_empty_bounds_is_permissive():
    """Bundles predating this feature carry no bounds and must not start refusing."""
    is_ood, _, _ = check_element_bounds({}, {"Ti": 50.0, "Cu": 50.0})
    assert not is_ood


def test_threshold_is_configurable():
    assert check_element_bounds({"Cu": 1.0}, {"Cu": 6.0}, max_extrapolation=5.0)[0]
    assert not check_element_bounds({"Cu": 1.0}, {"Cu": 6.0}, max_extrapolation=10.0)[0]


# ── 3. End-to-end through the production predictor ─────────────────────

def _predict(comp_wt: dict, temper: str = "STA") -> dict:
    from apps.api.ml.matgl_models import yield_strength_MPa
    return yield_strength_MPa(weight_to_atomic(comp_wt), temper=temper)


def test_ti_20cu_now_refused():
    """The regression this guard was built for."""
    p = _predict({"Ti": 80.0, "Cu": 20.0})
    assert p.get("value") is None
    assert p.get("ood_reason") == "element_extrapolation"
    assert p.get("ood_element") == "Cu"
    assert "out_of_domain" in (p.get("source") or "")


def test_absent_element_refused_end_to_end():
    p = _predict({"Ti": 90.0, "W": 10.0})
    assert p.get("value") is None
    assert p.get("ood_reason") == "element_absent"
    assert p.get("ood_element") == "W"


@pytest.mark.parametrize("name,comp,temper", [
    ("Ti-6Al-4V",     {"Ti": 90.0, "Al": 6.0, "V": 4.0}, "STA"),
    ("Grade 2 CP-Ti", {"Ti": 99.2, "Fe": 0.3, "O": 0.25}, "Annealed"),
    ("Ti-2.5Cu",      {"Ti": 97.5, "Cu": 2.5}, "STA"),
])
def test_known_good_titanium_still_predicts(name, comp, temper):
    p = _predict(comp, temper)
    assert p.get("value") is not None, f"{name} was refused: {p.get('error')}"


def test_no_legitimate_alloy_refused():
    """
    The false-refusal regression test — the one that matters most.

    Every alloy across the holdout and external-OOD sets that we expect to be
    in-domain must still receive a prediction.  A guard that refuses real
    alloys is worse than the hole it plugs.
    """
    from apps.api.ml.eval.holdout_alloys import ALL_HOLDOUT, ALL_OOD_EXTERNAL
    from apps.api.ml.matgl_models import yield_strength_MPa

    refused: list[str] = []
    for tier in (ALL_HOLDOUT, ALL_OOD_EXTERNAL):
        for family, alloys in tier.items():
            for a in alloys:
                if not a.get("expected_in_domain", True):
                    continue  # genuinely OOD by design; refusal is correct
                pred = yield_strength_MPa(
                    weight_to_atomic(a["composition_wt"]), temper=a.get("temper"))
                if pred.get("value") is None and pred.get("ood_reason"):
                    refused.append(
                        f"{family}/{a['name']} ({pred['ood_reason']} "
                        f"via {pred.get('ood_element')})")

    assert not refused, "element-bounds guard falsely refused: " + "; ".join(refused)
