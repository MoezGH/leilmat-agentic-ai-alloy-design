"""
apps.api.ml.calphad.equilibrium
================================

``phase_assemblage(composition, T_K)`` — the single public entry point for
CALPHAD-based equilibrium phase calculations.

Returns
-------
dict with keys:
  phases        dict[str, float]  phase name → mole fraction (sum ≈ 1)
  phase_comps   dict[str, dict]   phase name → {element: mole_fraction}
  T_K           float
  source        "calphad_pycalphad"
  tdb           str               basename of the TDB used
  chemsys       str               e.g. "Al-Mg-Si"
  calibration   "deterministic"   CALPHAD output is not a stochastic model
  error         str | None        non-None on failure (OOD / convergence)
  value         None              placeholder so callers can do out["value"] is None
"""
from __future__ import annotations

import asyncio
import functools
import hashlib
import logging
import warnings
from pathlib import Path
from typing import Any

import numpy as np

from apps.api.ml.calphad.databases import lookup_tdb, chemsys_str

logger = logging.getLogger(__name__)

# ── In-process LRU cache (keyed by composition + T_K + tdb_hash) ────────────

_CACHE: dict[str, dict] = {}
_CACHE_MAX = 256   # keep last 256 results in memory


def _cache_key(composition: dict[str, float], T_K: float, tdb_path: Path) -> str:
    comp_str = ",".join(f"{k.upper()}:{v:.6g}" for k, v in sorted(composition.items()))
    tdb_hash = hashlib.md5(tdb_path.name.encode()).hexdigest()[:8]
    return f"{comp_str}|T={T_K:.2f}|{tdb_hash}"


# ── Mole-fraction normalisation helper ───────────────────────────────────────

def _normalise(composition: dict[str, float]) -> dict[str, float]:
    """Return composition normalised to sum-to-1, dropping VA and zero entries."""
    filtered = {k.upper(): v for k, v in composition.items()
                if k.upper() not in {"VA"} and v > 0}
    total = sum(filtered.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in filtered.items()}


# ── Phase extraction from pycalphad xarray dataset ───────────────────────────

def _extract(eq_result, elements: list[str]) -> tuple[dict[str, float], dict[str, dict]]:
    """Parse a pycalphad equilibrium Dataset into (phase_fractions, phase_comps).

    pycalphad stores:
      NP (vertex)    → mole fraction of phase at each vertex slot
      Phase (vertex) → phase name string
      X (vertex, component) → composition of that vertex (mole fracs)
    """
    phase_fractions: dict[str, float] = {}
    phase_comps: dict[str, dict] = {}

    # Squeeze out all size-1 dimensions
    np_vals   = np.array(eq_result["NP"]).squeeze()
    ph_vals   = np.array(eq_result["Phase"]).squeeze()
    x_vals    = np.array(eq_result["X"]).squeeze()   # shape (n_vertex, n_component)

    # Handle scalar / 0-d arrays
    if np_vals.ndim == 0:
        np_vals = np_vals.reshape(1)
        ph_vals = ph_vals.reshape(1)
        x_vals  = x_vals.reshape(1, -1) if x_vals.ndim > 0 else x_vals.reshape(1, 1)

    n_vertex = np_vals.shape[0]
    n_comp   = len(elements)

    for i in range(n_vertex):
        ph = str(ph_vals[i]).strip() if ph_vals.ndim > 0 else str(ph_vals).strip()
        if not ph or ph in {"", "nan", "None"}:
            continue
        frac = float(np_vals[i]) if np_vals.ndim > 0 else float(np_vals)
        if np.isnan(frac) or frac < 1e-8:
            continue
        # Accumulate (same phase can appear in multiple vertices for miscibility gaps)
        phase_fractions[ph] = phase_fractions.get(ph, 0.0) + frac
        # Per-phase composition
        if x_vals.ndim >= 2 and i < x_vals.shape[0]:
            comp_row = x_vals[i]
            comp = {
                elements[j]: float(comp_row[j])
                for j in range(min(n_comp, len(comp_row)))
                if not np.isnan(comp_row[j]) and comp_row[j] > 1e-8
            }
            phase_comps[ph] = comp

    # Renormalise fractions to sum = 1
    total = sum(phase_fractions.values())
    if total > 0:
        phase_fractions = {k: round(v / total, 6) for k, v in phase_fractions.items()}
    return phase_fractions, phase_comps


# ── Synchronous inner calculation (runs in a thread) ─────────────────────────

