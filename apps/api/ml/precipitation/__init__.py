"""
apps.api.ml.precipitation
==========================

Sprint 5 — Kampmann-Wagner-Numerical (KWN) precipitation-kinetics solver.

For a given composition + precipitate phase + isothermal aging condition
(T, t), predict volume fraction f_v, mean radius r̄, and number density N
of strengthening precipitates: θ' in 2xxx Al, β'' in 6xxx Al, η in 7xxx,
γ' / γ'' in Ni superalloys.

This is the *kinetic* bridge between Sprint 1's CALPHAD thermodynamics
("how much precipitate is possible at equilibrium?") and the
mechanical-property prediction layer ("what does the actual
heat-treatment route give us?").

Public API
----------
from apps.api.ml.precipitation.kwn import (
    simulate_precipitation, simulate_precipitation_sync,
    available_phases, PRECIPITATE_DATA,
)
"""
