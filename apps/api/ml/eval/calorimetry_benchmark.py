"""
Appendix E — M3GNet formation energy vs experimental calorimetry.

The MP formation-energy stress test (Appendix C/D) benchmarks M3GNet against
PBE-DFT, which is what the model was trained to reproduce.  This module adds a
harder target: experimental ΔHf values, so the number reported here is the
combined DFT + model error against measurement.

DATA STATUS (2026-11-01): VERIFIED, 12 references.  An earlier set of 25
hand-compiled values was cross-checked against two published experimental
compilations that ``matminer`` distributes: ``expt_formation_enthalpy``
(Kim, Meschel, Nash et al., Sci. Data 4, 170162, 2017) and
``expt_formation_enthalpy_kingsbury``.  Twelve of the 25 compounds appear in
them with an experimental value.  For eleven of those the hand-compiled number
was wrong, typically about half the experimental magnitude (likely a
per-formula-unit value divided by the atom count twice); only Mg2Si agreed.
The other 13 compounds have no independent experimental value in either
compilation and were removed rather than kept unverified:
Al3Ni, γ-TiAl, α2-Ti3Al, Fe3Al, Al3Fe, Ti2Ni, MgZn2, Al2Cu, Cu3Au, β-CuZn,
MoNi, FeCo, Al6Mn.  The 12 below take their value (and uncertainty, where the
compilation gives one) from those sources; the old numbers are in git history.

Consequence: the belief that "DFT overbinds transition-metal intermetallics by
2–4×" came from the wrong numbers.  Against the verified values M3GNet's MAE is
about 128 meV/atom with a small mean signed error (-37 meV); the error is
scatter (CoAl, NiTi, FeAl, Al3Ti, Cr3Si), not a uniform overbinding a linear
correction can remove.  See experimental_correction.py.

References:
    Kim, Meschel, Nash et al., Sci. Data 4, 170162 (2017), doi:10.1038/sdata.2017.162
    NIST-JANAF Thermochemical Tables (Mg-Si), https://janaf.nist.gov/tables/Mg-034.html
    Rzyman, "Enthalpies of formation of AlFe: experiment versus calculation"

Usage
-----
    python -m apps.api.ml.eval.calorimetry_benchmark
"""
from __future__ import annotations

import json
from typing import Any


# ─────────────────────────────────────────────────────────────────────────
# Experimental ΔHf references (298 K, eV/atom)
#
# Compositions are atomic fractions summing to 1.0.  The evaluate() harness
# from mp_formation_benchmark normalises internally, so the scale does not
# matter, but fractions are cleaner to read alongside the MP entries.
# ─────────────────────────────────────────────────────────────────────────

