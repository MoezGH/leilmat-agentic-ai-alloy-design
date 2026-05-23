"""
apps.api.ml.microstructure.solidification
==========================================

Public ``simulate_dendrite()`` — runs the KWC phase-field and renders each
frame as a base64-encoded PNG ready for the frontend.

The function is intentionally narrow: pure substance, 2D, schematic.
Compositional coupling enters only via:
* ``crystal_symmetry``: N-fold anisotropy order (6 = FCC/HCP dendrite tips,
  4 = tetragonal/BCC <100> growth, 3 = trigonal)
* ``orientation_deg``: rotation of the crystallographic axis
* ``undercooling_factor``: scales the driving force (proxy for ΔT/ΔT_eq)

Honest framing
--------------
The response carries ``source: "phase_field_kwc"`` and
``calibration: "schematic"`` so users (and the rest of the app) know this
is a morphological visualisation, not a quantitative property prediction.

For a quantitative prediction of dendrite arm spacing, scaling laws (e.g.
Trivedi-Kurz) or commercial codes (MICRESS, ProCAST) are needed.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import logging
import math
from typing import Any

import numpy as np

from apps.api.ml.microstructure.phase_field import run_kwc, DEFAULT_PARAMS

logger = logging.getLogger(__name__)

# Small LRU cache — phase-field runs are 10-60 s
_CACHE: dict[str, dict] = {}
_CACHE_MAX = 16


def _phi_to_png(
    phi: np.ndarray,
    T: np.ndarray | None = None,
    show_temperature: bool = True,
) -> str:
    """Render a 2D phi grid as a base64-encoded PNG.

    Solid (phi > 0.5) renders in a teal-cyan gradient; liquid stays dark
    with a faint thermal halo when ``T`` is provided.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list(
        "leilmat_dendrite",
        [
            (0.00, "#000713"),   # deep liquid
            (0.30, "#0a2540"),
            (0.49, "#0e3a5f"),
            (0.51, "#22d3ee"),   # crisp interface
            (0.65, "#67e8f9"),
            (1.00, "#ccfbf1"),   # solid core
        ],
    )

    fig = plt.figure(figsize=(3.2, 3.2), dpi=128)
    ax  = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.imshow(phi, cmap=cmap, vmin=0.0, vmax=1.0, interpolation="bilinear", origin="lower")
    if show_temperature and T is not None:
        # Faint thermal halo overlay in the liquid
        from matplotlib.colors import Normalize
        norm = Normalize(vmin=float(T.min()), vmax=float(T.max()) + 1e-6)
        ax.imshow(T, cmap="inferno", alpha=0.12, norm=norm,
                  interpolation="bilinear", origin="lower")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0,
                facecolor="#000713")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _cache_key(payload: dict) -> str:
    return hashlib.md5(
        repr(sorted(payload.items())).encode()
    ).hexdigest()[:16]


def _simulate(
    crystal_symmetry: int,
    orientation_deg: float,
    undercooling_factor: float,
    grid: int,
    n_steps: int,
    n_frames: int,
) -> dict[str, Any]:
    """Blocking phase-field call.  MUST be run in a worker thread."""
    # Map UI knobs onto KWC parameters
    params = dict(DEFAULT_PARAMS)
    params["N"]       = float(max(2, min(12, crystal_symmetry)))
    params["theta_0"] = math.radians(orientation_deg)
    # Stronger undercooling → larger κ1 ⇒ faster, sharper dendrite
    params["kappa1"]  = 0.9 * max(0.3, min(2.5, undercooling_factor))

    result = run_kwc(
        grid=grid, n_steps=n_steps, n_frames=n_frames, params=params,
    )

    frames_out: list[dict] = []
    for f in result["frames"]:
        frames_out.append({
            "step": f["step"],
            "sim_time": f["time"],
            "solid_fraction": f["solid_fraction"],
            "png": _phi_to_png(f["phi"], f["T"], show_temperature=True),
        })

    return {
        "frames": frames_out,
        "metadata": result["metadata"],
        "source": "phase_field_kwc",
        "calibration": "schematic",
        "warnings": [
            "2D pure-substance KWC phase-field; no solute coupling.",
            "Time units are dimensionless (simulation time, not seconds).",
            "Render is morphologically representative, not quantitative.",
        ],
    }


