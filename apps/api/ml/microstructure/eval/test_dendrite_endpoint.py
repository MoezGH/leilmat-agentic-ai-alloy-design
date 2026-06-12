"""
Contract tests for the public dendrite endpoint (``simulate_dendrite``).

The production path runs the anisotropic Kobayashi-Warren-Carter phase-field
on Taichi (``taichi_kwc``); the internal physics is covered by
``test_taichi_kwc.py``.  These tests pin the *public response contract* the
frontend depends on — source / calibration tags, frame shape, base64 PNG, and
in-process caching.

(The former Sprint-2.5 FiPy ``phase_field.py`` simulator and its stale tests
were removed once Taichi superseded it; this file replaces them.)

Run:
    pytest apps/api/ml/microstructure/eval/ -v
"""
from __future__ import annotations

import pytest

from apps.api.ml.microstructure.solidification import simulate_dendrite_sync


@pytest.mark.slow
def test_simulate_dendrite_contract():
    out = simulate_dendrite_sync(grid=60, n_steps=150, n_frames=4)
    assert "frames" in out and "metadata" in out
    # Current (Taichi) contract — NOT the retired "phase_field_kwc"/"schematic".
    assert out["source"] == "phase_field_kwc_anisotropic_taichi"
    assert out["calibration"] == "qualitative"
    assert isinstance(out["warnings"], list) and out["warnings"]
    if out["frames"]:
        f0 = out["frames"][0]
        assert "step" in f0 and "solid_fraction" in f0 and "png" in f0
        assert f0["png"].startswith("iVBOR")   # base64 PNG header


@pytest.mark.slow
def test_warnings_are_honest_about_scope():
    """Warnings must flag the qualitative / dimensionless framing (no
    quantitative-prediction overclaim)."""
    out = simulate_dendrite_sync(grid=50, n_steps=80, n_frames=2)
    joined = " ".join(out["warnings"]).lower()
    assert "2d" in joined or "dimensionless" in joined or "kobayashi" in joined


@pytest.mark.slow
def test_caching_returns_immediately():
    """Second call with the same payload should hit the in-process cache."""
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