CALORI_REFERENCES: list[dict[str, Any]] = [
    {
        "name": "Ni3Al", "nelements": 2,
        "composition": {"Ni": 0.75, "Al": 0.25},
        "ref_eV_per_atom": -0.420,
        "ref_uncertainty_eV": 0.017,
        "source": "Kim, Meschel, Nash et al., Sci. Data 4, 170162 (2017), doi:10.1038/sdata.2017.162",
    },
    {
        "name": "NiAl (B2)", "nelements": 2,
        "composition": {"Ni": 0.5, "Al": 0.5},
        "ref_eV_per_atom": -0.640,
        "ref_uncertainty_eV": 0.011,
        "source": "Kim, Meschel, Nash et al., Sci. Data 4, 170162 (2017), doi:10.1038/sdata.2017.162",
    },
    {
        "name": "Al3Ti (D022)", "nelements": 2,
        "composition": {"Al": 0.75, "Ti": 0.25},
        "ref_eV_per_atom": -0.379,
        "ref_uncertainty_eV": 0.012,
        "source": "Kim, Meschel, Nash et al., Sci. Data 4, 170162 (2017), doi:10.1038/sdata.2017.162",
    },
    {
        "name": "FeAl (B2)", "nelements": 2,
        "composition": {"Fe": 0.5, "Al": 0.5},
        "ref_eV_per_atom": -0.260,
        "ref_uncertainty_eV": None,
        "source": "Rzyman, enthalpies of formation of AlFe: experiment versus calculation",
    },
    {
        "name": "NiTi (Nitinol B2)", "nelements": 2,
        "composition": {"Ni": 0.5, "Ti": 0.5},
        "ref_eV_per_atom": -0.343,
        "ref_uncertainty_eV": 0.011,
        "source": "Kim, Meschel, Nash et al., Sci. Data 4, 170162 (2017), doi:10.1038/sdata.2017.162",
    },
    {
        "name": "Ni3Ti", "nelements": 2,
        "composition": {"Ni": 0.75, "Ti": 0.25},
        "ref_eV_per_atom": -0.437,
        "ref_uncertainty_eV": 0.012,
        "source": "Kim, Meschel, Nash et al., Sci. Data 4, 170162 (2017), doi:10.1038/sdata.2017.162",
    },
    {
        "name": "Mg2Si", "nelements": 2,
        "composition": {"Mg": 0.667, "Si": 0.333},
        "ref_eV_per_atom": -0.269,
        "ref_uncertainty_eV": None,
        "source": "NIST-JANAF table for Mg-Si (https://janaf.nist.gov/tables/Mg-034.html)",
    },
    {
        "name": "Cu3Sn", "nelements": 2,
        "composition": {"Cu": 0.75, "Sn": 0.25},
        "ref_eV_per_atom": -0.108,
        "ref_uncertainty_eV": 0.032,
        "source": "Kim, Meschel, Nash et al., Sci. Data 4, 170162 (2017), doi:10.1038/sdata.2017.162",
    },
    {
        "name": "CoAl (B2)", "nelements": 2,
        "composition": {"Co": 0.5, "Al": 0.5},
        "ref_eV_per_atom": -0.537,
        "ref_uncertainty_eV": 0.011,
        "source": "Kim, Meschel, Nash et al., Sci. Data 4, 170162 (2017), doi:10.1038/sdata.2017.162",
    },
    {
        "name": "NbAl3 (D022)", "nelements": 2,
        "composition": {"Nb": 0.25, "Al": 0.75},
        "ref_eV_per_atom": -0.420,
        "ref_uncertainty_eV": 0.006,
        "source": "Kim, Meschel, Nash et al., Sci. Data 4, 170162 (2017), doi:10.1038/sdata.2017.162",
    },
    {
        "name": "ZrAl3 (D023)", "nelements": 2,
        "composition": {"Zr": 0.25, "Al": 0.75},
        "ref_eV_per_atom": -0.502,
        "ref_uncertainty_eV": 0.013,
        "source": "Kim, Meschel, Nash et al., Sci. Data 4, 170162 (2017), doi:10.1038/sdata.2017.162",
    },
    {
        "name": "Cr3Si (A15)", "nelements": 2,
        "composition": {"Cr": 0.75, "Si": 0.25},
        "ref_eV_per_atom": -0.282,
        "ref_uncertainty_eV": 0.011,
        "source": "Kim, Meschel, Nash et al., Sci. Data 4, 170162 (2017), doi:10.1038/sdata.2017.162",
    },
]


def run_calorimetry_benchmark() -> dict[str, Any]:
    """Benchmark M3GNet against verified experimental calorimetry for 12 well-known phases.

    Returns the same schema as ``evaluate()`` in mp_formation_benchmark — so the
    scorecard renderer can reuse the same table logic.  The ``source`` field in
    each result entry will reflect whether M3GNet or the Miedema fallback ran.

    Note on expected accuracy:
        M3GNet reproduces MP-PBE DFT values, so this MAE is DFT error plus model
        error against measurement.  Expect it to be larger than Appendix C.
    """
    from apps.api.ml.eval.mp_formation_benchmark import evaluate
    from apps.api.ml.featurizers import formation_energy_eV_per_atom

    result = evaluate(CALORI_REFERENCES, formation_energy_eV_per_atom)
    result["n_references"] = len(CALORI_REFERENCES)
    result["reference_source"] = "experimental formation enthalpies (Kim et al. 2017, NIST-JANAF, Rzyman)"
    result["dft_gap_note"] = (
        "M3GNet is trained on MP-PBE, so the reported MAE is the combined DFT and "
        "model error against measurement. A linear correction was tried and "
        "does not improve on it (experimental_correction.py)."
    )

    # When the real M3GNet ran, report the frozen linear bias correction
    # (experimental_correction.py) fitted on these same references — the honest
    # accuracy number is the leave-one-out CV MAE, not the in-sample fit.
    sources = result.get("predictor_sources") or {}
    if set(sources) == {"m3gnet_dft"}:
        from apps.api.ml.experimental_correction import CORRECTION
        if CORRECTION.get("slope") is not None:
            result["correction"] = {
                "slope": CORRECTION["slope"],
                "intercept": CORRECTION["intercept"],
                "loo_mae_meV": round(CORRECTION["loo_mae_eV"] * 1000, 1),
                "loo_q90_meV": round(CORRECTION["loo_q90_eV"] * 1000, 1),
                "n_fit": CORRECTION["n_fit"],
                "fitted_at": CORRECTION["fitted_at"],
            }
    return result


def main() -> None:
    result = run_calorimetry_benchmark()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
