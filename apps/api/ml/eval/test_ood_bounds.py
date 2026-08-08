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


# ── Missing-trace-element diagnostics ───────────────────────────────────
#
# Magpie min/max/range descriptors are computed over the elements PRESENT,
# with no concentration weighting, so omitting a 0.05 wt% carbon moves
# `minimum AtomicWeight` from 52 to 12 and throws the vector out of the
# training cloud.  The refusal is correct — dropping C and Si from AISI 316
# moves general_steel's own output from 218 MPa (lit ~215) to 831 MPa — but
# the user can only act on the reason, so it must be named.

def test_ubiquitous_elements_learned_for_steel():
    """Steel bundles must know C/Si/Mn are near-universal in their training set."""
    import joblib
    from pathlib import Path
    p = Path(__file__).resolve().parents[4] / "models" / "general_steel_ys_rf.pkl"
    if not p.exists():
        import pytest
        pytest.skip("general_steel bundle not built")
    ubiq = joblib.load(p).get("ubiquitous_elements") or {}
    for el in ("Fe", "C"):
        assert el in ubiq, f"{el} should be ubiquitous in general_steel training data"


def test_missing_trace_elements_are_named_in_refusal():
    """A steel missing C/Si must be refused WITH the omission spelled out."""
    from apps.api.ml.matgl_models import yield_strength_MPa
    partial = {"Fe": 67.0, "Cr": 17.0, "Ni": 12.0, "Mo": 2.5, "Mn": 1.5}   # AISI 316 sans C/Si
    pred = yield_strength_MPa(weight_to_atomic(partial), temper="Annealed")

    assert pred.get("value") is None, "refusal is correct here — the prediction would be ~4x wrong"
    assert pred.get("ood_reason") == "missing_expected_elements"
    missing = pred.get("missing_elements") or {}
    assert "C" in missing, f"carbon omission must be surfaced, got {missing}"
    assert "C" in (pred.get("error") or ""), "the error text must name the missing element"


def test_complete_composition_still_predicts():
    """The same alloy WITH its trace elements must predict normally —
    proving the diagnostic did not become a new refusal path."""
    from apps.api.ml.matgl_models import yield_strength_MPa
    full = {"Fe": 67.0, "C": 0.05, "Cr": 17.0, "Ni": 12.0,
            "Mo": 2.5, "Mn": 1.5, "Si": 0.5}
    pred = yield_strength_MPa(weight_to_atomic(full), temper="Annealed")
    assert pred.get("value") is not None, f"AISI 316 should predict, got {pred.get('error')}"
    assert 120 <= pred["value"] <= 350, f"expected ~215 MPa for annealed 316, got {pred['value']}"


def test_find_missing_ubiquitous_is_units_agnostic():
    """Only presence is compared, so wt% and at% inputs behave identically."""
    from apps.api.ml.ood import find_missing_ubiquitous
    ubiq = {"Fe": 90.0, "C": 0.18}
    assert find_missing_ubiquitous(ubiq, {"Fe": 99.0}) == {"C": 0.18}
    assert find_missing_ubiquitous(ubiq, {"Fe": 99.0, "C": 0.1}) == {}
    assert find_missing_ubiquitous(ubiq, {"Fe": 99.0, "C": 0.0}) == {"C": 0.18}
    assert find_missing_ubiquitous({}, {"Fe": 99.0}) == {}
