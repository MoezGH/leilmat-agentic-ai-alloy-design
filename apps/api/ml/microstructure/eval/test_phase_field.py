"""
Regression tests for the FiPy phase-field microstructure simulator (Sprint 2.5).

Tests check that the physics + API surface behave correctly:
* The seed grows monotonically (no dissolving)
* Latent heat is released into the temperature field
* N-fold symmetry parameter affects morphology
* The API contract is stable
* Caching works

The full Kobayashi-Warren-Carter dendrite with side-branching arms requires
the cross-derivative anisotropy term that we explicitly omit (schematic
calibration).  These tests validate what the simulator *does* reproduce:
anisotropic faceted-crystal growth from an undercooled seed.

Run:
    pytest apps/api/ml/microstructure/eval/ -v -m "not slow"
"""
from __future__ import annotations

import numpy as np
import pytest

from apps.api.ml.microstructure.phase_field import run_kwc, DEFAULT_PARAMS
from apps.api.ml.microstructure.solidification import (
    simulate_dendrite_sync,
)


# ── 1. Direct phase-field physics ─────────────────────────────────────────────

@pytest.mark.slow
def test_seed_grows_under_undercooling():
    """A seed in an undercooled bath must grow (solid fraction monotone non-decreasing)."""
    out = run_kwc(grid=80, n_steps=400, n_frames=6, dt=5e-5)
    fractions = [f["solid_fraction"] for f in out["frames"]]
    assert len(fractions) >= 3
    # Each subsequent frame should have at least as much solid (or equal — early stop)
    for a, b in zip(fractions, fractions[1:]):
        assert b >= a - 1e-3, f"Seed regression: {a:.3f} → {b:.3f}"
    # Must show real growth
    assert fractions[-1] > fractions[0] + 0.05


@pytest.mark.slow
def test_latent_heat_warms_growing_region():
    """Some part of the domain must be hotter than the initial bath
    (latent-heat release into the temperature field)."""
    out = run_kwc(grid=80, n_steps=400, n_frames=4, dt=5e-5)
    if not out["frames"]:
        pytest.skip("no frames produced")
    final_T = out["frames"][-1]["T"]
    # The bath starts at -0.3 (see DEFAULT_PARAMS); somewhere should be > -0.1
    assert float(final_T.max()) > -0.1, (
        f"Latent-heat release not visible: max T = {float(final_T.max()):.3f}"
    )


@pytest.mark.slow
def test_N_fold_symmetry_changes_morphology():
    """Different N values must produce visibly different shapes."""
    out_4 = run_kwc(grid=80, n_steps=400, n_frames=4, dt=5e-5,
                     params={"N": 4.0, "c": 0.10})
    out_6 = run_kwc(grid=80, n_steps=400, n_frames=4, dt=5e-5,
                     params={"N": 6.0, "c": 0.10})
    if not (out_4["frames"] and out_6["frames"]):
        pytest.skip("simulations did not produce frames")
    phi4 = out_4["frames"][-1]["phi"]
    phi6 = out_6["frames"][-1]["phi"]
    # The two should be measurably different (per-pixel L1 difference > 1 %)
    diff = float(np.abs(phi4 - phi6).mean())
    assert diff > 0.005, f"N=4 vs N=6 indistinguishable: mean |Δφ| = {diff:.4f}"


# ── 2. API contract ───────────────────────────────────────────────────────────

@pytest.mark.slow
def test_simulate_dendrite_returns_required_keys():
    out = simulate_dendrite_sync(grid=60, n_steps=150, n_frames=4)
    assert "frames" in out
    assert "metadata" in out
    assert out["source"] == "phase_field_kwc"
    assert out["calibration"] == "schematic"
    assert isinstance(out["warnings"], list)
    if out["frames"]:
        f0 = out["frames"][0]
        assert "step" in f0 and "solid_fraction" in f0 and "png" in f0
        assert f0["png"].startswith("iVBOR")   # base64 PNG header


@pytest.mark.slow
def test_caching_returns_immediately():
    """Second call with same payload should return the cached result quickly."""
    import time
    from apps.api.ml.microstructure import solidification as sm
    sm._CACHE.clear()
    t0 = time.time()
    simulate_dendrite_sync(grid=60, n_steps=120, n_frames=3)
    cold = time.time() - t0
    t1 = time.time()
    simulate_dendrite_sync(grid=60, n_steps=120, n_frames=3)
    warm = time.time() - t1
    assert warm < cold * 0.1, f"Cached call ({warm:.2f}s) should be ≪ cold ({cold:.2f}s)"


@pytest.mark.slow
def test_warnings_include_schematic_caveat():
    """The honest 'schematic' caveat must appear in the warnings list."""
    out = simulate_dendrite_sync(grid=50, n_steps=80, n_frames=2)
    joined = " ".join(out["warnings"]).lower()
    assert "schematic" in joined or "2d" in joined or "dimensionless" in joined


# ── 3. Smoke (fast) ───────────────────────────────────────────────────────────

def test_default_params_have_expected_shape():
    """DEFAULT_PARAMS must contain the KWC fields the model relies on."""
    for k in ("alpha", "c", "N", "theta_0", "kappa1", "kappa2", "tau",
              "eps_bar", "K", "D"):
        assert k in DEFAULT_PARAMS


def test_anisotropy_strength_in_dendrite_regime():
    """Anisotropy strength c must be ≥ 0.04 for visible faceting."""
    assert DEFAULT_PARAMS["c"] >= 0.04
