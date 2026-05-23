"""
apps.api.ml.cost
=================

Sprint 8 — hierarchical alloy cost model.

The legacy cost ``manufacturability.cost_score`` was a single
mass-weighted spot price.  An OEM procurement officer would not
recognise that number — they pay for form factor, certification,
heat-treatment, and supplier minimums separately.

The Sprint 8 model:

::

    cost_USD_per_kg = mass_weighted_spot_price
                    × form_factor_multiplier         # ingot / sheet / plate / bar / wire / powder
                    × certification_multiplier        # commercial / AMS / ASME / NACE
                    × heat_treatment_multiplier       # annealed → vacuum-aged
                    + supplier_minimum_overhead / lot_kg

Every multiplier has a documented industry-standard basis.  See the
individual source files for citations.

Public API
----------
``compute_cost(composition, form, cert, ht, lot_kg)`` →
    dict with the full breakdown.
"""
from apps.api.ml.cost.model import compute_cost, available_options
