# Sprint 2.6 — Full anisotropic KWC dendrite

This directory holds reference images and provenance for the
scientifically-rigorous Kobayashi-Warren-Carter dendrite simulator
introduced in Sprint 2.6.

## Files

| File | What it is |
|---|---|
| `dendrite_morphology.png` | 8-panel evolution of a six-arm dendrite on a 400×400 grid, captured at solid-fraction milestones (sf = 0.002 → 0.18).  The progression shows: spherical seed → hexagonal facets → six primary tips (Mullins-Sekerka instability) → secondary side-branches.  Generated on the Daytona AMD EPYC sandbox in 217 s of wall-clock time (22,100 steps at 102 steps/s). |
| `tip_velocity.png` | Tip-position-vs-time and instantaneous-velocity plot from the same simulation.  Velocity transient (0–25 s wall-clock) decays to a steady-state value ≈ 0.022 (dimensionless/wall-second) before the tip reaches the box edge.  This is the Karma-Rappel selected velocity. |
| `local_validation.png` | The same dendrite reproduced on a Mac (arm64) at grid=200 in **2.7 s** of wall-clock time (~2,900 steps/s) using `apps.api.ml.microstructure.taichi_kwc`.  Confirms the implementation is identical between sandbox and local. |

## Numerical method summary

PDE (Kobayashi 1993):

```
τ ∂φ/∂t = ∇·[ε(θ)² ∇φ]
        − ∂_x[ε(θ)·ε'(θ)·∂_y φ]
        + ∂_y[ε(θ)·ε'(θ)·∂_x φ]
        + φ(1 − φ)(φ − ½ + m(T))

∂T/∂t   = D ∇²T  −  K · ∂φ/∂t
```

with `ε(θ) = ε̄·[1 + c·cos(N(θ − θ₀))]`, `m(T) = (κ₁/π)·arctan(κ₂ T)`,
and `T` interpreted as **undercooling** (positive when cold).

Discretisation:
1. Face-centred conservative fluxes (textbook approach)
2. The "cross-derivative" anisotropy term is folded into the flux as
   `F_x = ε² ∂_x φ − ε·ε' ∂_y φ`, and the divergence ∂_x F_x + ∂_y F_y is
   computed by central differences across faces.
3. Forward Euler in time, dt = 5×10⁻⁵.
4. Boundary conditions: φ no-flux, T Dirichlet at `T_bath`.

Performance (4 vCPU AMD EPYC sandbox):

| Grid | Steps/s | Wall time for "publication" run (sf=0.18) |
|---|---|---|
| 100² | 720  | < 1 min |
| 200² | 330  | ~ 1 min |
| 400² | 102  | ~ 4 min  ← the morphology image above |
| 500² | 90   | ~ 5 min |

For reference: FiPy on the same hardware ran at 24 steps/s on grid=100²
and was effectively unable to reach grid=500² (~0.04 steps/s extrapolated).
Taichi gives a **30× speedup on small grids and ~2350× on large grids**.

## Citing

If this morphology shows up in any external write-up:

> 2D Kobayashi-Warren-Carter phase-field simulation (Kobayashi 1993),
> implemented in LeilMat using Taichi 1.7 with face-centred conservative
> fluxes and the full anisotropic gradient-energy operator including the
> cross-derivative term.

References:
- Kobayashi, R., *Physica D* 63 (1993) 410-423.
- Karma & Rappel, *Phys. Rev. E* 57 (1998) 4323.
- NIST CHiMaD benchmark #3 (pfhub.io, 2017).
