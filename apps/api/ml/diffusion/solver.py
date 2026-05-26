"""
Crank-Nicolson 1-D diffusion solver — Fick's 2nd law.

Why Crank-Nicolson rather than explicit FTCS:
    * Unconditionally stable — no dt < dx² / (2D) constraint, which
      otherwise forces sub-millisecond steps for typical Al-matrix
      diffusion at homogenisation temperatures.
    * Second-order accurate in time (vs first-order for FTCS) so the
      profile shape is preserved through the long homogenisation tail.

PDE:
    ∂c/∂t = D · ∂²c/∂x²,   x ∈ [0, L],   ∂c/∂x = 0 at x = 0, L

Discretisation (interior nodes i = 1 … N-2):
    (1 + α) c_i^{n+1} - α/2 (c_{i-1}^{n+1} + c_{i+1}^{n+1})
        = (1 - α) c_i^n + α/2 (c_{i-1}^n + c_{i+1}^n)
    α = D · dt / dx²

Boundary nodes use mirror ghost-points for the zero-flux BC, which
collapses the i = 0 and i = N-1 rows of the tridiagonal system to:
    (1 + α) c_0  - α c_1     = (1 - α) c_0^n + α c_1^n
    (1 + α) c_{N-1} - α c_{N-2} = (1 - α) c_{N-1}^n + α c_{N-2}^n

The system is tridiagonal — we solve via ``scipy.linalg.solve_banded``
which is O(N) per timestep.

References
──────────
* Crank, J. (1975) "The Mathematics of Diffusion," 2nd ed., Ch. 8
  (Crank-Nicolson scheme, error analysis, stability).
* Shewmon, P.G. (1989) "Diffusion in Solids," Ch. 1-2 for the matrix-
  solute D₀, Q literature values bundled in ``DIFFUSIVITY_DB``.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.linalg import solve_banded


# Universal gas constant, J / (mol·K).
R_GAS = 8.314_462_618


# ─── Literature diffusivity constants ─────────────────────────────────
# Keyed by ``"<solute>_in_<matrix-phase>"``.  Values from Brandes &
# Brook (1992) "Smithells Metals Reference Book," 7th ed., Ch. 13,
# and from Shewmon (1989) for the FCC-Ni and FCC-Fe entries.
#
# D₀ in m² / s,  Q in J / mol.  Validity range is the temperature
# window the assessment covers — extrapolation outside emits a warning
# at the API boundary.

DIFFUSIVITY_DB: dict[str, dict[str, Any]] = {
    "Mg_in_Al": {
        "label":          "Mg in Al (FCC)",
        "D0":             1.49e-5,    # m²/s
        "Q":              120_500.0,  # J/mol
        "valid_T_C":      (200, 660),
        "ref":            "Smithells 7e §13.1 (Al-Mg interdiffusion)",
    },
    "Cu_in_Al": {
        "label":          "Cu in Al (FCC)",
        "D0":             6.5e-5,
        "Q":              135_700.0,
        "valid_T_C":      (200, 660),
        "ref":            "Smithells 7e §13.1 (Al-Cu)",
    },
    "Zn_in_Al": {
        "label":          "Zn in Al (FCC)",
        "D0":             2.59e-5,
        "Q":              120_900.0,
        "valid_T_C":      (200, 660),
        "ref":            "Smithells 7e §13.1 (Al-Zn)",
    },
    "Mn_in_FeGamma": {
        "label":          "Mn in γ-Fe (austenite)",
        "D0":             1.78e-5,
        "Q":              261_000.0,
        "valid_T_C":      (900, 1300),
        "ref":            "Shewmon (1989) §2.5 (Fe-Mn austenite)",
    },
    "C_in_FeGamma": {
        "label":          "C in γ-Fe (austenite)",
        "D0":             2.0e-5,
        "Q":              140_000.0,
        "valid_T_C":      (700, 1300),
        "ref":            "Smithells 7e §13.6 (Fe-C carburising)",
    },
    "Cr_in_Ni": {
        "label":          "Cr in Ni (FCC)",
        "D0":             1.1e-4,
        "Q":              272_000.0,
        "valid_T_C":      (700, 1400),
        "ref":            "Shewmon (1989) §2.5 (Ni-Cr)",
    },
    "Al_in_Ni": {
        "label":          "Al in Ni (FCC)",
        "D0":             1.87e-4,
        "Q":              268_000.0,
        "valid_T_C":      (700, 1400),
        "ref":            "Smithells 7e §13.10 (Ni-Al)",
    },
}


def list_systems() -> list[dict[str, str]]:
    """Surface the catalogue for the frontend's dropdown."""
    return [
        {"key": key, "label": meta["label"], "ref": meta["ref"]}
        for key, meta in DIFFUSIVITY_DB.items()
    ]