async def simulate_dendrite(
    composition: dict[str, float] | None = None,
    T_C: float | None = None,
    crystal_symmetry: int = 6,
    orientation_deg: float = 0.0,
    undercooling_factor: float = 1.0,
    grid: int = 100,
    n_steps: int = 800,
    n_frames: int = 12,
) -> dict[str, Any]:
    """Async wrapper: runs the phase-field in a thread and returns PNG frames.

    Parameters
    ----------
    composition, T_C : optional
        Carried through to ``metadata`` for provenance.  Future versions
        will use them to set the anisotropy order automatically.
    crystal_symmetry : int, default 6
        N-fold dendrite-tip symmetry.  6 = FCC/HCP, 4 = tetragonal/BCC
        <100>, 3 = trigonal.  Range 2-12.
    orientation_deg : float, default 0
        Crystallographic rotation (the "easy" growth direction).
    undercooling_factor : float, default 1.0
        Proxy for ΔT/ΔT_equilibrium.  Larger = faster, sharper dendrites.
    grid : int, default 100
        Square-grid size (NxN cells).
    n_steps : int, default 800
        Number of explicit time steps.  ~30 s wall-clock for grid=100,
        n_steps=800 on a modern CPU.
    n_frames : int, default 12
        Number of frames to capture (log-spaced over the run).
    """
    payload = {
        "crystal_symmetry": int(crystal_symmetry),
        "orientation_deg": round(orientation_deg, 1),
        "undercooling_factor": round(undercooling_factor, 2),
        "grid": int(grid),
        "n_steps": int(n_steps),
        "n_frames": int(n_frames),
    }
    key = _cache_key(payload)
    if key in _CACHE:
        cached = _CACHE[key]
        cached["metadata"]["composition"] = composition
        cached["metadata"]["T_C"] = T_C
        cached["metadata"]["cache_hit"] = True
        return cached

    try:
        result = await asyncio.to_thread(_simulate, **payload)
    except Exception as exc:
        logger.exception("phase-field simulation failure")
        return {
            "frames": [], "metadata": {},
            "source": "phase_field_kwc", "calibration": "schematic",
            "warnings": [], "error": str(exc),
        }

    result["metadata"]["composition"] = composition
    result["metadata"]["T_C"] = T_C
    result["metadata"]["cache_hit"] = False

    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = result
    return result


def simulate_dendrite_sync(**kwargs) -> dict[str, Any]:
    """Synchronous wrapper for tests / CLI."""
    composition = kwargs.pop("composition", None)
    T_C = kwargs.pop("T_C", None)
    payload = {
        "crystal_symmetry":   int(kwargs.get("crystal_symmetry", 6)),
        "orientation_deg":    round(float(kwargs.get("orientation_deg", 0.0)), 1),
        "undercooling_factor": round(float(kwargs.get("undercooling_factor", 1.0)), 2),
        "grid":               int(kwargs.get("grid", 100)),
        "n_steps":            int(kwargs.get("n_steps", 800)),
        "n_frames":           int(kwargs.get("n_frames", 12)),
    }
    key = _cache_key(payload)
    if key in _CACHE:
        cached = _CACHE[key]
        cached["metadata"]["composition"] = composition
        cached["metadata"]["T_C"] = T_C
        cached["metadata"]["cache_hit"] = True
        return cached

    result = _simulate(**payload)
    result["metadata"]["composition"] = composition
    result["metadata"]["T_C"] = T_C
    result["metadata"]["cache_hit"] = False

    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = result
    return result
