"""
apps.api.ml.precipitation.kwn
==============================

Kampmann-Wagner-Numerical (KWN) precipitation-kinetics solver.

State variables (per-phase, spherical-equivalent):
    N       : number density of precipitates per m³
    r_bar   : volume-weighted mean radius (m)

PDE we integrate (Robson, Acta Mater. 52 (2004) 4669, §2):
    dN/dt = J(t)                                                  (nucleation)
    d(r_bar)/dt = ⟨v_growth⟩ + ⟨v_coarsening⟩                     (growth + LSW)

where
    J(t)             = N₀ Z β* exp(−ΔG* / kT)                    (classical CNT)
    ΔG*              = (16π/3) · γ³ / (ΔG_v)²                     (nucleation barrier)
    v_growth         = D (X_α − X_α^r) / r / (X_β − X_α^r)         (Zener-like)
    v_coarsening     = (8 γ D V_m X_α^eq) / (9 R T (X_β − X_α^eq) r²)   (LSW)

Mass balance closure: the matrix solute X_α(t) is updated from the
ever-growing precipitate volume via
    X_α(t) = X_α^0 − f_v(t) · (X_β − X_α(t))   (linearised; ok for f_v ≲ 0.10)

with f_v = (4/3) π r̄³ N.

Caveats baked in
----------------
* Spherical equivalent — real θ'/γ" are plates / disks.  We report
  ``effective_radius_nm`` and label this in the response.
* Mean-field, single-population — no full PSD evolution.
* Heterogeneous nucleation on dislocations/grain boundaries is folded into
  the pre-exponential by tuning N₀ to match the canonical set's volume
  fractions.  This is the same calibration trick JMatPro uses.

Public API
----------
``simulate_precipitation(composition, phase, T_C, aging_time_s)``
    Async wrapper.
``simulate_precipitation_sync(...)``
    Synchronous version for tests / CLI.
``simulate_curve(...)``
    Time-resolved (vf(t), r(t)) for plotting.
"""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Any, Optional

import numpy as np

from apps.api.ml.precipitation.interfacial_energy import (
    PRECIPITATE_DATA, available_phases,
)

logger = logging.getLogger(__name__)

# ── Physical constants ──────────────────────────────────────────────────────
_R          = 8.314_462       # J / (mol K)
_kB         = 1.380_649e-23   # J / K
_NA         = 6.022_140_76e23 # / mol


# ── Helpers ─────────────────────────────────────────────────────────────────

def _interp_Xeq(table: list, T_C: float) -> float:
    """Linear interpolation / clamped extrapolation of (T, X_eq) pairs."""
    pts = sorted(table)
    if T_C <= pts[0][0]:
        return float(pts[0][1])
    if T_C >= pts[-1][0]:
        return float(pts[-1][1])
    for (T0, X0), (T1, X1) in zip(pts, pts[1:]):
        if T0 <= T_C <= T1:
            f = (T_C - T0) / (T1 - T0)
            return float(X0 + f * (X1 - X0))
    return float(pts[-1][1])


def _solute_atom_fraction(composition: dict, solute: str) -> float:
    """Approximate atom fraction of ``solute`` in the composition.

    Composition is in weight percent; convert to atomic % using
    ``apps.api.ml.alloy_datasets.weight_to_atomic``.  We tolerate missing
    elements (returns 0).
    """
    from apps.api.ml.alloy_datasets import weight_to_atomic
    try:
        at = weight_to_atomic(composition)
    except Exception:
        return 0.0
    return float(at.get(solute, 0.0)) / 100.0


def _diffusivity_m2_s(D0: float, Q: float, T_K: float) -> float:
    return D0 * math.exp(-Q / (_R * T_K))


# ── Driving force ───────────────────────────────────────────────────────────

def _chemical_driving_force_J_m3(X_alpha: float, X_eq: float, X_beta: float,
                                  V_m: float, T_K: float) -> float:
    """Chemical driving force per unit volume of precipitate.

    Mean-field dilute-solution form:
        ΔG_v = − (RT / V_m) · ln(X_α / X_eq)        (when X_α > X_eq)

    Note this is positive when the matrix is supersaturated (i.e. when
    X_α > X_eq), driving precipitation.  Returns 0 when below saturation.
    """
    if X_alpha <= X_eq:
        return 0.0
    return _R * T_K * math.log(X_alpha / X_eq) / V_m


def _nucleation_barrier_J(gamma: float, dG_v_J_m3: float) -> float:
    """ΔG* for a homogeneous spherical critical nucleus."""
    if dG_v_J_m3 <= 0:
        return float("inf")
    return (16.0 * math.pi / 3.0) * (gamma ** 3) / (dG_v_J_m3 ** 2)


def _critical_radius_m(gamma: float, dG_v_J_m3: float) -> float:
    if dG_v_J_m3 <= 0:
        return float("inf")
    return 2.0 * gamma / dG_v_J_m3


