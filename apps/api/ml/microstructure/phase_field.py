"""
apps.api.ml.microstructure.phase_field
=======================================

Kobayashi-Warren-Carter (1996) phase-field model for **pure-substance**
dendritic solidification.  Implemented with FiPy (NIST, public domain).

This is the textbook 2D phase-field benchmark — the same model used in
NIST's CHiMaD benchmarks and in many materials-science PhD theses.

What it simulates
-----------------
* Two coupled PDEs:
    τ ∂φ/∂t = ∇·(ε² ∇φ) + φ(1-φ)(φ - 0.5 + m(T))      (phase field)
    ∂U/∂t   = D ∇²U + K ∂φ/∂t                         (temperature)
  where φ ∈ [0,1] is the order parameter (0 = liquid, 1 = solid),
  U is dimensionless temperature, and m(T) is the driving force.
* Crystalline anisotropy via an N-fold symmetry term in ε(θ):
    ε(θ) = ε̄ [1 + c cos(N(θ - θ₀))]

Limitations (be honest with the user)
-------------------------------------
* **Pure substance**: no solute (Al-Cu segregation would need a coupled
  solute PDE; that's a Sprint 2.6 extension).
* **2D**: real dendrite competition is 3D.  The 2D slice is morphologically
  representative but geometrically biased (more side-branching than reality).
* **Schematic, not quantitative**: parameters are dimensionless.  Time on
  the simulation is "simulation time", not a physical wall-clock duration.
  See `simulate_dendrite` docstring for the scaling.

References
----------
* Kobayashi, R., *Physica D* 63 (1993) 410-423.
* Warren & Boettinger, *Acta Metall.* 43 (1995) 689-703.
* NIST CHiMaD benchmark suite (open repo).
"""
from __future__ import annotations

import io
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# Default Kobayashi-Warren-Carter parameters (Kobayashi 1993 Table 1, with
# anisotropy strength tuned up to 0.04 for visible six-arm dendrite tips).
DEFAULT_PARAMS: dict[str, float] = {
    "alpha":   0.015,    # m(T) prefactor
    "c":       0.04,     # anisotropy strength (≥ 0.04 needed for dendrite arms)
    "N":       6.0,      # N-fold symmetry (6 for hex/FCC dendrite tips)
    "theta_0": 0.0,      # crystallographic offset (radians)
    "kappa1":  0.9,      # driving-force prefactor
    "kappa2":  20.0,     # driving-force sharpness
    "tau":     3.0e-4,   # interface relaxation time
    "eps_bar": 0.01,     # gradient energy coefficient
    "K":       1.5,      # latent-heat coupling
    "D":       1.0,      # thermal diffusivity (dimensionless)
}


