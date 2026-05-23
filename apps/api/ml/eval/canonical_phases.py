"""
Canonical reference formation energies for validating the M3GNet predictor.

Reference values are pulled from the Materials Project (PBE-DFT computed
formation energies) for thermodynamically stable intermetallic phases that
M3GNet-Eform-MP-2018.6.1 was trained to reproduce. Each entry includes:

  - name: human-readable phase name (e.g. "γ'-Ni3Al")
  - composition: atomic-% dict (matches the predictor's input convention)
  - ref_eV_per_atom: MP-computed PBE-DFT formation energy
  - mp_id: Materials Project material id (for citation)
  - e_above_hull: distance above the convex hull (0 = stable phase)
  - note: brief engineering context

To re-verify these against the live MP database:
    python -m apps.api.ml.eval.canonical_phases --verify

The expected M3GNet accuracy is roughly:
  - Stoichiometric ordered phases (clean supercell): MAE ~50 meV/atom
  - Random-substitution supercells (our current approach): MAE ~100-200 meV/atom
    (configurational disorder biases the predicted energy slightly upward)
"""
from __future__ import annotations

from typing import Any


# ─────────────────────────────────────────────────────────────────────────
# Pure elements — formation energy is zero by definition.
# ─────────────────────────────────────────────────────────────────────────

PURE_ELEMENTS = [
    {"name": "pure Al",  "composition": {"Al": 100}, "ref_eV_per_atom": 0.0, "source": "by_definition"},
    {"name": "pure Fe",  "composition": {"Fe": 100}, "ref_eV_per_atom": 0.0, "source": "by_definition"},
    {"name": "pure Ni",  "composition": {"Ni": 100}, "ref_eV_per_atom": 0.0, "source": "by_definition"},
    {"name": "pure Ti",  "composition": {"Ti": 100}, "ref_eV_per_atom": 0.0, "source": "by_definition"},
    {"name": "pure Cu",  "composition": {"Cu": 100}, "ref_eV_per_atom": 0.0, "source": "by_definition"},
]


# ─────────────────────────────────────────────────────────────────────────
# Stoichiometric intermetallics with MP-computed PBE-DFT references.
# All entries below sit on the convex hull (e_above_hull = 0) — these are
# the cleanest possible benchmarks.
# ─────────────────────────────────────────────────────────────────────────

