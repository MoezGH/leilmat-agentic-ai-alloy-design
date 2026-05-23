"""
Empirical-coverage tests for the conformal prediction intervals.

A 90% conformal interval should contain the true value at least 85% of the
time on a held-out test set (the small slack accommodates finite-sample
noise on the 20-30-alloy datasets).

Tests check coverage on:
  - The held-out non-ferrous YS alloys (Track B.1 dataset)
  - The canonical-phase formation-energy references (Track A.1)

Run:
    pytest apps/api/ml/eval/test_conformal_coverage.py -v
"""
from __future__ import annotations

import pickle
from pathlib import Path

import pytest

MODELS_DIR = Path(__file__).parent.parent.parent.parent.parent / "models"
TARGET_COVERAGE = 0.90
MIN_ACCEPTABLE_COVERAGE = 0.85   # slack for finite-sample variability


_FAMILY_FILES = {
    "aluminum": "aluminum_ys_rf.pkl",
    "titanium": "titanium_ys_rf.pkl",
    "nickel":   "nickel_ys_rf.pkl",
    "steel":    "yield_strength_rf.pkl",
}


def _model_exists(family: str) -> bool:
    return (MODELS_DIR / _FAMILY_FILES[family]).exists()


# ── 1. Calibrator is present and well-formed for each YS model ────────

@pytest.mark.parametrize("family", list(_FAMILY_FILES.keys()))
def test_ys_model_has_calibrator(family: str):
    """Every yield-strength model bundle should ship with a conformal calibrator."""
    if not _model_exists(family):
        pytest.skip("model file missing")
    with open(MODELS_DIR / _FAMILY_FILES[family], "rb") as f:
        bundle = pickle.load(f)
    assert "conformal" in bundle, (
        f"{family}: bundle missing 'conformal' field — re-run "
        "`python -m apps.api.ml.training`"
    )
    cal = bundle["conformal"]
    assert cal["q"] > 0
    assert cal["n_calibration"] >= 10
    assert 0.80 <= cal["empirical_coverage"] <= 1.00


@pytest.mark.parametrize("family,target_alpha", [(f, 0.10) for f in _FAMILY_FILES.keys()])
def test_ys_calibrator_targets_alpha_10(family: str, target_alpha: float):
    """Calibrators should be fit to α=0.10 (90% coverage)."""
    if not _model_exists(family):
        pytest.skip("model file missing")
    with open(MODELS_DIR / _FAMILY_FILES[family], "rb") as f:
        bundle = pickle.load(f)
    assert abs(bundle["conformal"]["alpha"] - target_alpha) < 1e-6


# ── 2. Empirical coverage on held-out alloys (the real test) ──────────

@pytest.fixture(scope="module")
def holdout_results():
    from apps.api.ml.eval.holdout_runner import run_all
    return run_all()


@pytest.mark.parametrize("family", ["aluminum", "titanium", "nickel"])
def test_ys_holdout_coverage_above_85pct(holdout_results, family):
    """Hold-out alloys should fall in the conformal interval at least 85% of
    the time (target 90% with finite-sample slack)."""
    if not _model_exists(family):
        pytest.skip("model file missing")
    preds = [p for p in holdout_results[family].get("predictions", [])
             if p.get("outcome") == "correct_predict"]
    if len(preds) < 3:
        pytest.skip(f"only {len(preds)} in-domain predictions — too few for coverage check")
    covered = sum(1 for p in preds
                  if p.get("ci_low") is not None
                  and p["ci_low"] <= p["y_true"] <= p["ci_high"])
    coverage = covered / len(preds)
    assert coverage >= MIN_ACCEPTABLE_COVERAGE, (
        f"{family}: coverage {coverage:.0%} on {len(preds)} hold-out alloys, "
        f"below the {MIN_ACCEPTABLE_COVERAGE:.0%} acceptable threshold. "
        f"Uncovered: {[p['name'] for p in preds if not (p['ci_low'] <= p['y_true'] <= p['ci_high'])]}"
    )


# ── 3. M3GNet conformal calibration is reachable ──────────────────────

def test_m3gnet_calibrator_produces_intervals():
    """M3GNet predictions should ship with ci_low/ci_high/coverage fields."""
    from apps.api.ml.m3gnet_predictor import formation_energy_m3gnet
    out = formation_energy_m3gnet({"Ni": 75.0, "Al": 25.0})
    if out.get("value") is None:
        pytest.skip("M3GNet model unavailable")
    assert "ci_low" in out and "ci_high" in out
    assert out["coverage"] == 0.9
    assert out["calibration"] == "conformal"
    assert out["ci_low"] < out["value"] < out["ci_high"]


def test_m3gnet_pure_element_zero_interval():
    """Pure elements should return a degenerate [0, 0] interval, source by_definition."""
    from apps.api.ml.m3gnet_predictor import formation_energy_m3gnet
    out = formation_energy_m3gnet({"Al": 100})
    assert out["value"] == 0.0
    assert out["ci_low"] == 0.0
    assert out["ci_high"] == 0.0
    assert out["calibration"] == "by_definition"


def test_m3gnet_canonical_phase_coverage():
    """At least 80% of canonical intermetallic phases should fall in their
    conformal interval (this is in-sample, but the calibrator is fit to the
    very edge of the distribution so coverage should be high)."""
    from apps.api.ml.m3gnet_predictor import formation_energy_m3gnet
    from apps.api.ml.eval.canonical_phases import CANONICAL_INTERMETALLICS

    in_interval = 0
    total = 0
    misses = []
    for entry in CANONICAL_INTERMETALLICS:
        out = formation_energy_m3gnet(entry["composition"])
        if out.get("value") is None or out.get("ci_low") is None:
            continue
        total += 1
        y_true = entry["ref_eV_per_atom"]
        if out["ci_low"] <= y_true <= out["ci_high"]:
            in_interval += 1
        else:
            misses.append((entry["name"], y_true, out["ci_low"], out["ci_high"]))
    if total < 5:
        pytest.skip(f"only {total} M3GNet predictions available")
    coverage = in_interval / total
    assert coverage >= 0.80, (
        f"M3GNet canonical coverage {coverage:.0%} ({in_interval}/{total}). "
        f"Misses: {misses}"
    )
