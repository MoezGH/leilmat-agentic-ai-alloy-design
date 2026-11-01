"""
Unit tests for the experimental bias correction (experimental_correction.py).

All tests run without matgl or network.  The correction is currently NOT applied (it did not beat the raw
M3GNet error on the verified references), so the applicability tests install sample coefficients with
monkeypatch; the guards are what they exercise.
"""
from __future__ import annotations

import pytest

from apps.api.ml.experimental_correction import (
    CORRECTION,
    correct_to_experimental,
    experimental_estimate,
)


@pytest.fixture
def fitted(monkeypatch):
    """Pretend a correction had been justified, to test the guards that would apply to it."""
    monkeypatch.setitem(CORRECTION, "slope", 0.9)
    monkeypatch.setitem(CORRECTION, "intercept", -0.01)
    monkeypatch.setitem(CORRECTION, "n_fit", 40)
    monkeypatch.setitem(CORRECTION, "fitted_at", "2099-01-01")


# ── 1. The decision is recorded with its evidence ──────────────────────

def test_no_correction_ships_unless_it_beats_the_raw_error_by_a_margin():
    """A linear map fitted on a dozen points is noise unless it clearly helps; a shipped one must clear 20 %."""
    if CORRECTION["slope"] is not None:
        assert CORRECTION["loo_mae_eV"] <= 0.8 * CORRECTION["raw_mae_eV"]
        assert CORRECTION["n_fit"] >= 30
    else:
        assert CORRECTION["applied"] is False


def test_the_reference_set_is_the_verified_one():
    from apps.api.ml.eval.calorimetry_benchmark import CALORI_REFERENCES

    assert CORRECTION["n_fit"] == len(CALORI_REFERENCES)
    for ref in CALORI_REFERENCES:
        assert ref["source"]
        assert ref["ref_eV_per_atom"] < 0


# ── 2. Not applied: the field is omitted ───────────────────────────────

def test_without_a_justified_correction_nothing_is_attached():
    pred = {"value": -0.45, "source": "m3gnet_dft", "uncertainty": 0.3}
    if CORRECTION["slope"] is None:
        assert correct_to_experimental(-0.45) is None
        assert experimental_estimate(pred, {"Ni": 75.0, "Al": 25.0}) is None


# ── 3. correct_to_experimental / experimental_estimate guards (with sample coefficients) ──

def test_linear_map(fitted):
    assert abs(correct_to_experimental(-0.5) - (0.9 * -0.5 - 0.01)) < 1e-9


def _m3gnet_pred(value=-0.45):
    return {"value": value, "source": "m3gnet_dft", "uncertainty": 0.3}


def test_estimate_applies_to_m3gnet_binary(fitted):
    est = experimental_estimate(_m3gnet_pred(), {"Ni": 75.0, "Al": 25.0})
    assert est is not None
    assert est["value"] == round(correct_to_experimental(-0.45), 4)
    assert est["uncertainty"] == CORRECTION["loo_q90_eV"]
    assert "LOO-CV" in est["basis"]


def test_estimate_skips_miedema_fallback(fitted):
    pred = {"value": -0.45, "source": "miedema_heuristic", "uncertainty": 0.3}
    assert experimental_estimate(pred, {"Ni": 75.0, "Al": 25.0}) is None


def test_estimate_skips_pure_element(fitted):
    assert experimental_estimate(_m3gnet_pred(0.001), {"Al": 100.0}) is None


def test_estimate_skips_missing_value(fitted):
    pred = {"value": None, "source": "m3gnet_dft"}
    assert experimental_estimate(pred, {"Ni": 50.0, "Ti": 50.0}) is None
