"""
Unit tests for the experimental bias correction (experimental_correction.py).

All tests run without matgl or network — they exercise the frozen coefficients
and the applicability guards.
"""
from __future__ import annotations

from apps.api.ml.experimental_correction import (
    CORRECTION,
    correct_to_experimental,
    experimental_estimate,
)


# ── 1. Frozen coefficients are populated and sane ──────────────────────

def test_coefficients_are_fitted():
    assert CORRECTION["slope"] is not None
    assert CORRECTION["intercept"] is not None
    assert CORRECTION["n_fit"] >= 20
    assert CORRECTION["fitted_at"] is not None


def test_correction_shrinks_overbinding():
    """DFT overbinds — slope must be well below 1 and positive."""
    assert 0.0 < CORRECTION["slope"] < 1.0


def test_loo_beats_raw():
    """The whole point: corrected LOO MAE must beat the raw 232 meV gap."""
    assert CORRECTION["loo_mae_eV"] < 0.232


# ── 2. correct_to_experimental ─────────────────────────────────────────

def test_linear_map():
    a, b = CORRECTION["slope"], CORRECTION["intercept"]
    assert abs(correct_to_experimental(-0.5) - (a * -0.5 + b)) < 1e-9


# ── 3. experimental_estimate applicability guards ──────────────────────

def _m3gnet_pred(value=-0.45):
    return {"value": value, "source": "m3gnet_dft", "uncertainty": 0.3}


def test_estimate_applies_to_m3gnet_binary():
    est = experimental_estimate(_m3gnet_pred(), {"Ni": 75.0, "Al": 25.0})
    assert est is not None
    assert est["value"] == round(correct_to_experimental(-0.45), 4)
    assert est["uncertainty"] == CORRECTION["loo_q90_eV"]
    assert "LOO-CV" in est["basis"]


def test_estimate_skips_miedema_fallback():
    pred = {"value": -0.45, "source": "miedema_heuristic", "uncertainty": 0.3}
    assert experimental_estimate(pred, {"Ni": 75.0, "Al": 25.0}) is None


def test_estimate_skips_pure_element():
    assert experimental_estimate(_m3gnet_pred(0.001), {"Al": 100.0}) is None


def test_estimate_skips_missing_value():
    pred = {"value": None, "source": "m3gnet_dft"}
    assert experimental_estimate(pred, {"Ni": 50.0, "Ti": 50.0}) is None
