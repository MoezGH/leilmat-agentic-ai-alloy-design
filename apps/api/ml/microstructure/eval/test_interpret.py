"""
Regression tests for the dendrite interpretation pipeline.

Layer 1 (image analysis) is fully tested here — it's deterministic and
fast.  Layer 2 (LLM call) gets a structural sanity check only — we
mock the OpenAI client because real LLM responses are non-deterministic
and we don't want CI to make network calls.

Run:
    pytest apps/api/ml/microstructure/eval/test_interpret.py -v
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from apps.api.ml.microstructure.interpret import (
    analyse_dendrite,
    _angular_radius_profile,
    _count_arms,
    _circularity,
    _symmetry_score,
    _boundary_touching,
    _classify_regime,
)


# ─────────────────────────────────────────────────────────────────────
# Synthetic fixtures — controlled inputs that exercise each measurement
# ─────────────────────────────────────────────────────────────────────

def _disc(grid: int, radius: float) -> np.ndarray:
    """A filled disc centred in the grid — circularity ~ 1.0, no arms."""
    cy = cx = (grid - 1) / 2.0
    yy, xx = np.meshgrid(np.arange(grid), np.arange(grid), indexing="ij")
    return ((yy - cy) ** 2 + (xx - cx) ** 2 <= radius ** 2).astype(np.float32)


def _star(grid: int, n_arms: int, length: float, width: float = 1.5) -> np.ndarray:
    """A radial 'star' with `n_arms` evenly spaced spokes — exercises arm
    detection and N-fold symmetry."""
    cy = cx = (grid - 1) / 2.0
    yy, xx = np.meshgrid(np.arange(grid), np.arange(grid), indexing="ij")
    dy = yy - cy
    dx = xx - cx
    r = np.hypot(dy, dx)
    theta = np.arctan2(dy, dx)
    phi = np.zeros((grid, grid), dtype=np.float32)
    # Always include a small central seed so the center-of-mass is defined.
    phi[r <= 3.0] = 1.0
    for k in range(n_arms):
        arm_angle = 2 * np.pi * k / n_arms
        # Wrap angular distance to (-pi, pi]
        d_theta = (theta - arm_angle + np.pi) % (2 * np.pi) - np.pi
        # Cells within `width` perpendicular cells of the arm centerline
        # AND within `length` radial cells:  thin spoke
        cross = r * np.sin(d_theta)
        along = r * np.cos(d_theta)
        phi[(np.abs(cross) <= width) & (along >= 0) & (along <= length)] = 1.0
    return phi


# ─────────────────────────────────────────────────────────────────────
# 1. Geometric primitives
# ─────────────────────────────────────────────────────────────────────

def test_disc_circularity_is_high():
    """A filled disc must score ≥ 0.85 on circularity."""
    phi = _disc(120, 30)
    assert _circularity(phi > 0.5) >= 0.85


def test_star_circularity_is_low():
    """A 6-arm star must score < 0.30 on circularity (branched shape)."""
    phi = _star(120, 6, length=40)
    assert _circularity(phi > 0.5) < 0.30


def test_boundary_touching_negative():
    """A small central disc must not touch the boundary."""
    phi = _disc(120, 20)
    assert _boundary_touching(phi > 0.5, margin=3) is False


def test_boundary_touching_positive():
    """A disc large enough to reach the edge must trigger the warning."""
    phi = _disc(120, 60)   # radius reaches the edge
    assert _boundary_touching(phi > 0.5, margin=3) is True


# ─────────────────────────────────────────────────────────────────────
# 2. Arm count detection
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("n_expected", [3, 4, 6, 8])
def test_arm_count_matches_synthetic_star(n_expected):
    """Arm-count detection must recover N for clean synthetic stars.

    Allow ±1 tolerance at N=8 — at 180 angular bins the inter-arm gap
    is 22 bins (≈ the min_separation_deg threshold) so a satellite peak
    can leak through.  Real engineering dendrites are N=4 (BCC) or N=6
    (FCC/HCP), and at those orders the algorithm is exact.
    """
    phi = _star(120, n_expected, length=40)
    mask = phi > 0.5
    profile = _angular_radius_profile(mask, (59.5, 59.5), n_bins=180)
    n_detected, _ = _count_arms(profile)
    if n_expected <= 6:
        assert n_detected == n_expected, (
            f"Expected {n_expected} arms, detected {n_detected}"
        )
    else:
        assert abs(n_detected - n_expected) <= 1, (
            f"Expected {n_expected}±1 arms, detected {n_detected}"
        )


def test_arm_count_on_seed_only():
    """A seed-only disc has zero distinct arms."""
    phi = _disc(120, 10)
    mask = phi > 0.5
    profile = _angular_radius_profile(mask, (59.5, 59.5))
    n_detected, _ = _count_arms(profile)
    # A disc has an essentially-flat angular profile → no peaks above
    # the prominence threshold → 0 arms.
    assert n_detected == 0


# ─────────────────────────────────────────────────────────────────────
# 3. Symmetry scoring
# ─────────────────────────────────────────────────────────────────────

def test_symmetry_score_high_on_matching_nfold():
    """A 6-arm star should score high (> 0.5) on 6-fold symmetry."""
    phi = _star(120, 6, length=40)
    mask = phi > 0.5
    profile = _angular_radius_profile(mask, (59.5, 59.5))
    sym = _symmetry_score(profile, n_fold_expected=6)
    assert sym > 0.5, f"6-fold star scored {sym:.3f} on N=6 symmetry"


def test_symmetry_score_low_on_mismatched_nfold():
    """A 6-arm star should score lower on 4-fold expectation than on 6."""
    phi = _star(120, 6, length=40)
    mask = phi > 0.5
    profile = _angular_radius_profile(mask, (59.5, 59.5))
    sym_4 = _symmetry_score(profile, n_fold_expected=4)
    sym_6 = _symmetry_score(profile, n_fold_expected=6)
    assert sym_6 > sym_4, (
        f"6-fold star scored higher on 4-fold ({sym_4:.3f}) than on 6-fold ({sym_6:.3f})"
    )


# ─────────────────────────────────────────────────────────────────────
# 4. Regime classification (heuristic)
# ─────────────────────────────────────────────────────────────────────

def test_regime_nucleation_for_tiny_solid():
    assert _classify_regime(
        n_arms=0, n_arms_expected=6, side_branch_amp="none",
        circularity=0.0, solid_fraction=0.0005,
    ) == "nucleation"


def test_regime_spherical_for_blob():
    assert _classify_regime(
        n_arms=0, n_arms_expected=6, side_branch_amp="none",
        circularity=0.95, solid_fraction=0.02,
    ) == "spherical"


def test_regime_dendritic_for_arms_with_side_branches():
    assert _classify_regime(
        n_arms=6, n_arms_expected=6, side_branch_amp="strong",
        circularity=0.15, solid_fraction=0.3,
    ) == "dendritic"


# ─────────────────────────────────────────────────────────────────────
# 5. End-to-end analyse_dendrite
# ─────────────────────────────────────────────────────────────────────

def test_analyse_dendrite_on_synthetic_star():
    """End-to-end: pass a 6-arm star as a single frame and verify the
    full schema returns sensible values."""
    phi = _star(120, 6, length=40)
    frames = [{
        "step": 1000, "time_s": 0.5,
        "solid_fraction": float((phi > 0.5).mean()),
        "phi": phi, "T": np.zeros_like(phi),
    }]
    params = {"N": 6, "T_bath": 0.5, "theta_0": 0.0}

    out = analyse_dendrite(frames, params)

    # Schema completeness
    for k in ("n_arms_detected", "n_arms_expected", "regime",
             "side_branch_amplitude", "symmetry_score", "circularity",
             "boundary_touching", "solid_fraction_final", "growth_phase",
             "quality_warnings", "source"):
        assert k in out, f"missing key {k}"

    # Specific values
    assert out["n_arms_detected"] == 6
    assert out["n_arms_expected"] == 6
    assert out["symmetry_score"] > 0.4
    assert out["circularity"] < 0.5
    assert out["boundary_touching"] is False
    assert out["source"] == "dendrite_image_analysis_v1"


def test_analyse_dendrite_empty_frames():
    """Empty-frame guard: no crash, clear warning."""
    out = analyse_dendrite([], {"N": 6, "T_bath": 0.5})
    assert out["regime"] == "no_data"
    assert out["n_arms_detected"] == 0
    assert "no frames" in out["quality_warnings"][0].lower()


def test_analyse_dendrite_fully_liquid_frame():
    """Fully-liquid frame: nucleation regime, clear warning."""
    grid = 60
    frames = [{
        "step": 0, "time_s": 0.0, "solid_fraction": 0.0,
        "phi": np.zeros((grid, grid), dtype=np.float32),
        "T":   np.zeros((grid, grid), dtype=np.float32),
    }]
    out = analyse_dendrite(frames, {"N": 6, "T_bath": 0.5})
    assert out["regime"] == "nucleation"
    assert out["n_arms_detected"] == 0
    assert any("nucleation" in w.lower() or "fully liquid" in w.lower()
               for w in out["quality_warnings"])


# ─────────────────────────────────────────────────────────────────────
# 6. Layer-2 fallback (no LLM in CI)
# ─────────────────────────────────────────────────────────────────────

def test_fallback_when_api_key_missing(monkeypatch):
    """When OPENROUTER_API_KEY is empty, interpret_dendrite must use the
    deterministic numeric-only fallback rather than raising."""
    import asyncio
    from apps.api.ml.microstructure.interpret_llm import interpret_dendrite

    # Force the API key to empty for this test.  The shared helper in
    # apps/api/ml/interpret_common.py now owns the settings read, so we
    # patch the attribute there.
    monkeypatch.setattr(
        "apps.api.ml.interpret_common.settings.openrouter_api_key",
        "",
        raising=False,
    )

    analysis = {
        "n_arms_detected": 6, "n_arms_expected": 6, "regime": "dendritic",
        "side_branch_amplitude": "strong", "boundary_touching": True,
        "solid_fraction_final": 0.30, "circularity": 0.12,
        "symmetry_score": 0.65, "tip_velocity_dimless": 35.0,
        "growth_phase": "impinging", "quality_warnings": [],
    }
    out = asyncio.run(interpret_dendrite(
        composition={"Al": 97.9, "Mg": 1.0, "Si": 0.6},
        temper="T6", T_C=175,
        analysis=analysis,
        sim_metadata={"grid": 120, "elapsed_s": 1.5},
    ))

    assert out["source"] == "deterministic_fallback"
    assert out["interpretation"]      # non-empty
    assert isinstance(out["recommendations"], list)
    # Boundary-touching case must surface a rerun-at-higher-fidelity rec
    titles = " ".join(r["title"].lower() for r in out["recommendations"])
    assert "fidelity" in titles or "rerun" in titles
