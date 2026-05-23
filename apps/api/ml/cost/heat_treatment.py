"""
apps.api.ml.cost.heat_treatment
=================================

Heat-treatment cost multipliers.

A heat-treated alloy has more energy + furnace time + atmosphere control
+ rework loss than the as-melted equivalent.  These multipliers are
based on the **ASM Heat Treaters' Guide** (3rd ed., 2016) plus the
operating cost models from Specialty Heat Treating Inc. and Bodycote.

The model is intentionally coarse — heat-treatment cost is typically
< 10 % of total alloy cost for non-aerospace forms and rises to ~30-50 %
for aerospace forgings where vacuum furnaces and process surveillance
dominate.
"""
HEAT_TREATMENT_MULTIPLIER: dict[str, float] = {
    "as_fabricated":         1.00,    # F temper — no treatment
    "annealed":              1.05,    # ~5 % uplift for furnace time
    "stress_relieved":       1.05,
    "normalised":            1.08,
    "Q&T":                   1.15,    # quench + temper cycle
    "solution_treated":      1.12,
    "solution_quenched":     1.15,
    "T6":                    1.20,    # solutionised + aged (Al / Ti)
    "T7x":                   1.22,    # T7/T73/T74/T7351 — extra overage
    "T8x":                   1.20,    # T81/T87 — cold-worked + aged
    "aged":                  1.18,    # Ni-base / PH-stainless
    "double_aged":           1.25,
    "carburised":            1.45,    # extra atmosphere + extended cycle
    "nitrided":              1.40,
    "vacuum_aged":           1.50,    # vacuum + ramped + surveillance
    "HIP":                   1.65,    # Hot Isostatic Pressing (Ni SX, AM)
    "vacuum_carburised":     1.75,
}

HEAT_TREATMENT_PROVENANCE: dict[str, str] = {
    "as_fabricated":         "F temper — no treatment",
    "annealed":              "ASM HTG ch.3 — 1.5-2 h furnace at 300-500 °C",
    "stress_relieved":       "ASM HTG ch.3 — lower-T anneal",
    "normalised":            "ASM HTG ch.13 — air-cool from austenitising T",
    "Q&T":                   "ASM HTG ch.13 — full austenitise + quench + temper",
    "solution_treated":      "ASM HTG ch.10 — solutionise + air cool",
    "solution_quenched":     "ASM HTG ch.10 — solutionise + water quench",
    "T6":                    "ASM HTG Aluminum vol.4 — solutionise + age 8-24 h",
    "T7x":                   "ASM HTG Aluminum vol.4 — overage 24-48 h",
    "T8x":                   "ASM HTG Aluminum vol.4 — cold-work + age",
    "aged":                  "Ni / PH-stainless aging cycle",
    "double_aged":           "γ' / γ\" Ni-superalloy two-step age",
    "carburised":            "ASM HTG ch.14 — pack/gas carburise 4-20 h",
    "nitrided":              "ASM HTG ch.16 — gas-nitride 20-60 h",
    "vacuum_aged":           "Bodycote 2024 vacuum-furnace pricing",
    "HIP":                   "Bodycote HIP — 1100-1200 °C / 100-200 MPa",
    "vacuum_carburised":     "Bodycote LPC — vacuum carburising premium",
}


def get_heat_treatment_multiplier(ht: str) -> float:
    """Return the multiplier for a heat-treatment code; default = as_fabricated (1.0)."""
    return HEAT_TREATMENT_MULTIPLIER.get(ht, 1.0)


def available_heat_treatments() -> list[str]:
    return list(HEAT_TREATMENT_MULTIPLIER.keys())


# Map common temper codes → heat-treatment cost class (so the caller can
# pass "T6", "T651", "Q&T", "Aged" etc. and get the right multiplier).
TEMPER_TO_HT_CLASS: dict[str, str] = {
    # Aluminum
    "O": "annealed",        "F": "as_fabricated",
    "T3": "solution_quenched", "T4": "solution_quenched", "T351": "solution_quenched",
    "T5": "T6", "T6": "T6", "T651": "T6", "T61": "T6",
    "T7": "T7x", "T73": "T7x", "T7351": "T7x", "T7451": "T7x",
    "T7651": "T7x", "T7751": "T7x",
    "T8": "T8x", "T81": "T8x", "T84": "T8x", "T851": "T8x",
    "T87": "T8x", "T8E74": "T8x", "T8771": "T8x", "T6511": "T8x",
    "H12": "annealed", "H14": "annealed", "H18": "annealed",
    "H22": "annealed", "H24": "annealed",
    "H32": "annealed", "H34": "annealed", "H38": "annealed",
    "H111": "annealed", "H116": "annealed", "H321": "annealed",
    # Steel
    "Annealed": "annealed",        "Hot-rolled": "as_fabricated",
    "As-rolled": "as_fabricated",  "Cold-rolled": "as_fabricated",
    "Cold-drawn": "as_fabricated", "Normalised":  "normalised",
    "TMCP": "normalised",          "HSLA": "as_fabricated",
    "Q&T": "Q&T", "Q&T 300": "Q&T", "Q&T 400": "Q&T", "Q&T 425": "Q&T",
    "Q&T 450": "Q&T", "Q&T 650": "Q&T",
    "Carburised": "carburised",    "Carburised + Q&T": "carburised",
    "Weathering": "as_fabricated",
    "H900": "vacuum_aged", "H950": "vacuum_aged", "H1000": "vacuum_aged",
    "H1025": "vacuum_aged", "H1050": "vacuum_aged", "H1150": "vacuum_aged",
    # Titanium
    "STA": "T6",            "HIP+Aged": "HIP",
    "β-anneal": "annealed", "Duplex anneal": "annealed",
    "Mill-annealed": "annealed",
    # Nickel
    "Aged": "aged",         "SX-Aged": "HIP",
    "Solution": "solution_treated",
}


def ht_class_from_temper(temper: str | None) -> str:
    """Map a temper code to its heat-treatment cost class."""
    if not temper:
        return "as_fabricated"
    return TEMPER_TO_HT_CLASS.get(temper, "annealed")