def _calc_equilibrium(
    composition: dict[str, float],
    T_K: float,
    tdb_path: Path,
) -> dict[str, Any]:
    """Blocking pycalphad call.  Must NOT be called on the asyncio event loop."""
    from pycalphad import Database, equilibrium, variables as v  # type: ignore

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        dbf = _get_db(tdb_path)
        elements_upper = [e.upper() for e in composition]

        # Build pycalphad conditions
        cond: dict = {v.T: T_K, v.P: 101325, v.N: 1}
        mole_fracs = _normalise(composition)
        for i, (el, xf) in enumerate(mole_fracs.items()):
            if i < len(mole_fracs) - 1:            # last element is set by difference
                cond[v.X(el)] = float(xf)

        # Select phases present in this database
        all_phases = list(dbf.phases.keys())
        # Prioritise major structural phases; include everything else so pycalphad
        # can find the global minimum.
        phases_to_use = all_phases

        try:
            eq = equilibrium(
                dbf,
                elements_upper + ["VA"],
                phases_to_use,
                cond,
                calc_opts={"pdens": 50},   # reduced point density for speed
            )
        except Exception as exc:
            return {
                "phases": {},
                "phase_comps": {},
                "T_K": T_K,
                "source": "calphad_pycalphad",
                "tdb": tdb_path.name,
                "chemsys": chemsys_str(composition),
                "calibration": "deterministic",
                "value": None,
                "error": f"pycalphad convergence failed: {exc}",
            }

        phase_fractions, phase_comps = _extract(eq, elements_upper)

    return {
        "phases": phase_fractions,
        "phase_comps": phase_comps,
        "T_K": T_K,
        "source": "calphad_pycalphad",
        "tdb": tdb_path.name,
        "chemsys": chemsys_str(composition),
        "calibration": "deterministic",
        "value": phase_fractions or None,   # None signals "refused"
        "error": None if phase_fractions else "no stable phases found",
    }


# ── Database LRU (keep up to 8 parsed TDB objects in memory) ─────────────────

_DB_CACHE: dict[str, Any] = {}
_DB_CACHE_ORDER: list[str] = []


def _get_db(path: Path):
    """Load and cache a pycalphad Database object."""
    from pycalphad import Database  # type: ignore

    key = str(path)
    if key not in _DB_CACHE:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _DB_CACHE[key] = Database(str(path))
        _DB_CACHE_ORDER.append(key)
        if len(_DB_CACHE_ORDER) > 8:
            oldest = _DB_CACHE_ORDER.pop(0)
            _DB_CACHE.pop(oldest, None)
    return _DB_CACHE[key]


# ── Public async entry point ──────────────────────────────────────────────────

async def phase_assemblage(
    composition: dict[str, float],
    T_K: float,
) -> dict[str, Any]:
    """Return the equilibrium phase assemblage for *composition* at *T_K*.

    Parameters
    ----------
    composition : dict[str, float]
        Element → mole fraction (or weight percent — any positive scale works;
        the function normalises internally).
    T_K : float
        Temperature in Kelvin.

    Returns
    -------
    dict
        See module docstring for the full key contract.
    """
    if not composition:
        return {
            "phases": {}, "phase_comps": {}, "T_K": T_K,
            "source": "calphad_pycalphad", "tdb": None,
            "chemsys": "", "calibration": "deterministic",
            "value": None, "error": "empty composition",
        }

    tdb_path = lookup_tdb(composition)
    if tdb_path is None:
        cs = chemsys_str(composition)
        return {
            "phases": {}, "phase_comps": {}, "T_K": T_K,
            "source": "calphad_no_tdb", "tdb": None,
            "chemsys": cs, "calibration": "deterministic",
            "value": None,
            "error": (
                f"No CALPHAD database covers the {cs} system. "
                "Bundled coverage is aluminium alloys (COST 507) and Fe-Co-Cr-Nb-Ti "
                "(a MatCalc extract); steels, Ni-based alloys and Fe-C are refused "
                "rather than answered from a database that does not model them. "
                "Drop a validated TDB into models/calphad_tdbs/ and register "
                "it in apps/api/ml/calphad/databases.py to extend coverage."
            ),
        }

    key = _cache_key(composition, T_K, tdb_path)
    if key in _CACHE:
        return _CACHE[key]

    # Run the blocking pycalphad call off the event loop
    try:
        result = await asyncio.to_thread(
            _calc_equilibrium, composition, T_K, tdb_path
        )
    except Exception as exc:
        logger.exception("Unexpected error in phase_assemblage")
        result = {
            "phases": {}, "phase_comps": {}, "T_K": T_K,
            "source": "calphad_pycalphad", "tdb": tdb_path.name,
            "chemsys": chemsys_str(composition), "calibration": "deterministic",
            "value": None, "error": str(exc),
        }

    # Cache management
    if len(_CACHE) >= _CACHE_MAX:
        oldest = next(iter(_CACHE))
        del _CACHE[oldest]
    _CACHE[key] = result
    return result


def phase_assemblage_sync(
    composition: dict[str, float],
    T_K: float,
) -> dict[str, Any]:
    """Synchronous wrapper for use in pytest / CLI scripts."""
    tdb_path = lookup_tdb(composition)
    if tdb_path is None:
        cs = chemsys_str(composition)
        return {
            "phases": {}, "phase_comps": {}, "T_K": T_K,
            "source": "calphad_no_tdb", "tdb": None,
            "chemsys": cs, "calibration": "deterministic",
            "value": None,
            "error": f"No CALPHAD database covers {cs}",
        }
    if not composition:
        return {
            "phases": {}, "phase_comps": {}, "T_K": T_K,
            "source": "calphad_pycalphad", "tdb": None,
            "chemsys": "", "calibration": "deterministic",
            "value": None, "error": "empty composition",
        }
    key = _cache_key(composition, T_K, tdb_path)
    if key in _CACHE:
        return _CACHE[key]
    result = _calc_equilibrium(composition, T_K, tdb_path)
    if len(_CACHE) >= _CACHE_MAX:
        oldest = next(iter(_CACHE))
        del _CACHE[oldest]
    _CACHE[key] = result
    return result
