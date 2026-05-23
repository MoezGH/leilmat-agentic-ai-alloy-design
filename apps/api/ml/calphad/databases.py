"""
apps.api.ml.calphad.databases
==============================

Chemsys → TDB file registry.

Resolution logic
----------------
1. *User registry* (`_USER_REGISTRY`): drop a commercial TDB (TCAL, TCFE, …)
   into ``models/calphad_tdbs/`` and add an entry here — it will be preferred
   over the bundled open-source databases when it covers more elements.
2. *Bundled open-source databases* (`_BUNDLED`): shipped with the repo and
   sourced from the pycalphad test suite (BSD-3-Clause).  Coverage notes are
   in ``models/calphad_tdbs/README.md``.

``lookup_tdb(composition)`` returns the *best* TDB path for a composition dict
(element → mole fraction), or ``None`` when no TDB covers the full chemsys.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

_TDB_DIR = Path(__file__).parent.parent.parent.parent.parent / "models" / "calphad_tdbs"


# ── Bundled open-source TDB definitions ──────────────────────────────────────

class _TDBEntry:
    """Metadata for a single TDB file."""

    def __init__(self, filename: str, elements: set[str], priority: int = 0):
        self.path = _TDB_DIR / filename
        self.elements = {e.upper() for e in elements}
        self.priority = priority   # higher = preferred when multiple match

    def covers(self, chemsys: set[str]) -> bool:
        return chemsys <= self.elements


# Priority 0 = bundled open-source; 10 = user-supplied / commercial
_BUNDLED: list[_TDBEntry] = [
    # COST507: 27-element Al-alloy workhorse (EU COST project, Dinsdale 1998)
    _TDBEntry(
        "cost507_al_alloys.tdb",
        {"AL", "MG", "SI", "CU", "FE", "MN", "CR", "TI", "ZR", "ZN",
         "NI", "MO", "LI", "SN", "V", "W", "NB", "TA", "HF", "Y",
         "CE", "ND", "B", "C", "N", "O"},
        priority=5,
    ),
    # MatCalc mc_fecocrnbti: Fe-based alloys + Ni superalloy base
    _TDBEntry(
        "mc_fecocrnbti_steels.tdb",
        {"FE", "CR", "NI", "CO", "TI", "NB", "MO", "SI", "C", "MN",
         "AL", "W", "V", "CU", "B", "N", "O"},
        priority=4,
    ),
    # Al-Co-Cr-Ni quaternary (γ' superalloy research)
    _TDBEntry(
        "alcocrni_nibase.tdb",
        {"AL", "CO", "CR", "NI"},
        priority=3,
    ),
    # Al-Cr-Ni ternary
    _TDBEntry(
        "alcrni_nibase.tdb",
        {"AL", "CR", "NI"},
        priority=2,
    ),
    # Al-Ni binary (γ' reference)
    _TDBEntry(
        "alni_binary.tdb",
        {"AL", "NI"},
        priority=1,
    ),
    # Al-Zn binary (7xxx precursor)
    _TDBEntry(
        "alzn_binary.tdb",
        {"AL", "ZN"},
        priority=1,
    ),
    # C-Fe binary (iron-carbon phase diagram)
    _TDBEntry(
        "cfe_binary.tdb",
        {"C", "FE"},
        priority=1,
    ),
]


# ── User / commercial TDB registry (extend this dict) ────────────────────────

_USER_REGISTRY: list[_TDBEntry] = [
    # Example:
    # _TDBEntry("tcal8_al_commercial.tdb",
    #           {"AL","MG","SI","CU","FE","MN","CR","TI","ZN","ZR","NI"},
    #           priority=20),
]


def lookup_tdb(composition: dict[str, float]) -> Optional[Path]:
    """Return the TDB path with the best coverage for *composition*.

    Selection strategy (in order of precedence):
    1. User-supplied / commercial TDBs (priority ≥ 10) — always preferred.
    2. Among bundled TDBs, prefer the *most specific* (fewest excess elements)
       database that covers the chemsys.  Ties are broken by priority.

    "Most specific" means: min(len(entry.elements) - len(chemsys)).  A binary
    Ni-Al TDB (2 elements) wins over COST507 (27 elements) for a Ni-Al calc.

    Parameters
    ----------
    composition : dict[str, float]
        Element symbol → mole fraction (or any positive weight).  Vacancy
        ("VA") is added automatically by pycalphad and should **not** be
        included here.

    Returns
    -------
    Path | None
        Absolute path to the best TDB file, or ``None`` when no registered TDB
        covers every element in the composition.
    """
    chemsys = {e.upper() for e in composition if e.upper() not in {"VA"}}
    all_entries = _USER_REGISTRY + _BUNDLED
    candidates = [
        entry for entry in all_entries
        if entry.covers(chemsys) and entry.path.exists()
    ]
    if not candidates:
        return None

    # User/commercial TDBs (priority ≥ 10) take absolute precedence
    user_candidates = [e for e in candidates if e.priority >= 10]
    if user_candidates:
        return max(user_candidates, key=lambda e: e.priority).path

    # Among bundled TDBs: give a large bonus for exact-match TDBs (0 excess elements).
    # This ensures a dedicated binary/ternary TDB (e.g. alni_binary for Ni-Al)
    # beats a generalist 27-element database for the same chemsys — but only when
    # the dedicated TDB was *designed* for that system (no irrelevant excess elements).
    # Generalist databases like COST507 and mc_fecocrnbti keep their plain priority
    # score for multi-element alloy systems.
    def _score(entry: "_TDBEntry") -> int:
        excess = len(entry.elements - chemsys - {"VA"})
        exact_bonus = 20 if excess == 0 else 0
        return entry.priority + exact_bonus

    return max(candidates, key=_score).path


def list_coverage() -> list[dict]:
    """Return a coverage summary for each registered TDB (bundled + user).

    Returned as a list of dicts suitable for the scorecard CLI and the
    ``GET /api/phase/equilibrium/coverage`` endpoint.
    """
    rows = []
    for entry in _USER_REGISTRY + _BUNDLED:
        rows.append(
            {
                "file": entry.path.name,
                "elements": sorted(entry.elements - {"VA"}),
                "n_elements": len(entry.elements - {"VA"}),
                "available": entry.path.exists(),
                "priority": entry.priority,
                "source": "user" if entry.priority >= 10 else "bundled",
            }
        )
    return rows


def chemsys_str(composition: dict[str, float]) -> str:
    """Return canonical sorted element string, e.g. ``'Al-Mg-Si'``."""
    elements = sorted(e.upper() for e in composition if e.upper() != "VA")
    return "-".join(elements)
