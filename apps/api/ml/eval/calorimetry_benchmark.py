"""
Appendix E — M3GNet formation energy vs experimental calorimetry.

The MP formation-energy stress test (Appendix C/D) benchmarks M3GNet against
PBE-DFT, which is what the model was trained to reproduce.  This module adds a
second, harder target: experimental ΔHf values from NIST WebBook, Kubaschewski
tables, and CALPHAD assessments.

Key distinction:
    DFT-PBE systematically overbinds transition-metal intermetallics — formation
    energies are typically 2–4× more negative than calorimetric values.  M3GNet
    reproduces DFT numbers well (Appendix C MAE ~167 meV/atom vs DFT), but when
    compared to experiment the bias becomes visible.  Appendix E *quantifies* that
    gap rather than hiding it.

DATA STATUS (2026-10): UNVERIFIED.  The 25 reference values below were compiled
    by the maintainers and attributed to the sources listed; they have not been
    checked row-by-row against those sources.  An equivalent audit of the nickel
    yield-strength references found 5 of 8 wrong, so treat the MAE reported here
    — and the experimental_correction fitted on these values — as provisional.

References:
    Kubaschewski, Alcock & Spencer — "Metallurgical Thermochemistry" (1993)
    Meschel & Kleppa — J. Alloys Compd. various (1993–2000)
    NIST-JANAF Thermochemical Tables (4th ed., Chase 1998)
    Turchanin et al. — J. Alloys Compd. 413 (2006)
    Saunders & Miodownik — "CALPHAD" (1998)
    Hultgren et al. — "Selected Values of Thermodynamic Properties of Alloys" (1973)

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
    # ── Al-Ni ────────────────────────────────────────────────────────────
    {
        "name": "Ni3Al", "nelements": 2,
        "composition": {"Ni": 0.75, "Al": 0.25},
        "ref_eV_per_atom": -0.110,
        "source": "Kubaschewski 1993 (−42.3 kJ/mol / 4 atoms)",
    },
    {
        "name": "NiAl (B2)", "nelements": 2,
        "composition": {"Ni": 0.50, "Al": 0.50},
        "ref_eV_per_atom": -0.303,
        "source": "NIST WebBook (−58.5 kJ/mol / 2 atoms)",
    },
    {
        "name": "Al3Ni", "nelements": 2,
        "composition": {"Al": 0.75, "Ni": 0.25},
        "ref_eV_per_atom": -0.111,
        "source": "Meschel & Kleppa J.Alloys.Compd. 1995 (−42.8 kJ/mol / 4 atoms)",
    },
    # ── Al-Ti ────────────────────────────────────────────────────────────
    {
        "name": "Al3Ti (D022)", "nelements": 2,
        "composition": {"Al": 0.75, "Ti": 0.25},
        "ref_eV_per_atom": -0.165,
        "source": "Saunders CALPHAD 1996 (−63.7 kJ/mol / 4 atoms)",
    },
    {
        "name": "γ-TiAl", "nelements": 2,
        "composition": {"Ti": 0.50, "Al": 0.50},
        "ref_eV_per_atom": -0.186,
        "source": "Turchanin J.Alloys.Compd. 2006 (−35.9 kJ/mol / 2 atoms)",
    },
    {
        "name": "α2-Ti3Al", "nelements": 2,
        "composition": {"Ti": 0.75, "Al": 0.25},
        "ref_eV_per_atom": -0.093,
        "source": "Meschel & Kleppa J.Alloys.Compd. 1993 (−36.0 kJ/mol / 4 atoms)",
    },
    # ── Al-Fe ────────────────────────────────────────────────────────────
    {
        "name": "FeAl (B2)", "nelements": 2,
        "composition": {"Fe": 0.50, "Al": 0.50},
        "ref_eV_per_atom": -0.130,
        "source": "Kubaschewski 1993 (−25.1 kJ/mol / 2 atoms)",
    },
    {
        "name": "Fe3Al (D03)", "nelements": 2,
        "composition": {"Fe": 0.75, "Al": 0.25},
        "ref_eV_per_atom": -0.040,
        "source": "Kubaschewski 1993 (−15.4 kJ/mol / 4 atoms)",
    },
    {
        "name": "Al3Fe", "nelements": 2,
        "composition": {"Al": 0.75, "Fe": 0.25},
        "ref_eV_per_atom": -0.093,
        "source": "Meschel & Kleppa J.Alloys.Compd. 1995 (−36.0 kJ/mol / 4 atoms)",
    },
    # ── Ni-Ti ────────────────────────────────────────────────────────────
    {
        "name": "NiTi (Nitinol B2)", "nelements": 2,
        "composition": {"Ni": 0.50, "Ti": 0.50},
        "ref_eV_per_atom": -0.175,
        "source": "Kleppa J.Phase Equilib. 1994 (−33.8 kJ/mol / 2 atoms)",
    },
    {
        "name": "Ni3Ti", "nelements": 2,
        "composition": {"Ni": 0.75, "Ti": 0.25},
        "ref_eV_per_atom": -0.169,
        "source": "Kubaschewski 1993 (−65.3 kJ/mol / 4 atoms)",
    },
    {
        "name": "Ti2Ni", "nelements": 2,
        "composition": {"Ti": 0.667, "Ni": 0.333},
        "ref_eV_per_atom": -0.157,
        "source": "Meschel & Kleppa J.Alloys.Compd. 1998 (−45.6 kJ/mol / 3 atoms)",
    },
    # ── Mg alloys ────────────────────────────────────────────────────────
    {
        "name": "Mg2Si", "nelements": 2,
        "composition": {"Mg": 0.667, "Si": 0.333},
        "ref_eV_per_atom": -0.268,
        "source": "NIST-JANAF Chase 1998 (−77.8 kJ/mol / 3 atoms)",
    },
    {
        "name": "MgZn2 (C14 Laves)", "nelements": 2,
        "composition": {"Mg": 0.333, "Zn": 0.667},
        "ref_eV_per_atom": -0.076,
        "source": "Kubaschewski 1993 (−22.1 kJ/mol / 3 atoms)",
    },
    # ── Al-Cu ────────────────────────────────────────────────────────────
    {
        "name": "Al2Cu (θ)", "nelements": 2,
        "composition": {"Al": 0.667, "Cu": 0.333},
        "ref_eV_per_atom": -0.121,
        "source": "NIST WebBook (−35.0 kJ/mol / 3 atoms)",
    },
    # ── Cu alloys ────────────────────────────────────────────────────────
    {
        "name": "Cu3Au (L12)", "nelements": 2,
        "composition": {"Cu": 0.75, "Au": 0.25},
        "ref_eV_per_atom": -0.020,
        "source": "NIST WebBook (−7.7 kJ/mol / 4 atoms)",
    },
    {
        "name": "β-CuZn (brass)", "nelements": 2,
        "composition": {"Cu": 0.50, "Zn": 0.50},
        "ref_eV_per_atom": -0.052,
        "source": "Dinsdale CALPHAD 1991 (−10.1 kJ/mol / 2 atoms)",
    },
    {
        "name": "Cu3Sn", "nelements": 2,
        "composition": {"Cu": 0.75, "Sn": 0.25},
        "ref_eV_per_atom": -0.051,
        "source": "Hultgren et al. 1973 (−19.8 kJ/mol / 4 atoms)",
    },
    # ── Co-Al ────────────────────────────────────────────────────────────
    {
        "name": "CoAl (B2)", "nelements": 2,
        "composition": {"Co": 0.50, "Al": 0.50},
        "ref_eV_per_atom": -0.271,
        "source": "Kubaschewski 1993 (−52.3 kJ/mol / 2 atoms)",
    },
    # ── Nb-Al ────────────────────────────────────────────────────────────
    {
        "name": "NbAl3 (D022)", "nelements": 2,
        "composition": {"Nb": 0.25, "Al": 0.75},
        "ref_eV_per_atom": -0.243,
        "source": "Meschel & Kleppa J.Alloys.Compd. 1997 (−93.7 kJ/mol / 4 atoms)",
    },
    # ── Zr-Al ────────────────────────────────────────────────────────────
    {
        "name": "ZrAl3 (D023)", "nelements": 2,
        "composition": {"Zr": 0.25, "Al": 0.75},
        "ref_eV_per_atom": -0.266,
        "source": "Meschel & Kleppa J.Alloys.Compd. 1997 (−102.7 kJ/mol / 4 atoms)",
    },
    # ── Mo-Ni ────────────────────────────────────────────────────────────
    {
        "name": "MoNi", "nelements": 2,
        "composition": {"Mo": 0.50, "Ni": 0.50},
        "ref_eV_per_atom": -0.032,
        "source": "Kubaschewski 1993 (−6.2 kJ/mol / 2 atoms)",
    },
    # ── Cr-Si ────────────────────────────────────────────────────────────
    {
        "name": "Cr3Si (A15)", "nelements": 2,
        "composition": {"Cr": 0.75, "Si": 0.25},
        "ref_eV_per_atom": -0.118,
        "source": "Meschel & Kleppa J.Alloys.Compd. 1998 (−45.6 kJ/mol / 4 atoms)",
    },
    # ── Fe-Co ────────────────────────────────────────────────────────────
    {
        "name": "FeCo (B2)", "nelements": 2,
        "composition": {"Fe": 0.50, "Co": 0.50},
        "ref_eV_per_atom": -0.024,
        "source": "Kubaschewski 1993 (−4.6 kJ/mol / 2 atoms)",
    },
    # ── Al-Mn ────────────────────────────────────────────────────────────
    {
        "name": "Al6Mn", "nelements": 2,
        "composition": {"Al": 0.857, "Mn": 0.143},
        "ref_eV_per_atom": -0.052,
        "source": "Meschel & Kleppa J.Alloys.Compd. 1996 (−35.2 kJ/mol / 7 atoms)",
    },
]


def run_calorimetry_benchmark() -> dict[str, Any]:
    """Benchmark M3GNet against experimental calorimetry for 25 well-known phases.

    Returns the same schema as ``evaluate()`` in mp_formation_benchmark — so the
    scorecard renderer can reuse the same table logic.  The ``source`` field in
    each result entry will reflect whether M3GNet or the Miedema fallback ran.

    Note on expected accuracy:
        M3GNet reproduces MP-PBE DFT values; DFT overbinds transition-metal
        intermetallics by a factor of ~2–3 vs calorimetry.  Expect MAE on this
        benchmark to be *larger* than Appendix C — that is the DFT-error gap,
        not a model defect.
    """
    from apps.api.ml.eval.mp_formation_benchmark import evaluate
    from apps.api.ml.featurizers import formation_energy_eV_per_atom

    result = evaluate(CALORI_REFERENCES, formation_energy_eV_per_atom)
    result["n_references"] = len(CALORI_REFERENCES)
    result["reference_source"] = "experimental calorimetry (NIST/Kubaschewski/CALPHAD)"
    result["dft_gap_note"] = (
        "M3GNet is trained on MP-PBE; DFT overbinds intermetallics ~2-4× vs "
        "calorimetry. Reported MAE quantifies this systematic gap."
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