def _nucleation_rate_per_m3_s(
    N0_per_m3: float, gamma: float, dG_v_J_m3: float,
    D: float, X_alpha: float, T_K: float, a_lat_m: float = 4.04e-10,
) -> float:
    """Classical nucleation rate.

    J = N₀ · β* · Z · exp(− ΔG* / k_B T)

    β* = (4 π r*² D X_α) / a⁴   (atomic attachment frequency)
    Z  = √(ΔG* / 3π k_B T)      (Zeldovich correction)  ≈ 0.05–0.1
    """
    if dG_v_J_m3 <= 0:
        return 0.0
    dG_star = _nucleation_barrier_J(gamma, dG_v_J_m3)
    r_star  = _critical_radius_m(gamma, dG_v_J_m3)
    beta_star = 4.0 * math.pi * (r_star ** 2) * D * X_alpha / (a_lat_m ** 4)
    Z = math.sqrt(dG_star / (3.0 * math.pi * _kB * T_K)) if dG_star > 0 else 0.0
    exponent = -dG_star / (_kB * T_K)
    # Guard against overflow / underflow
    if exponent < -300:
        return 0.0
    return N0_per_m3 * beta_star * Z * math.exp(exponent)


# ── Main solver ──────────────────────────────────────────────────────────────

def simulate_curve(
    composition: dict,
    phase: str,
    T_C: float,
    aging_time_s: float,
    n_steps: int = 400,
    N0_per_m3: float = 1.0e26,         # heterogeneous site density (calibrated)
) -> dict[str, Any]:
    """Run the KWN solve and return time-resolved arrays.

    Parameters
    ----------
    composition   : dict[str, float]
        Weight-percent composition.
    phase : str
        Key into :data:`PRECIPITATE_DATA`.
    T_C : float
        Isothermal aging temperature in Celsius.
    aging_time_s : float
        Total aging time in seconds.
    n_steps : int
        Number of time points (log-spaced over the run for efficient
        capture of the early nucleation transient).
    N0_per_m3 : float
        Pre-exponential nucleation-site density.  Treated as a coarse
        knob; default value is calibrated against the canonical set.
    """
    if phase not in PRECIPITATE_DATA:
        return {
            "value": None, "source": "kwn_no_phase",
            "error": f"Unknown precipitate phase {phase!r}.  "
                     f"Available: {available_phases()}",
        }

    p   = PRECIPITATE_DATA[phase]
    T_K = T_C + 273.15

    # Initial matrix solute (atomic fraction)
    X0 = _solute_atom_fraction(composition, p["solute"])
    if X0 <= 0:
        return {
            "value": None, "source": "kwn_solute_missing",
            "error": f"Composition does not contain {p['solute']!r}; "
                     f"cannot nucleate {phase}.",
        }

    X_eq   = _interp_Xeq(p["Xeq_T_C"], T_C)
    if X_eq >= X0:
        return {
            "value": {"volume_fraction": 0.0, "mean_radius_nm": 0.0,
                      "number_density_per_m3": 0.0},
            "source": "kwn_undersaturated",
            "X_alpha_initial": round(X0, 5),
            "X_eq_at_T":       round(X_eq, 5),
            "note": (f"Matrix solute X_α({p['solute']})={X0:.4f} is below "
                     f"equilibrium X_eq={X_eq:.4f} at {T_C} °C; "
                     "no precipitation driving force."),
        }

    # Saturated solid-solution concentration in the precipitate (assumed
    # stoichiometric ~1 — most precipitates are concentrated phases).
    # For dilute precipitates this could be lowered; doesn't qualitatively
    # change the kinetics.
    X_beta = 0.25 if phase.startswith("Al2Cu") else 0.50

    # Effective diffusivity = thermal D × vacancy/pipe enhancement.
    # Bulk Cu-in-Al at 190 °C is ~3·10⁻²⁰ m²/s; experimentally observed
    # θ' kinetics correspond to D_eff ≈ 10⁻¹⁶–10⁻¹⁷ m²/s (Bourgeois 2011).
    # The enhancement factor absorbs quenched-in vacancies + pipe diffusion
    # along dislocations — the standard "kinetic accelerator" in low-T
    # KWN literature (Robson 2004, Wagner-Kampmann 1991).
    D_thermal = _diffusivity_m2_s(p["D0_m2_s"], p["Q_J_mol"], T_K)
    D = D_thermal * p.get("vacancy_enhancement", 1.0)
    gamma = p["gamma_J_m2"]
    V_m   = p["V_m_m3_mol"]
    a_lat = 4.04e-10 if p["matrix"] in ("Al", "Ni") else 2.95e-10

    # Log-spaced time grid (much finer at early times)
    t0 = max(1.0, aging_time_s * 1e-4)
    times = np.concatenate([
        np.array([0.0]),
        np.logspace(math.log10(t0), math.log10(aging_time_s), n_steps - 1),
    ])

    # State arrays
    N      = np.zeros_like(times)
    r_bar  = np.zeros_like(times)
    X_alpha = np.zeros_like(times)
    X_alpha[0] = X0

    for i in range(1, len(times)):
        dt = times[i] - times[i - 1]

        # Update driving force from current matrix
        dG_v = _chemical_driving_force_J_m3(X_alpha[i-1], X_eq, X_beta, V_m, T_K)
        r_star = _critical_radius_m(gamma, dG_v)

        # ── Nucleation ──
        J = _nucleation_rate_per_m3_s(
            N0_per_m3, gamma, dG_v, D, X_alpha[i-1], T_K, a_lat,
        )
        dN = J * dt

        # ── Growth + coarsening ──
        r_prev = r_bar[i-1] if r_bar[i-1] > 1e-12 else max(r_star, 1e-9)
        # Zener-like diffusion-controlled growth
        if X_beta > X_alpha[i-1]:
            v_growth = (D * (X_alpha[i-1] - X_eq)
                        / (r_prev * (X_beta - X_alpha[i-1])))
        else:
            v_growth = 0.0
        # LSW coarsening (kicks in once r̄ ≫ r*)
        v_coarsen = ((8.0 * gamma * D * V_m * X_eq)
                     / (9.0 * _R * T_K * (X_beta - X_eq) * r_prev ** 2))
        # Decompose: when there's a real driving force growth dominates; once
        # X_α → X_eq coarsening takes over (LSW r̄³ ∝ t).  Use a simple
        # supersaturation-weighted average so the transition is smooth.
        if dG_v > 0:
            w = min(1.0, max(0.0, (X_alpha[i-1] - X_eq) / max(X0 - X_eq, 1e-9)))
            dr = (w * v_growth + (1.0 - w) * v_coarsen) * dt
        else:
            dr = v_coarsen * dt

        # Nucleation contribution to mean radius (use weighted average)
        if N[i-1] + dN > 0 and dN > 0:
            r_new_from_nucleation = max(r_star, 1e-9)
            r_after_growth = r_prev + dr
            r_bar[i] = ((N[i-1] * r_after_growth + dN * r_new_from_nucleation)
                        / (N[i-1] + dN))
        else:
            r_bar[i] = r_prev + dr

        N[i] = N[i-1] + dN

        # ── Mass balance: matrix concentration depletion ──
        vf_now = (4.0 / 3.0) * math.pi * (r_bar[i] ** 3) * N[i]
        # Limit volume fraction to physically achievable
        vf_now = min(vf_now, X0 / X_beta)
        # Conservation of solute atoms:  X_α (1 − f_v) + X_β f_v = X₀
        X_alpha[i] = max(X_eq, (X0 - X_beta * vf_now) / (1.0 - vf_now + 1e-12))

    # Final volume fraction
    vf = (4.0 / 3.0) * math.pi * (r_bar[-1] ** 3) * N[-1]
    vf = min(vf, X0 / X_beta)

    return {
        "value": {
            "volume_fraction":        round(vf, 6),
            "mean_radius_nm":         round(r_bar[-1] * 1e9, 3),
            "number_density_per_m3":  float(N[-1]),
            "aging_temperature_C":    T_C,
            "aging_time_s":           aging_time_s,
        },
        "phase":           phase,
        "morphology":      p.get("morphology"),
        "source":          "kwn_robson_2004",
        "calibration":     "literature_gamma",
        "trajectory": {
            "times_s":     times.tolist(),
            "vf":          [(4/3) * math.pi * r**3 * n for r, n in zip(r_bar, N)],
            "r_bar_nm":    (r_bar * 1e9).tolist(),
            "X_alpha":     X_alpha.tolist(),
        },
        "inputs": {
            "X_alpha_initial":   round(X0, 5),
            "X_eq_at_T":         round(X_eq, 5),
            "D_m2_s":            float(D),
            "gamma_J_m2":        gamma,
            "V_m_m3_mol":        V_m,
            "T_K":               round(T_K, 1),
            "N0_per_m3":         N0_per_m3,
        },
        "warnings": [
            "Mean-field spherical-equivalent KWN; reports r̄ = volume-weighted mean.",
            "Real morphology may be platelet/needle/disk — see `morphology`.",
        ],
    }


def simulate_precipitation_sync(
    composition: dict,
    phase: str,
    T_C: float,
    aging_time_s: float,
) -> dict[str, Any]:
    """Synchronous KWN simulation — returns final {vf, r̄, N}."""
    return simulate_curve(composition, phase, T_C, aging_time_s)


async def simulate_precipitation(
    composition: dict,
    phase: str,
    T_C: float,
    aging_time_s: float,
) -> dict[str, Any]:
    """Async wrapper for use behind FastAPI endpoints."""
    return await asyncio.to_thread(
        simulate_curve, composition, phase, T_C, aging_time_s,
    )
