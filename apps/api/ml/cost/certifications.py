"""
apps.api.ml.cost.certifications
=================================

Certification multipliers on the base material cost.

A "commercial-grade" alloy is the cheapest tier — no specific
specification, mill's own internal QA only.  Each step up the
certification ladder adds documentation, traceability, and a discrete
testing-cost surcharge.

Sources
-------
* MIL-DTL-9710 (aerospace material specifications)
* MIL-STD-2154 (NDT requirements)
* AMS Q-9-100 surcharge schedules (publicly listed by Carpenter, Howmet,
  Special Metals)
* ASME B&PV Code Section II material qualifications
* NACE MR0175 / ISO 15156 (sour-service oilfield)
"""
CERTIFICATION_MULTIPLIER: dict[str, float] = {
    "commercial":  1.00,    # no spec — generic engineering grade
    "ASTM":        1.05,    # ASTM grade with mill cert (1-5 % uplift)
    "ASME":        1.15,    # ASME Section II (Code-stamped pressure vessel)
    "AMS":         1.75,    # AMS spec (aerospace) — Class A trace, NDT, certified-lot premium
    "AMS_class_I": 1.75,    # AMS Class I (single-melt + UT inspection)
    "AMS_class_II":1.65,    # AMS Class II
    "MIL-DTL":     1.80,    # MIL-DTL aerospace-defence (premium melt + chain-of-custody)
    "NACE":        1.30,    # NACE MR0175 sour-service oilfield qualification
    "BPV":         1.20,    # ASME B&PV Section II/IID nuclear-grade
    "NEMA_MG-1":   1.10,    # NEMA MG-1 (electrical machinery)
    "ISO-9001":    1.05,    # generic quality-system certification
}

CERTIFICATION_PROVENANCE = {
    "commercial":  "no spec; mill's own QA only",
    "ASTM":        "ASTM grade + mill cert (Carpenter / Howmet price lists)",
    "ASME":        "ASME B&PV Code Section II Class qualification",
    "AMS":         "AMS aerospace material specification (Class A traceability)",
    "AMS_class_I": "AMS Class I (single-melt + UT inspection)",
    "AMS_class_II":"AMS Class II requirements",
    "MIL-DTL":     "MIL-DTL aerospace-defence chain-of-custody",
    "NACE":        "NACE MR0175 sour-service qualification (oil & gas)",
    "BPV":         "ASME B&PV nuclear-grade Section IID",
    "NEMA_MG-1":   "NEMA MG-1 electrical-machinery quality",
    "ISO-9001":    "ISO 9001 quality-system certification",
}


def get_certification_multiplier(cert: str) -> float:
    """Return the multiplier for a certification level; default = commercial."""
    return CERTIFICATION_MULTIPLIER.get(cert, 1.0)


def available_certifications() -> list[str]:
    return list(CERTIFICATION_MULTIPLIER.keys())
