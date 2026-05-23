"""
Regression tests for Sprint 5 — KWN precipitation kinetics.

Checks:
1. Database integrity (every phase has the required keys, sensible γ / D).
2. Driving-force / nucleation-barrier physics behaves correctly.
3. The full simulator hits the canonical reference points within their
   declared tolerance band.
4. Edge cases (undersaturated, missing solute, unknown phase) refuse cleanly.
5. Time-resolved trajectory is monotone in solute depletion.

Run:
    pytest apps/api/ml/precipitation/eval/test_precipitation.py -v
"""
from __future__ import annotations

import math
import pytest

from apps.api.ml.precipitation.interfacial_energy import (
    PRECIPITATE_DATA, available_phases,
)
from apps.api.ml.precipitation.kwn import (
    simulate_precipitation_sync,
    _chemical_driving_force_J_m3,
    _nucleation_barrier_J,
    _critical_radius_m,
    _interp_Xeq,
)


# ── 1. Database integrity ────────────────────────────────────────────────────

REQUIRED_KEYS = {"gamma_J_m2", "matrix", "solute", "D0_m2_s", "Q_J_mol",
                 "V_m_m3_mol", "Xeq_T_C", "vacancy_enhancement", "morphology"}


def test_at_least_five_precipitate_phases():
    """We promised γ' / γ" / θ' / β" / η' / α at least."""
    assert len(PRECIPITATE_DATA) >= 5


@pytest.mark.parametrize("phase", list(PRECIPITATE_DATA))
def test_phase_database_has_required_keys(phase):
    entry = PRECIPITATE_DATA[phase]
    missing = REQUIRED_KEYS - set(entry.keys())
    assert not missing, f"{phase}: missing keys {missing}"


@pytest.mark.parametrize("phase", list(PRECIPITATE_DATA))
def test_phase_database_values_physical(phase):
    entry = PRECIPITATE_DATA[phase]
    assert 0 < entry["gamma_J_m2"] < 1.0,    f"{phase}: γ outside [0, 1] J/m²"
    assert 1e-8 < entry["D0_m2_s"] < 1e-2,    f"{phase}: D₀ outside Arrhenius range"
    assert 50_000 < entry["Q_J_mol"] < 400_000, f"{phase}: Q outside 50-400 kJ/mol"
    assert 1e-6 < entry["V_m_m3_mol"] < 1e-4, f"{phase}: V_m outside molar-volume range"
    assert entry["vacancy_enhancement"] >= 1.0, f"{phase}: enhancement must be ≥1"


# ── 2. Physics helpers ───────────────────────────────────────────────────────

def test_driving_force_zero_at_equilibrium():
    """ΔG_v = 0 when X_α = X_eq."""
    assert _chemical_driving_force_J_m3(0.01, 0.01, 0.5, 2.8e-5, 463.0) == 0.0


def test_driving_force_positive_when_supersaturated():
    """ΔG_v > 0 when X_α > X_eq (drives precipitation)."""
    g = _chemical_driving_force_J_m3(0.02, 0.005, 0.5, 2.8e-5, 463.0)
    assert g > 0


def test_driving_force_zero_when_undersaturated():
    """ΔG_v = 0 (not negative) when X_α < X_eq — model floor."""
    g = _chemical_driving_force_J_m3(0.001, 0.005, 0.5, 2.8e-5, 463.0)
    assert g == 0


def test_nucleation_barrier_scales_with_gamma_cubed():
    """Doubling γ should multiply ΔG* by 8."""
    g_v = 4e8
    dG1 = _nucleation_barrier_J(0.1, g_v)
    dG2 = _nucleation_barrier_J(0.2, g_v)
    assert dG2 / dG1 == pytest.approx(8.0, rel=1e-4)


def test_critical_radius_decreases_with_driving_force():
    """Higher supersaturation → smaller critical nucleus."""
    r1 = _critical_radius_m(0.1, 2e8)
    r2 = _critical_radius_m(0.1, 4e8)
    assert r2 < r1