def run_kwc(
    grid: int = 100,
    n_steps: int = 800,
    n_frames: int = 12,
    dt: float = 5.0e-5,
    dx: float = 0.025,
    seed_radius_cells: int = 4,
    params: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Run the KWC dendrite simulation and return frames + metadata.

    Parameters
    ----------
    grid : int
        Square-grid resolution (NxN cells).  100 is a good balance of
        speed and visible side-branching.
    n_steps : int
        Total number of explicit time steps.
    n_frames : int
        Number of snapshots to return (log-spaced over the run).
    dt, dx : float
        Time and space step (dimensionless).  Default from Kobayashi 1993.
    seed_radius_cells : int
        Initial solid-seed radius in grid cells.
    params : dict[str, float] | None
        Override any of the DEFAULT_PARAMS.

    Returns
    -------
    dict
        ``frames``  list of ``{step, time, phi_grid, T_grid, solid_fraction}``
        ``metadata`` dict with run settings and derived measurements
    """
    from fipy import (
        CellVariable, Grid2D, TransientTerm, DiffusionTerm,
        ImplicitSourceTerm, numerix,
    )
    import warnings
    warnings.filterwarnings("ignore")

    p = {**DEFAULT_PARAMS, **(params or {})}

    mesh = Grid2D(dx=dx, dy=dx, nx=grid, ny=grid)
    phi  = CellVariable(name="phase",       mesh=mesh, value=0.0, hasOld=True)
    # Initial bath: undercooled liquid.  T₀ = -0.3 is a moderate undercooling
    # that grows a six-arm dendrite over ~500 steps without filling the grid.
    T_initial = -0.3
    T    = CellVariable(name="temperature", mesh=mesh, value=T_initial, hasOld=True)

    # Circular seed in the centre
    x, y = mesh.cellCenters
    cx, cy = grid * dx / 2, grid * dx / 2
    r2 = (x - cx) ** 2 + (y - cy) ** 2
    phi.setValue(1.0, where=r2 < (seed_radius_cells * dx) ** 2)

    # Anisotropic gradient energy
    psi   = p["theta_0"] + numerix.arctan2(phi.faceGrad[1], phi.faceGrad[0])
    eps   = p["eps_bar"] * (1.0 + p["c"] * numerix.cos(p["N"] * psi))

    m_phi = phi - 0.5 - (p["kappa1"] / numerix.pi) * numerix.arctan(p["kappa2"] * T)

    phi_eq = (
        TransientTerm(coeff=p["tau"])
        == DiffusionTerm(coeff=eps ** 2)
        + ImplicitSourceTerm(coeff=(phi - 0.5 - m_phi) * (1 - phi - m_phi))
    )
    T_eq = TransientTerm() == DiffusionTerm(coeff=p["D"]) + (phi - phi.old) * p["K"]

    # Frame-capture strategy: hit explicit solid-fraction milestones.
    # KWC dendrite growth is non-linear in step count — once the tip forms,
    # the solid fraction explodes from ~5% to 100% in a few dozen steps.
    # Sampling by milestone (rather than by fixed step interval) gives a
    # smooth animation: seed → first arms → secondary branches → mature
    # dendrite → impingement.
    target_fractions = np.linspace(0.005, 0.45, n_frames).tolist()
    next_milestone_idx = 0
    STOP_SOLID_FRACTION = 0.45

    frames: list[dict] = []
    # Always include the initial state for context.
    phi_arr = np.array(phi.value, dtype=np.float32).reshape(grid, grid)
    T_arr   = np.array(T.value,   dtype=np.float32).reshape(grid, grid)
    initial_sf = float((phi_arr > 0.5).mean())
    frames.append({"step": 0, "time": 0.0, "phi": phi_arr, "T": T_arr,
                   "solid_fraction": round(initial_sf, 4)})

    for step in range(1, n_steps + 1):
        phi.updateOld(); T.updateOld()
        phi_eq.solve(var=phi, dt=dt)
        T_eq.solve(var=T, dt=dt)

        # Only check the cell-values occasionally (cheap proxy)
        if step % 5 != 0:
            continue
        phi_arr = np.array(phi.value, dtype=np.float32).reshape(grid, grid)
        solid_fraction = float((phi_arr > 0.5).mean())
        # Save *one* frame per check that crosses any number of milestones —
        # advance the cursor through all crossed milestones at once.
        if next_milestone_idx < len(target_fractions) \
           and solid_fraction >= target_fractions[next_milestone_idx]:
            T_arr = np.array(T.value, dtype=np.float32).reshape(grid, grid)
            frames.append({
                "step": step,
                "time": round(step * dt, 6),
                "phi": phi_arr.copy(),
                "T":   T_arr.copy(),
                "solid_fraction": round(solid_fraction, 4),
            })
            while (next_milestone_idx < len(target_fractions)
                   and solid_fraction >= target_fractions[next_milestone_idx]):
                next_milestone_idx += 1
        if solid_fraction > STOP_SOLID_FRACTION:
            break

    # ── Derived measurements ─────────────────────────────────────────────
    # Dendrite radial extent: half the distance between the two solid pixels
    # furthest from the centre, along the horizontal axis (cheap proxy).
    final = frames[-1]
    phi_final = final["phi"]
    solid_mask = phi_final > 0.5
    if solid_mask.any():
        idxs = np.argwhere(solid_mask)
        cy_pix, cx_pix = grid // 2, grid // 2
        dists = np.sqrt((idxs[:, 0] - cy_pix) ** 2 + (idxs[:, 1] - cx_pix) ** 2)
        max_radius_cells = float(dists.max())
        dendrite_extent_um = round(max_radius_cells * dx, 3)
    else:
        max_radius_cells   = 0.0
        dendrite_extent_um = 0.0

    # Tip velocity (cells per time unit, then to um/time)
    tip_velocity = (
        (max_radius_cells - seed_radius_cells) * dx / (n_steps * dt)
        if n_steps > 0 else 0.0
    )

    metadata = {
        "grid": grid,
        "n_steps": n_steps,
        "dt": dt,
        "dx": dx,
        "n_frames_returned": len(frames),
        "total_sim_time": round(n_steps * dt, 6),
        "final_solid_fraction": frames[-1]["solid_fraction"],
        "dendrite_radial_extent_dimless": dendrite_extent_um,
        "tip_velocity_dimless_per_step": round(tip_velocity, 6),
        "params": p,
    }
    return {"frames": frames, "metadata": metadata}
