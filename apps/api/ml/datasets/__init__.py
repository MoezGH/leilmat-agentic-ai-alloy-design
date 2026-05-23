"""
apps.api.ml.datasets
=====================

Sprint 3 — curated alloy datasets with provenance.

The original ``apps.api.ml.alloy_datasets`` module holds the *minimal*
curated set (~20-35 alloys per family) used for the first training pass.
This package adds **rigorously-cited extensions** so we can scale the
training data while keeping every value traceable to a public source.

Schema
------
Each entry is a ``dict`` with keys:

* ``name``            — standard alloy designation (e.g. ``"6061-T6"``).
* ``composition_wt``  — ``dict[element, weight%]``.
* ``ys_MPa``          — yield strength in MPa.
* ``temper``          — heat-treatment / temper code (e.g. ``"T6"``, ``"O"``).
* ``source``          — citation string (``"ASM Handbook v.2 §6.3"``, ``"AMS 4045"``).
* ``value_type``      — ``"typical"`` | ``"minimum"`` | ``"certified"``.
                        Only ``"typical"`` and ``"certified"`` enter training;
                        ``"minimum"`` values are kept for held-out QA.

Subpackages
-----------
* ``apps.api.ml.datasets.extended`` — the new entries, organised by family.
* ``apps.api.ml.datasets.crosswalk`` — canonical-name resolver across
  designation systems (AISI, UNS, DIN, JIS, AA).
* ``apps.api.ml.datasets.provenance`` — helpers for source attribution.

Public API
----------
``load_extended(family: str) -> list[dict]`` — returns the extended entries.
``load_combined(family: str) -> list[dict]`` — base + extended, deduplicated.
"""
from typing import List, Dict

_FAMILY_MODULES = {
    "aluminum":      "apps.api.ml.datasets.extended.aluminum",
    "titanium":      "apps.api.ml.datasets.extended.titanium",
    "nickel":        "apps.api.ml.datasets.extended.nickel",
    "general_steel": "apps.api.ml.datasets.extended.general_steel",
}


def load_extended(family: str) -> List[Dict]:
    """Return the Sprint-3 extended entries for *family* (empty if module missing)."""
    if family not in _FAMILY_MODULES:
        raise ValueError(f"Unknown family: {family}.  Valid: {list(_FAMILY_MODULES)}")
    import importlib
    try:
        mod = importlib.import_module(_FAMILY_MODULES[family])
    except ImportError:
        return []
    return list(getattr(mod, "ENTRIES", []))


def load_combined(family: str) -> List[Dict]:
    """Return base (alloy_datasets.py) + extended, with duplicates resolved.

    Two entries are duplicates if they have the same ``(name, temper)`` pair
    after canonicalising the name via the crosswalk.
    """
    from apps.api.ml.datasets.crosswalk import canonical_name

    base_attr = {
        "aluminum":      "ALUMINUM_ALLOYS",
        "titanium":      "TITANIUM_ALLOYS",
        "nickel":        "NICKEL_ALLOYS",
        "general_steel": "GENERAL_STEEL_ALLOYS",
    }[family]
    from apps.api.ml import alloy_datasets
    base = list(getattr(alloy_datasets, base_attr))
    extended = load_extended(family)

    seen = set()
    combined: List[Dict] = []
    for entry in base + extended:
        key = (canonical_name(entry["name"]), entry.get("temper", ""))
        if key in seen:
            continue
        seen.add(key)
        combined.append(entry)
    return combined
