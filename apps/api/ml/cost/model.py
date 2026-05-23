"""
apps.api.ml.cost.model
=========================

The Sprint 8 cost-prediction function.

::

    cost_USD_per_kg = mass_weighted_spot_price
                    × form_factor_multiplier
                    × certification_multiplier
                    × heat_treatment_multiplier
                    + supplier_minimum_overhead / lot_kg

Public API
----------
``compute_cost(composition, form, cert, ht, lot_kg, family=None)``
    Returns the full breakdown + provenance.

``available_options()``
    Lists the per-axis vocabularies for the UI dropdown.
"""
from __future__ import annotations

from typing import Any, Optional

from apps.api.ml.cost.elements_2025 import (
    ELEMENT_PRICE_USD_PER_KG, DEFAULT_PRICE_USD_PER_KG, PRICE_PROVENANCE,
)
from apps.api.ml.cost.form_factor import (
    FORM_FACTOR_MULTIPLIER, FORM_FACTOR_PROVENANCE, get_form_factor,
    available_forms,
)
from apps.api.ml.cost.certifications import (
    CERTIFICATION_MULTIPLIER, CERTIFICATION_PROVENANCE,
    get_certification_multiplier, available_certifications,
)
from apps.api.ml.cost.heat_treatment import (
    HEAT_TREATMENT_MULTIPLIER, HEAT_TREATMENT_PROVENANCE,
    get_heat_treatment_multiplier, ht_class_from_temper,
    available_heat_treatments,
)
from apps.api.ml.cost.supplier_minimums import (
    overhead_for_family, classify_family, overhead_per_kg,
)


def _mass_fractions(composition: dict) -> dict:
    """Convert at% or wt% to mass fractions.

    Accepts the same heterogeneous input convention used elsewhere
    (composition is either at%/wt% — we treat the dict as relative and
    use pymatgen atomic masses to derive mass fractions).
    """
    from pymatgen.core import Element
    masses = {}
    for el, v in composition.items():
        if v <= 0:
            continue
        try:
            masses[el] = v * Element(el).atomic_mass
        except Exception:
            continue
    tot = sum(masses.values())
    if tot <= 0:
        return {}
    return {el: m / tot for el, m in masses.items()}


def _spot_price(mass_fractions: dict) -> tuple[float, list]:
    """Mass-weighted USD/kg + per-element contribution list."""
    total = 0.0
    contributions = []
    for el, mf in mass_fractions.items():
        price = ELEMENT_PRICE_USD_PER_KG.get(el, DEFAULT_PRICE_USD_PER_KG)
        c = mf * price
        total += c
        contributions.append({
            "element":          el,
            "mass_fraction":    round(mf, 5),
            "USD_per_kg_pure":  price,
            "USD_per_kg_alloy": round(c, 3),
        })
    contributions.sort(key=lambda d: -d["USD_per_kg_alloy"])
    return total, contributions


def compute_cost(
    composition: dict,
    form: str            = "plate",
    cert: str            = "commercial",
    ht:   Optional[str]  = None,
    lot_kg: float        = 100.0,
    family: Optional[str]= None,
) -> dict[str, Any]:
    """Compute the alloy cost with a full breakdown.

    Parameters
    ----------
    composition : dict
        Weight % or atomic %.  Converted to mass fractions internally
        via pymatgen atomic masses.
    form : str
        Mill product form.  See ``available_options()['forms']``.
    cert : str
        Certification level.  See ``available_options()['certifications']``.
    ht : str | None
        Heat-treatment code or temper string (e.g. ``"T6"``, ``"Q&T"``,
        ``"H900"``).  ``None`` → no heat-treatment cost.
    lot_kg : float
        Order quantity in kg.  Smaller lots amortise less of the supplier
        minimum overhead.  Default 100 kg.
    family : str | None
        Force a supplier-minimum family bucket; if ``None`` we classify
        from the composition.

    Returns
    -------
    dict with:
        - ``USD_per_kg``         (final, including supplier overhead)
        - ``breakdown``          spot, form_mult, cert_mult, ht_mult, overhead
        - ``contributions``      per-element USD/kg breakdown
        - ``family``             classified supplier-family bucket
        - ``source`` / ``calibration`` fields
    """
    mf = _mass_fractions(composition)
    if not mf:
        return {
            "USD_per_kg": None, "source": "cost_v2",
            "error": "empty or unrecognised composition",
        }

    spot, contributions = _spot_price(mf)
    form_mult  = get_form_factor(form)
    cert_mult  = get_certification_multiplier(cert)
    ht_class   = ht_class_from_temper(ht) if ht else "as_fabricated"
    ht_mult    = get_heat_treatment_multiplier(ht_class)

    base_subtotal = spot * form_mult * cert_mult * ht_mult

    family_key = family or classify_family(composition, cert)
    overhead   = overhead_for_family(family_key)
    overhead_kg = overhead_per_kg(family_key, lot_kg)
    total_kg = base_subtotal + overhead_kg

    return {
        "USD_per_kg":          round(total_kg, 2),
        "USD_per_kg_no_overhead": round(base_subtotal, 2),
        "breakdown": {
            "spot_price_USD_per_kg":      round(spot, 3),
            "form_factor_multiplier":     form_mult,
            "certification_multiplier":   cert_mult,
            "heat_treatment_class":       ht_class,
            "heat_treatment_multiplier":  ht_mult,
            "supplier_overhead_USD":      overhead,
            "supplier_overhead_per_kg":   round(overhead_kg, 3),
            "lot_kg":                     lot_kg,
        },
        "family":           family_key,
        "form":             form,
        "certification":    cert,
        "contributions":    contributions[:8],   # top 8 cost drivers
        "source":           "cost_v2_hierarchical",
        "calibration":      "spot_prices_2025_q2",
        "provenance": {
            "spot":         PRICE_PROVENANCE,
            "form":         FORM_FACTOR_PROVENANCE.get(form, "unknown"),
            "cert":         CERTIFICATION_PROVENANCE.get(cert, "unknown"),
            "ht":           HEAT_TREATMENT_PROVENANCE.get(ht_class, "unknown"),
        },
    }


def available_options() -> dict:
    """Per-axis vocabularies for the UI dropdown."""
    return {
        "forms":          available_forms(),
        "certifications": available_certifications(),
        "heat_treatments":available_heat_treatments(),
    }