def _arrhenius_D(D0: float, Q: float, T_K: float) -> float:
    """D(T) via Arrhenius — D = D₀ · exp(-Q / RT)."""
    return D0 * math.exp(-Q / (R_GAS * T_K))


def simulate_diffusion_curve(
    system:        str,
    T_C:           float,
    L_um:          float,
    c_left:        float,
    c_right:       float,
    total_time_s:  float,
    n_x:           int = 101,
    n_snapshots:   int = 50,
) -> dict:
    """Run a 1-D Crank-Nicolson diffusion couple and return the full
    time-resolved profile.

    Parameters
    ----------
    system : str
        Key into ``DIFFUSIVITY_DB`` (e.g. ``"Mg_in_Al"``).
    T_C : float
        Homogenisation temperature in °C.
    L_um : float
        Diffusion-couple length in μm.  The bar runs from 0 to L.
    c_left, c_right : float
        Initial concentrations on the two halves (wt% or at%; the
        solver is unit-agnostic — whatever you put in comes out).
    total_time_s : float
        Total simulated aging time.  Snapshots are log-spaced so
        the early transient is sampled densely.
    n_x : int, optional
        Number of spatial grid points (default 101).
    n_snapshots : int, optional
        Number of time snapshots to record (default 50).

    Returns
    -------
    dict
        ``{value, system, trajectory, inputs, warnings}`` — same shape
        family as the precipitation result, so the frontend can mirror
        the playback UX.
    """
    if system not in DIFFUSIVITY_DB:
        return {
            "error":  f"Unknown solute-matrix system '{system}'.",
            "source": "diffusion_fick_1d",
        }
    meta = DIFFUSIVITY_DB[system]
    T_K = T_C + 273.15
    D   = _arrhenius_D(meta["D0"], meta["Q"], T_K)

    L_m = L_um * 1e-6
    dx  = L_m / (n_x - 1)

    # Build the timestep grid.  Use ~400 internal CN steps regardless
    # of total time — Crank-Nicolson is unconditionally stable so we
    # don't need to chase a dt-stability bound, but smaller dt keeps
    # the Neumann-BC truncation error tight.
    n_steps    = 400
    dt         = total_time_s / n_steps
    alpha      = D * dt / (dx * dx)

    # Snapshot indices — log-spaced from step 1 (so the first nontrivial
    # snapshot has actually evolved) to the last step.
    snap_at = sorted(set(
        [0] +
        np.unique(
            np.round(np.logspace(
                math.log10(1), math.log10(n_steps), n_snapshots - 1,
            )).astype(int)
        ).tolist()
    ))[:n_snapshots]

    # Initial condition — step.
    c          = np.empty(n_x)
    mid        = n_x // 2
    c[:mid]    = c_left
    c[mid:]    = c_right

    # ─── Build the LHS tridiagonal matrix in banded form ────────────
    # solve_banded wants (l, u, ab) with ab shape (l + u + 1, n).  For
    # tridiagonal: l = u = 1, so ab is (3, n_x).
    # Row 0 (super-diagonal):    -α/2 each interior, 0 at extremes
    # Row 1 (main diagonal):     (1 + α) on interior, (1 + α) at boundaries
    # Row 2 (sub-diagonal):      -α/2 each interior
    # Boundary rows are special — Neumann BC mirror gives:
    #   row 0:        (1 + α) c_0 - α c_1 = …
    #   row N-1:      (1 + α) c_{N-1} - α c_{N-2} = …
    ab = np.zeros((3, n_x))
    ab[0, 1:]  = -alpha / 2     # super-diagonal
    ab[1, :]   = 1.0 + alpha    # main diagonal
    ab[2, :-1] = -alpha / 2     # sub-diagonal
    # Neumann-BC adjustments to the off-diagonals at i = 0 and i = N-1:
    ab[0, 1]    = -alpha    # super at i=0 is -α (mirror)
    ab[2, -2]   = -alpha    # sub at i=N-1 is -α (mirror)

    # ─── Time-march ─────────────────────────────────────────────────
    profiles   = [c.copy()]
    snap_times = [0.0]
    snap_set   = set(snap_at)

    for n in range(1, n_steps + 1):
        # RHS = (1 - α) c_i^n + α/2 (c_{i-1}^n + c_{i+1}^n)
        rhs              = (1.0 - alpha) * c
        rhs[1:-1]       += (alpha / 2) * (c[2:] + c[:-2])
        rhs[0]          += alpha * c[1]      # mirror BC
        rhs[-1]         += alpha * c[-2]
        c = solve_banded((1, 1), ab, rhs)

        if n in snap_set:
            profiles.append(c.copy())
            snap_times.append(n * dt)

    # ─── Outputs ────────────────────────────────────────────────────
    x_um             = (np.linspace(0, L_m, n_x) * 1e6).tolist()
    # Final diffusion length: characteristic 2√(D t) penetration.
    L_diff_final_um  = 2.0 * math.sqrt(D * total_time_s) * 1e6
    # Per-snapshot √(Dt) so the frontend can overlay it on the chart.
    sqrt_Dt_um       = [2.0 * math.sqrt(D * t) * 1e6 for t in snap_times]

    # Validity check.
    valid_lo, valid_hi = meta["valid_T_C"]
    warnings: list[str] = []
    if T_C < valid_lo or T_C > valid_hi:
        warnings.append(
            f"T={T_C}°C is outside the {meta['label']} assessment range "
            f"({valid_lo}-{valid_hi}°C); extrapolated D may be unreliable."
        )
    if L_diff_final_um < 0.05 * L_um:
        warnings.append(
            "Diffusion length ≪ couple length — increase time or T to "
            "see meaningful evolution.  Currently nothing has moved."
        )
    if L_diff_final_um > 1.5 * L_um:
        warnings.append(
            "Diffusion length ≫ couple length — composition is nearly "
            "homogenised.  Mean concentration = (c_left + c_right) / 2."
        )

    return {
        "value": {
            "D_m2_s":           float(D),
            "T_C":              T_C,
            "total_time_s":     total_time_s,
            "L_um":             L_um,
            "diffusion_length_final_um": L_diff_final_um,
        },
        "system":   system,
        "label":    meta["label"],
        "source":   "fick_1d_crank_nicolson",
        "trajectory": {
            "x_um":         x_um,
            "times_s":      snap_times,
            # 2-D nested list: ``c_profiles[t_idx][x_idx]``.
            "c_profiles":   [p.tolist() for p in profiles],
            "sqrt_Dt_um":   sqrt_Dt_um,
        },
        "inputs": {
            "c_left":           c_left,
            "c_right":          c_right,
            "n_x":              n_x,
            "n_snapshots":      len(profiles),
            "D0_m2_s":          meta["D0"],
            "Q_J_per_mol":      meta["Q"],
            "ref":              meta["ref"],
        },
        "warnings": warnings,
    }
