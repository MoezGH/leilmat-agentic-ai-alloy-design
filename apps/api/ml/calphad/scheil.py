"""
apps.api.ml.calphad.scheil
===========================

Scheil-Gulliver non-equilibrium solidification, using the ``scheil`` package
(companion to pycalphad).

The Scheil-Gulliver assumption is **no back-diffusion in the solid + perfect
mixing in the liquid**, which is conservative: real castings sit between
full equilibrium (lever rule) and pure Scheil.  For most engineering work
Scheil over-predicts segregation but gives the right qualitative picture:

* Where solidification *starts* (liquidus)
* Where the *last drop* of liquid freezes (Scheil solidus, lower than
  equilibrium solidus)
* What that last drop is *made of* (terminal liquid composition; predicts
  hot-tearing intermetallics)
* How wide the *mushy zone* is (narrow = casting-friendly)

Public API
----------
``async scheil_solidification(composition, T_start_K=None)``
``scheil_solidification_sync(composition, T_start_K=None)``

Returns a dict with all the standard fields:

```
{
  "liquidus_K":          float,
  "solidus_K":           float,
  "mushy_zone_K":        float,
  "fraction_solid_curve":[{"T_K": …, "fs": …}, …],
  "active_phases":       {phase_name: max_fraction},
  "terminal_liquid":     {element: mole_fraction},
  "terminal_eutectic":   {phase_name: fraction_at_solidus},
  "hot_tearing_index":   float,        # ad-hoc: see below
  "source":              "scheil_gulliver",
  "tdb":                 str,
  "chemsys":             str,
  "calibration":         "deterministic",
  "value":               {...} | None,
  "error":               str | None
}
```

Hot-tearing index (HT)
----------------------
We adopt a simple proxy: ``HT = mushy_zone_K * sum(terminal_eutectic_fractions)``.
Wide mushy zones with a lot of late-freezing intermetallic give high HT (bad
for casting).  Narrow, fully-eutectic alloys give low HT.  This is a screening
heuristic, not a numerical hot-tearing model — see Eskin's "Physical
Metallurgy of Direct Chill Casting" for the proper criteria.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import warnings
from pathlib import Path
from typing import Any

import numpy as np

from apps.api.ml.calphad.databases import lookup_tdb, chemsys_str

logger = logging.getLogger(__name__)

# In-process cache: Scheil is the slowest piece (~10 s typical)
_CACHE: dict[str, dict] = {}
_CACHE_MAX = 64


def _cache_key(composition: dict[str, float], T_start_K: float, tdb_path: Path) -> str:
    comp_str = ",".join(f"{k.upper()}:{v:.6g}" for k, v in sorted(composition.items()))
    tdb_hash = hashlib.md5(tdb_path.name.encode()).hexdigest()[:8]
    return f"{comp_str}|T0={T_start_K:.1f}|{tdb_hash}"


def _normalise(composition: dict[str, float]) -> dict[str, float]:
    filtered = {k.upper(): v for k, v in composition.items()
                if k.upper() not in {"VA"} and v > 0}
    total = sum(filtered.values())
    return {k: v / total for k, v in filtered.items()} if total > 0 else {}


def _refused(reason: str, chemsys: str, T_start_K: float) -> dict:
    return {
        "liquidus_K": None, "solidus_K": None, "mushy_zone_K": None,
        "fraction_solid_curve": [], "active_phases": {},
        "terminal_liquid": {}, "terminal_eutectic": {},
        "hot_tearing_index": None,
        "source": "scheil_no_tdb" if reason == "no_tdb" else "scheil_gulliver",
        "tdb": None, "chemsys": chemsys,
        "calibration": "deterministic",
        "value": None, "error": reason,
    }


def _scheil_calc(
    composition: dict[str, float],
    T_start_K: float,
    tdb_path: Path,
) -> dict[str, Any]:
    """Blocking pycalphad + scheil call; MUST run in a worker thread."""
    from pycalphad import Database, variables as v
    from scheil import simulate_scheil_solidification

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        dbf = Database(str(tdb_path))
        elements = sorted(e.upper() for e in composition if e.upper() not in {"VA"})
        mole_fracs = _normalise(composition)

        # Scheil takes conditions on *all-but-one* elements (the dependent one)
        conditions = {
            v.X(el): float(frac)
            for el, frac in mole_fracs.items()
            if elements.index(el) != 0  # skip first (dependent) element
        }
        phases = list(dbf.phases.keys())

        try:
            res = simulate_scheil_solidification(
                dbf, elements + ["VA"], phases,
                conditions, T_start_K,
                step_temperature=5.0,
            )
        except Exception as exc:
            return _refused(f"scheil convergence failed: {exc}",
                            chemsys_str(composition), T_start_K)

    # ─ Reshape SolidificationResult → API payload ─
    temps   = np.array(res.temperatures, dtype=float)
    fs_curve = np.array(res.fraction_solid, dtype=float)

    # Liquidus = first T with fs > 0; Solidus = T where fs reaches 1 (or last)
    above_zero = np.where(fs_curve > 1e-5)[0]
    if len(above_zero) == 0:
        return _refused("no solidification observed (started below solidus?)",
                        chemsys_str(composition), T_start_K)
    liquidus_idx = int(above_zero[0])
    solidus_idx  = int(np.argmax(fs_curve >= 0.999)) if (fs_curve >= 0.999).any() else len(fs_curve) - 1
    liquidus_K = float(temps[liquidus_idx])
    solidus_K  = float(temps[solidus_idx])

    # Curve trimmed to the mushy zone
    curve = [
        {"T_K": float(temps[i]), "fs": float(fs_curve[i])}
        for i in range(liquidus_idx, solidus_idx + 1)
    ]

    # Per-phase max fractions and eutectic phases (those appearing late)
    active: dict[str, float] = {}
    terminal_eutectic: dict[str, float] = {}
    for phase, amts in res.phase_amounts.items():
        amts_arr = np.array(amts, dtype=float)
        peak = float(amts_arr.max())
        if peak > 1e-4:
            active[phase] = round(peak, 4)
            # If the phase appears in the final 20 % of the solidification range
            tail_start = liquidus_idx + int(0.8 * (solidus_idx - liquidus_idx))
            if (amts_arr[tail_start:solidus_idx + 1] > 1e-4).any():
                terminal_eutectic[phase] = round(peak, 4)

    # Terminal liquid composition (last finite x_liquid value per element)
    terminal_liquid: dict[str, float] = {}
    for el, vals in res.x_liquid.items():
        arr = np.array(vals, dtype=float)
        finite = arr[np.isfinite(arr)]
        if len(finite) > 0:
            terminal_liquid[el] = float(round(finite[-1], 4))

    mushy_zone_K = float(round(liquidus_K - solidus_K, 2))

    # Hot-tearing index (ad-hoc)
    intermetallic_at_solidus = sum(
        amt for ph, amt in terminal_eutectic.items()
        if ph not in {"LIQUID", "FCC_A1", "BCC_A2", "HCP_A3"}
    )
    hot_tearing_index = round(mushy_zone_K * (0.5 + intermetallic_at_solidus), 2)

    return {
        "liquidus_K": round(liquidus_K, 2),
        "solidus_K":  round(solidus_K, 2),
        "mushy_zone_K": mushy_zone_K,
        "fraction_solid_curve": curve,
        "active_phases": active,
        "terminal_liquid": terminal_liquid,
        "terminal_eutectic": terminal_eutectic,
        "hot_tearing_index": hot_tearing_index,
        "source": "scheil_gulliver",
        "tdb": tdb_path.name,
        "chemsys": chemsys_str(composition),
        "calibration": "deterministic",
        "value": {
            "liquidus_K": round(liquidus_K, 2),
            "solidus_K":  round(solidus_K, 2),
            "mushy_zone_K": mushy_zone_K,
        },
        "error": None,
    }


def scheil_solidification_sync(
    composition: dict[str, float],
    T_start_K: float | None = None,
) -> dict[str, Any]:
    """Synchronous Scheil-Gulliver simulation (for tests / CLI)."""
    if not composition:
        return _refused("empty composition", "", T_start_K or 0)
    tdb_path = lookup_tdb(composition)
    if tdb_path is None:
        return _refused("no_tdb", chemsys_str(composition), T_start_K or 0)

    # If user didn't supply a start T, default to ~150 K above an estimated liquidus
    if T_start_K is None:
        T_start_K = 1800.0 if any(e.upper() == "FE" for e in composition) else 1300.0

    key = _cache_key(composition, T_start_K, tdb_path)
    if key in _CACHE:
        return _CACHE[key]

    result = _scheil_calc(composition, T_start_K, tdb_path)
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = result
    return result


async def scheil_solidification(
    composition: dict[str, float],
    T_start_K: float | None = None,
) -> dict[str, Any]:
    """Async Scheil-Gulliver simulation (off-loaded to a worker thread)."""
    if not composition:
        return _refused("empty composition", "", T_start_K or 0)
    tdb_path = lookup_tdb(composition)
    if tdb_path is None:
        return _refused("no_tdb", chemsys_str(composition), T_start_K or 0)
    if T_start_K is None:
        T_start_K = 1800.0 if any(e.upper() == "FE" for e in composition) else 1300.0

    key = _cache_key(composition, T_start_K, tdb_path)
    if key in _CACHE:
        return _CACHE[key]

    try:
        result = await asyncio.to_thread(_scheil_calc, composition, T_start_K, tdb_path)
    except Exception as exc:
        logger.exception("scheil_solidification failure")
        result = _refused(str(exc), chemsys_str(composition), T_start_K)

    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = result
    return result
