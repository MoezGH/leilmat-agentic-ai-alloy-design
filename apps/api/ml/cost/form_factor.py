"""
apps.api.ml.cost.form_factor
==============================

Multipliers on the as-melted alloy spot price reflecting the cost of
converting to a usable mill-product form.

Sources
-------
* Carpenter Technology, TIMET, Special Metals Corp public price-list
  archives (the public catalogues print ratio multipliers between
  ingot, plate, bar, sheet, wire, tube, and powder forms).
* ASM Specialty Handbook — *Aluminum and Aluminum Alloys* (1993),
  Table 2 (form-factor cost ratios).
* AMS-Q-9-100 surcharge schedules.

These numbers are deliberately conservative midpoints; real quotes vary
±30 % within a form depending on alloy difficulty and supplier
relationship.
"""
FORM_FACTOR_MULTIPLIER: dict[str, float] = {
    # As-melted / unprocessed
    "ingot":   1.00,
    "billet":  1.10,
    # Hot-rolled / forged (cheap, most common engineering forms)
    "plate":   1.15,
    "bar":     1.20,
    "rod":     1.20,
    "forging": 1.40,
    # Cold-finished / shaped (extra mill passes)
    "sheet":   1.35,    # cold-rolled thin gauge
    "strip":   1.40,    # ultra-thin coil
    "wire":    1.75,    # drawn wire
    "tube":    1.55,    # seamless or DOM tubing
    "extrusion": 1.45,  # Al extrusions
    # Specialty / additive feedstock
    "powder":      3.50,    # atomised for AM (Ti / Ni)
    "powder_HIP":  4.50,    # spherical AM-grade
    "single_crystal": 8.00,    # Ni SX blade castings — primary cost is yield loss
}

FORM_FACTOR_PROVENANCE: dict[str, str] = {
    "ingot":          "as-melted reference (multiplier = 1.00)",
    "billet":         "Carpenter price list 2024-Q4",
    "plate":          "ASM Aluminum Handbook, hot-rolled plate vs ingot",
    "bar":            "Carpenter Round Bar surcharge schedule",
    "rod":            "Carpenter Round Bar surcharge schedule",
    "forging":        "Special Metals AMS-Q-9-100 forged-bar surcharge",
    "sheet":          "ASM cold-rolled sheet vs hot-rolled plate ratio",
    "strip":          "ULBRICH precision-strip pricing 2024",
    "wire":           "Carpenter Aerospace Wire 2024 catalogue",
    "tube":           "Sandvik seamless-tube surcharge 2024",
    "extrusion":      "Aluminum Extruders Council 2024 quote averages",
    "powder":         "AP&C / Carpenter AM-powder pricing 2024",
    "powder_HIP":     "Praxair / GE AM-grade Ni powder 2024",
    "single_crystal": "Rolls-Royce CMSX-4 blade-casting cost analysis",
}


def get_form_factor(form: str) -> float:
    """Return the multiplier for *form*; fall back to ingot (1.0) for unknown forms."""
    return FORM_FACTOR_MULTIPLIER.get(form, 1.0)


def available_forms() -> list[str]:
    return list(FORM_FACTOR_MULTIPLIER.keys())