def test_xeq_interpolation_clamps_outside_range():
    table = [(190, 0.0008), (230, 0.0028)]
    assert _interp_Xeq(table, 100) == 0.0008      # below
    assert _interp_Xeq(table, 300) == 0.0028      # above
    assert _interp_Xeq(table, 210) == pytest.approx(0.0018, rel=1e-3)   # interp


# ── 3. Edge-case refusals ────────────────────────────────────────────────────

def test_unknown_phase_returns_error():
    out = simulate_precipitation_sync({"Al": 96, "Cu": 4}, "made_up_phase", 200, 3600)
    assert out["value"] is None
    assert out["source"] == "kwn_no_phase"


def test_missing_solute_refuses():
    """Asking for Al-Cu θ' precipitation in pure Al should refuse."""
    out = simulate_precipitation_sync({"Al": 100.0}, "Al2Cu_theta_prime", 190, 3600)
    assert out["value"] is None
    assert out["source"] == "kwn_solute_missing"


def test_undersaturated_returns_zero_precipitate():
    """6061-like at very low temperature where Mg₂Si is undersaturated."""
    out = simulate_precipitation_sync(
        {"Al": 99.5, "Mg": 0.3, "Si": 0.2}, "Mg2Si_beta_doubleprime",
        100.0,    # below the Mg₂Si solvus for this composition
        3600,
    )
    # Either undersaturated label OR essentially-zero vf
    v = out.get("value") or {}
    assert out["source"] == "kwn_undersaturated" or v.get("volume_fraction", 0) < 0.001


# ── 4. Canonical kinetics — Sprint 5's acceptance criteria ──────────────────

@pytest.fixture(scope="module")
def runner_results():
    from apps.api.ml.precipitation.eval.precipitation_runner import run_all
    return run_all()


def test_pass_rate_at_least_70_percent(runner_results):
    """The canonical-kinetics set must pass at the documented tolerances."""
    pr = runner_results["pass_rate"]
    fails = [r["name"] for r in runner_results["results"] if r["outcome"] != "pass"]
    assert pr >= 0.70, f"KWN pass rate {pr:.0%} below 70 %; failures: {fails}"


def test_no_runtime_errors(runner_results):
    """No canonical case should crash the solver."""
    errs = [r for r in runner_results["results"] if r["outcome"] == "error"]
    assert not errs, [(r["name"], r.get("error")) for r in errs]


# ── 5. Trajectory invariants ─────────────────────────────────────────────────

def test_solute_concentration_is_monotone_decreasing():
    """X_α(t) must decrease monotonically as precipitates consume solute."""
    out = simulate_precipitation_sync(
        {"Al": 96.0, "Cu": 4.0}, "Al2Cu_theta_prime", 190.0, 8 * 3600,
    )
    X = out["trajectory"]["X_alpha"]
    for a, b in zip(X, X[1:]):
        assert b <= a + 1e-6, f"X_α not monotone: {a} → {b}"


def test_volume_fraction_is_monotone_non_decreasing():
    """vf(t) must rise monotonically (no shrinkage in this model)."""
    out = simulate_precipitation_sync(
        {"Al": 96.0, "Cu": 4.0}, "Al2Cu_theta_prime", 190.0, 8 * 3600,
    )
    vf = out["trajectory"]["vf"]
    for a, b in zip(vf, vf[1:]):
        assert b >= a - 1e-6, f"vf not monotone: {a} → {b}"


def test_mean_radius_is_monotone_non_decreasing():
    """r̄(t) only grows in KWN (no Ostwald reversal modelled)."""
    out = simulate_precipitation_sync(
        {"Al": 96.0, "Cu": 4.0}, "Al2Cu_theta_prime", 190.0, 8 * 3600,
    )
    r = out["trajectory"]["r_bar_nm"]
    # Allow tiny numerical noise at the very first step
    for i in range(2, len(r)):
        assert r[i] >= r[i-1] - 1e-3, f"r̄ shrank at step {i}: {r[i-1]} → {r[i]}"
