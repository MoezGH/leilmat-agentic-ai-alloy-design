"""
Materials Project ground-state structure lookup for the M3GNet predictor.

Why this exists:
    The supercell approach in m3gnet_predictor builds a 32-atom box from
    the majority element's lattice and randomly substitutes atoms. For a
    composition that happens to coincide with a known stoichiometric
    intermetallic (Ni3Al, NiTi, Ti3Al, Mg2Si, …), the synthesised cell has
    the wrong lattice parameter, wrong space group, or wrong sublattice
    ordering — so M3GNet sees a high-energy configuration and overestimates
    stability by 200-300 meV/atom on those phases.

What this module does:
    Given a target composition, search the Materials Project for the
    closest stable phase by fractional composition (within a tolerance),
    fetch its pymatgen Structure (real lattice constants, real Wyckoff
    positions), and hand it back as an additional candidate for M3GNet
    to evaluate. When it matches, M3GNet predicts on the same input
    structure that produced the MP-PBE reference, so the only remaining
    error is the M3GNet model itself — ~50 meV/atom (published bench).

Strategy:
    1. Build a chemical-system key from the input (e.g. "Al-Ni").
    2. On first query for that chemsys, fetch ALL near-hull phases
       (e_above_hull ≤ 50 meV) from MP and cache them in-process.
    3. Match against the input composition by max-elementwise fractional
       distance ≤ tolerance (default 3 at%).
    4. Return the closest matching Structure, or None.

Caching:
    In-process dict keyed by chemsys. Loss on process restart is acceptable
    (MP is fast and the queries are rare in practice). For production we
    could pickle the cache to disk, but for now the cost is bounded by the
    number of distinct chemsys the user explores.

Robustness:
    - No MP API key in settings → return None (silent fallback).
    - MP API timeout or error → return None.
    - Composition has > 4 elements → skip (no useful MP match for highly
      multi-component alloys).
"""
from __future__ import annotations

import threading
import time
from typing import Any

# Module-level chemsys → list[(comp_frac, e_above_hull, structure)] cache
_mp_cache: dict[str, list[tuple[dict[str, float], float, Any]]] = {}
_mp_cache_lock = threading.Lock()
_mp_cache_misses = 0
_mp_cache_hits = 0


def _chemsys_key(composition: dict[str, float]) -> str:
    """Build the MP chemsys query string from a composition dict."""
    return "-".join(sorted(el for el, v in composition.items() if v > 0))


def _fetch_chemsys(chemsys: str, mp_api_key: str, max_hull: float = 0.05) -> list[tuple[dict[str, float], float, Any]]:
    """
    Hit the MP API for all phases in `chemsys` within `max_hull` eV/atom of
    the convex hull. Returns a list of (fractional_composition, hull_dist,
    structure) tuples.
    """
    from mp_api.client import MPRester

    with MPRester(mp_api_key) as mpr:
        docs = mpr.materials.summary.search(
            chemsys=chemsys,
            energy_above_hull=(0, max_hull),
            fields=["material_id", "formula_pretty", "composition_reduced",
                    "energy_above_hull", "structure"],
        )

    out: list[tuple[dict[str, float], float, Any]] = []
    for d in docs:
        try:
            # composition_reduced is a pymatgen Composition; normalise to fractions
            comp = d.composition_reduced
            total = sum(comp.as_dict().values())
            fracs = {el: v / total for el, v in comp.as_dict().items()}
            out.append((fracs, float(d.energy_above_hull or 0.0), d.structure))
        except Exception:
            continue
    return out


def _composition_distance(a: dict[str, float], b: dict[str, float]) -> float:
    """Max absolute difference across the union of element keys."""
    keys = set(a) | set(b)
    return max(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys)


def _scale_to_target_size(structure: Any, target_atoms: int = 32) -> Any:
    """Tile the structure isotropically until it has ≥ target_atoms.

    Small primitive cells (2-3 atoms) cause M3GNet to give unstable
    predictions — its message-passing layers expect a reasonable
    coordination shell, but a primitive cell's periodic images may sit too
    close. Tiling to ~32 atoms matches what the supercell builder uses and
    keeps predictions consistent across paths.
    """
    n = len(structure)
    if n >= target_atoms:
        return structure
    rep = max(1, int(round((target_atoms / n) ** (1.0 / 3))))
    if rep <= 1:
        rep = 2  # at least double
    try:
        return structure.copy().make_supercell([rep, rep, rep])
    except Exception:
        return structure


def get_mp_structure(
    composition: dict[str, float],
    tolerance: float = 0.03,
    max_hull: float = 0.05,
    max_elements: int = 4,
    target_atoms: int = 32,
) -> Any | None:
    """
    Find the closest stable MP structure to `composition`.

    Args:
        composition:  atomic % or atomic fraction dict — will be normalised.
        tolerance:    max elementwise fractional difference for a match
                      (0.03 = 3 atomic %).
        max_hull:     ignore MP entries more than this many eV/atom above
                      the convex hull.
        max_elements: skip lookup for compositions with more than this many
                      elements (MP matches are unlikely to help and queries
                      get slow).

    Returns:
        A pymatgen Structure of the closest stable phase, or None.
    """
    global _mp_cache_hits, _mp_cache_misses

    elements = [el for el, v in composition.items() if v > 0]
    if not elements or len(elements) > max_elements:
        return None

    total = sum(v for v in composition.values() if v > 0)
    if total <= 0:
        return None
    target = {el: v / total for el, v in composition.items() if v > 0}

    chemsys = _chemsys_key(composition)

    # Cached?
    if chemsys in _mp_cache:
        _mp_cache_hits += 1
        candidates = _mp_cache[chemsys]
    else:
        # Need to fetch — coordinate so concurrent calls don't duplicate work
        with _mp_cache_lock:
            if chemsys in _mp_cache:
                candidates = _mp_cache[chemsys]
            else:
                try:
                    from apps.api.config import settings
                except Exception:
                    return None
                if not settings.mp_api_key:
                    _mp_cache[chemsys] = []
                    return None
                try:
                    t0 = time.time()
                    candidates = _fetch_chemsys(chemsys, settings.mp_api_key, max_hull=max_hull)
                    _mp_cache[chemsys] = candidates
                    _mp_cache_misses += 1
                    print(f"[mp_lookup] fetched {len(candidates)} stable phases in '{chemsys}' "
                          f"in {time.time() - t0:.1f}s")
                except Exception as exc:
                    print(f"[mp_lookup] MP query failed for {chemsys}: {exc}")
                    _mp_cache[chemsys] = []
                    return None

    if not candidates:
        return None

    # Pick the closest match within tolerance
    best_struct = None
    best_dist = float("inf")
    for cand_fracs, _hull_dist, structure in candidates:
        d = _composition_distance(cand_fracs, target)
        if d < tolerance and d < best_dist:
            best_struct = structure
            best_dist = d

    if best_struct is None:
        return None
    return _scale_to_target_size(best_struct, target_atoms=target_atoms)


def cache_stats() -> dict[str, int]:
    """Diagnostics — used by the health endpoint and the scorecard."""
    return {
        "n_chemsys_cached":    len(_mp_cache),
        "n_phases_cached":     sum(len(v) for v in _mp_cache.values()),
        "n_chemsys_with_hits": sum(1 for v in _mp_cache.values() if v),
        "hits":                _mp_cache_hits,
        "misses":              _mp_cache_misses,
    }
