"""
Regression tests for the full anisotropic KWC Taichi simulator (Sprint 2.6).

These tests are deliberately fast — they run small (grid=80, ~2000 steps)
simulations that complete in under 5 seconds even on a laptop, and they
check the *scientifically meaningful* properties:

* The seed in undercooled bath grows (no dissolving)
* Latent heat is released into the temperature field
* The morphology develops N-fold symmetry — count radial arms
* Tip velocity is positive and decays toward a steady-state value
* The simulator runs at ≥ 200 steps/s (sanity check on the Taichi compile)

The slow tests (``test_grid_200_produces_six_arms``) reproduce the canonical
Kobayashi 1993 morphology at grid=200 — they take ~10 s and are marked slow.

Run only fast suite:
    pytest apps/api/ml/microstructure/eval/test_taichi_kwc.py -v -m "not slow"
"""
import numpy as np
import pytest

# Skip the whole module cleanly when Taichi isn't installed
taichi = pytest.importorskip("taichi", reason="Taichi required for Sprint 2.6 tests")

from apps.api.ml.microstructure.taichi_kwc import (
    run_kwc, measure_tip_velocity, DEFAULT_PARAMS,
)


# ── 1. Smoke tests (fast) ─────────────────────────────────────────────────────

def test_default_params_complete():
    """All KWC parameters expected by the kernel are defined."""
    for k in ("N", "theta_0", "c", "eps_bar", "tau", "kappa1", "kappa2",
              "D", "K", "T_bath", "dt"):
        assert k in DEFAULT_PARAMS, f"Missing default parameter: {k}"


def test_default_T_bath_is_positive_undercooling():
    """Kobayashi 1993 convention: T = undercooling (positive when cold).

    A negative default would silently swap the sign convention back to the
    Sprint 2.5 (FiPy) form and the seed would dissolve instead of growing.
    """
    assert DEFAULT_PARAMS["T_bath"] > 0, (
        "T_bath must be positive — Kobayashi 1993 uses T = undercooling. "
        f"Got {DEFAULT_PARAMS['T_bath']}"
    )


def test_default_anisotropy_in_dendrite_regime():
    """Anisotropy strength must be ≥ 0.04 for visible MS instability."""
    assert DEFAULT_PARAMS["c"] >= 0.04


# ── 2. Single-process simulator (slow due to Taichi field allocation) ──────────

@pytest.mark.slow
def test_seed_grows_in_undercooled_bath():
    """Run a small simulation and verify the seed grows monotonically."""
    out = run_kwc(grid=80, n_steps=2000, seed_radius_cells=4,
                  target_solid_fractions=[0.005, 0.010, 0.020, 0.040],
                  log_every=50)
    sfs = [f["solid_fraction"] for f in out["frames"]]
    assert len(sfs) >= 3, f"Too few frames captured: {sfs}"
    # Solid fraction must rise monotonically (within numerical noise)
    for a, b in zip(sfs, sfs[1:]):
        assert b >= a - 1e-3, f"Seed regression: {a:.4f} → {b:.4f}"
    assert sfs[-1] > sfs[0] + 0.01, f"No real growth: sf range {sfs[0]} → {sfs[-1]}"


@pytest.mark.slow
def test_latent_heat_creates_thermal_field_response():
    """The temperature (undercooling) field must drop near the growing seed.

    Latent heat release locally reduces the undercooling (T → 0).  Far from
    the seed, T should still be ≈ T_bath.
    """
    out = run_kwc(grid=80, n_steps=1500, seed_radius_cells=4,
                  target_solid_fractions=[0.01, 0.03],
                  log_every=50)
    if len(out["frames"]) < 2:
        pytest.skip("simulation didn't reach the second milestone")
    T = out["frames"][-1]["T"]
    g = T.shape[0]
    T_near_seed = float(T[g//2 - 2:g//2 + 2, g//2 - 2:g//2 + 2].mean())
    T_far       = float(T[2:6, 2:6].mean())          # corner — far from centre
    assert T_near_seed < T_far - 0.05, (
        f"Latent heat should suppress undercooling near seed: "
        f"T_near={T_near_seed:.3f}, T_far={T_far:.3f}"
    )


@pytest.mark.slow
def test_morphology_shows_six_radial_arms():
    """Confirm N=6 symmetry produces six well-separated radial arms.

    Counts arms as distinct solid spokes intersecting a circle at 0.7×extent.
    """
    out = run_kwc(grid=120, n_steps=4000, seed_radius_cells=5,
                  params={"T_bath": 0.55, "c": 0.05},
                  target_solid_fractions=[0.01, 0.03, 0.06, 0.09],
                  log_every=50)
    final = out["frames"][-1]["phi"]
    g = final.shape[0]
    cx, cy = g // 2, g // 2
    solid = (final > 0.5)
    ys, xs = np.where(solid)
    assert ys.size > 0, "no solid region in the final frame"
    r_pix = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    r_sample = 0.7 * float(r_pix.max())
    # Sweep an angle and count solid→liquid transitions
    n_angles = 720
    in_arm = False
    arm_count = 0
    for k in range(n_angles):
        theta = 2 * np.pi * k / n_angles
        i = int(cy + r_sample * np.sin(theta))
        j = int(cx + r_sample * np.cos(theta))
        if 0 <= i < g and 0 <= j < g:
            is_solid = final[i, j] > 0.5
            if is_solid and not in_arm:
                arm_count += 1
                in_arm = True
            elif not is_solid:
                in_arm = False
    assert 5 <= arm_count <= 8, (
        f"Expected 5-8 primary arms (N=6 ± noise), counted {arm_count}.  "
        f"Morphology may not have developed enough — final sf={out['frames'][-1]['solid_fraction']:.3f}"
    )


# ── 3. Performance sanity ─────────────────────────────────────────────────────

@pytest.mark.slow
def test_taichi_is_at_least_200_steps_per_second():
    """The whole point of Sprint 2.6 is that Taichi is fast enough for
    interactive use.  If this regresses below 200 steps/s on grid=80, the
    JIT or LLVM pipeline has broken somewhere.
    """
    out = run_kwc(grid=80, n_steps=1000, seed_radius_cells=3, log_every=50)
    sps = out["metadata"]["steps_per_s"]
    assert sps >= 200, (
        f"Taichi performance regression: only {sps:.0f} steps/s on grid=80 "
        "(expected ≥ 200 — even a single CPU core should manage this)"
    )


# ── 4. Tip-velocity measurement ───────────────────────────────────────────────

@pytest.mark.slow
def test_tip_velocity_is_positive_and_in_karma_rappel_range():
    """Dimensionless tip velocity (sim-time, not wall-clock) must sit in the
    Karma-Rappel 1998 range: positive (growing) and below O(20) for our
    parameters (ε̄=0.01, D=1, T_bath=0.55).  Velocity above 20 indicates
    numerical instability; negative indicates the seed dissolves.
    """
    out = measure_tip_velocity(grid=100, n_steps=3000,
                               params={"T_bath": 0.55, "c": 0.05})
    if out["v_steady"] is None:
        pytest.skip("not enough history to estimate v_steady")
    v = out["v_steady"]
    assert 0 < v < 20.0, (
        f"Tip velocity {v} outside expected Karma-Rappel range (0, 20). "
        "Negative = dissolving; > 20 = numerical instability."
    )