CANONICAL_INTERMETALLICS = [
    {
        "name": "γ'-Ni3Al",
        "composition": {"Ni": 75.0, "Al": 25.0},
        "ref_eV_per_atom": -0.4264,
        "mp_id": "mp-2593",
        "e_above_hull": 0.0,
        "note": "γ' precipitate — backbone of Ni-base superalloys (Inconel 718/738, Waspaloy).",
    },
    {
        "name": "β-NiAl",
        "composition": {"Ni": 50.0, "Al": 50.0},
        "ref_eV_per_atom": -0.6849,
        "mp_id": "mp-1487",
        "e_above_hull": 0.0,
        "note": "B2-NiAl; bond-coat layer in turbine thermal barrier coatings.",
    },
    {
        "name": "θ-Al2Cu",
        "composition": {"Al": 66.67, "Cu": 33.33},
        "ref_eV_per_atom": -0.2127,
        "mp_id": "mp-985806",
        "e_above_hull": 0.0,
        "note": "Precipitate phase in 2xxx Al-Cu alloys (2014, 2024).",
    },
    {
        "name": "Al3Ti (D022)",
        "composition": {"Al": 75.0, "Ti": 25.0},
        "ref_eV_per_atom": -0.4339,
        "mp_id": "mp-542915",
        "e_above_hull": 0.0,
        "note": "Ordered tetragonal D022; grain refiner in Al alloys.",
    },
    {
        "name": "γ-TiAl",
        "composition": {"Ti": 50.0, "Al": 50.0},
        "ref_eV_per_atom": -0.4470,
        "mp_id": "mp-1953",
        "e_above_hull": 0.0,
        "note": "L10 γ-TiAl; lightweight high-T phase, GEnx LPT blade material.",
    },
    {
        "name": "α2-Ti3Al",
        "composition": {"Ti": 75.0, "Al": 25.0},
        "ref_eV_per_atom": -0.2972,
        "mp_id": "mp-1823",
        "e_above_hull": 0.0,
        "note": "Ordered hexagonal D019 α2; companion phase to γ-TiAl.",
    },
    {
        "name": "B2-FeAl",
        "composition": {"Fe": 50.0, "Al": 50.0},
        "ref_eV_per_atom": -0.3269,
        "mp_id": "mp-2658",
        "e_above_hull": 0.0,
        "note": "Ordered B2; basis for Fe-Al iron aluminide structural alloys.",
    },
    {
        "name": "D03-Fe3Al",
        "composition": {"Fe": 75.0, "Al": 25.0},
        "ref_eV_per_atom": -0.1989,
        "mp_id": "mp-1183162",
        "e_above_hull": 0.0,
        "note": "Ordered D03 Fe3Al; oxidation-resistant iron aluminide.",
    },
    {
        "name": "L12-Cu3Au",
        "composition": {"Cu": 75.0, "Au": 25.0},
        "ref_eV_per_atom": -0.0366,
        "mp_id": "mp-2258",
        "e_above_hull": 0.0,
        "note": "Classic L12 ordering example; weak Cu-Au bonding.",
    },
    {
        "name": "Mg2Si",
        "composition": {"Mg": 66.67, "Si": 33.33},
        "ref_eV_per_atom": -0.1086,
        "mp_id": "mp-1367",
        "e_above_hull": 0.0,
        "note": "Antifluorite Mg2Si; strengthening precipitate in 6xxx Al alloys.",
    },
    {
        "name": "Ni3Ti",
        "composition": {"Ni": 75.0, "Ti": 25.0},
        "ref_eV_per_atom": -0.4828,
        "mp_id": "mp-1409",
        "e_above_hull": 0.0,
        "note": "η-Ni3Ti; embrittling phase in maraging steels (M250).",
    },
    {
        "name": "B2-NiTi (Nitinol)",
        "composition": {"Ni": 50.0, "Ti": 50.0},
        "ref_eV_per_atom": -0.3959,
        "mp_id": "mp-1048",
        "e_above_hull": 0.0,
        "note": "Nitinol austenite; shape-memory alloy.",
    },
    {
        "name": "γ-Cu5Zn8 brass",
        "composition": {"Cu": 38.46, "Zn": 61.54},
        "ref_eV_per_atom": -0.1085,
        "mp_id": "mp-1368",
        "e_above_hull": 0.0,
        "note": "γ-brass phase; intermediate Cu-Zn composition.",
    },
]


# ─────────────────────────────────────────────────────────────────────────
# Public accessor
# ─────────────────────────────────────────────────────────────────────────

ALL_REFERENCES = PURE_ELEMENTS + CANONICAL_INTERMETALLICS


def _verify_against_mp() -> None:
    """Re-fetch each reference value from the live MP database and report drift.

    Used as a sanity check that our hardcoded values still match what MP
    publishes. Run after MP releases (~ once a year).
    """
    from apps.api.config import settings
    from mp_api.client import MPRester

    if not settings.mp_api_key:
        print("MP_API_KEY not configured; cannot verify.")
        return

    print(f"{'Phase':<22} {'mp_id':<12} {'stored':>10} {'live':>10} {'diff':>8}")
    print("-" * 70)
    mp_ids = [e["mp_id"] for e in CANONICAL_INTERMETALLICS]
    with MPRester(settings.mp_api_key) as mpr:
        docs = mpr.materials.summary.search(
            material_ids=mp_ids,
            fields=["material_id", "formation_energy_per_atom"],
        )
        live = {d.material_id: d.formation_energy_per_atom for d in docs}

    for entry in CANONICAL_INTERMETALLICS:
        stored = entry["ref_eV_per_atom"]
        actual = live.get(entry["mp_id"])
        if actual is None:
            print(f"{entry['name']:<22} {entry['mp_id']:<12} {stored:>+10.4f} {'--':>10} {'MISSING':>8}")
        else:
            diff = actual - stored
            marker = "✓" if abs(diff) < 0.001 else "⚠"
            print(f"{entry['name']:<22} {entry['mp_id']:<12} {stored:>+10.4f} {actual:>+10.4f} {diff:>+8.4f} {marker}")


if __name__ == "__main__":
    import sys
    if "--verify" in sys.argv:
        _verify_against_mp()
    else:
        print(f"Total references: {len(ALL_REFERENCES)} ({len(PURE_ELEMENTS)} pure + {len(CANONICAL_INTERMETALLICS)} intermetallics)")
        for e in ALL_REFERENCES:
            print(f"  {e['name']:<22}  E_form = {e['ref_eV_per_atom']:+.4f} eV/atom")
