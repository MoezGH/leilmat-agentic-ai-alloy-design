"""
Appendix G — High-Entropy Alloy formation energy + cross-module consistency.

Two sub-tests:

G1 — HEA formation energy
    Run M3GNet on ~10 canonical HEA compositions (Cantor, AlCoCrFeNi, refractory
    systems, …) and compare to CALPHAD/DFT survey reference values.  HEAs are the
    hardest test for a model trained on binary/ternary MP data: 5-component
    near-equimolar compositions are rare in the training set.

G2 — Cross-module sign-agreement (consistency check)
    For each of the 13 canonical intermetallics in ``canonical_phases.py``, verify
    that M3GNet predicts ΔHf < 0 (energetically stable vs the constituent elements).
    All canonical phases are thermodynamically stable by construction, so M3GNet
    should agree on the sign 100% of the time — any disagreement indicates a
    predictor failure (wrong sign = predicted as less stable than pure elements).

References (HEA ΔHf):
    Senkov et al. — Acta Mater. 61 (2013); J. Alloys Compd. 509 (2011)
    Manzoni & Glatzel — New J. Chem. 40 (2016)
    George et al. — Nat. Rev. Mater. 4 (2019)
    Couzinie & Dirras — Mater. Char. 147 (2019)
    Huang et al. — npj Comput. Mater. 5 (2019)
    Turchanin et al. — Int. J. Mater. Res. 99 (2008)

Usage
-----
    python -m apps.api.ml.eval.hea_benchmark
"""
from __future__ import annotations

import json
from typing import Any


# ─────────────────────────────────────────────────────────────────────────
# G1 — HEA reference database
#
# Reference values are CALPHAD-assessed or DFT-survey averages — not single-
# point calculations.  These are inherently less certain than the binary
# intermetallic values in calorimetry_benchmark.py; treat them as order-of-
# magnitude checks rather than ground-truth comparisons.
# ─────────────────────────────────────────────────────────────────────────

HEA_REFERENCES: list[dict[str, Any]] = [
    # ── FCC single-phase HEAs ────────────────────────────────────────────
    {
        "name": "Cantor (CrMnFeCoNi)", "nelements": 5,
        "composition": {"Cr": 0.20, "Mn": 0.20, "Fe": 0.20, "Co": 0.20, "Ni": 0.20},
        "ref_eV_per_atom": -0.11,
        "source": "Senkov 2013 CALPHAD; Otto 2013 DFT survey",
    },
    {
        "name": "CoCrCuFeNi (Cu-bearing)", "nelements": 5,
        "composition": {"Co": 0.20, "Cr": 0.20, "Cu": 0.20, "Fe": 0.20, "Ni": 0.20},
        "ref_eV_per_atom": -0.07,
        "source": "George 2019 CALPHAD (Cu raises ΔHf due to Cu immiscibility)",
    },
    {
        "name": "Fe3(CrMnCoNi) Cantor-Fe-rich", "nelements": 5,
        "composition": {"Fe": 0.429, "Cr": 0.143, "Mn": 0.143, "Co": 0.143, "Ni": 0.143},
        "ref_eV_per_atom": -0.09,
        "source": "Turchanin 2008 DFT survey (Fe-enriched Cantor variant)",
    },
    # ── BCC / dual-phase HEAs ────────────────────────────────────────────
    {
        "name": "AlCoCrFeNi (equimolar)", "nelements": 5,
        "composition": {"Al": 0.20, "Co": 0.20, "Cr": 0.20, "Fe": 0.20, "Ni": 0.20},
        "ref_eV_per_atom": -0.22,
        "source": "Manzoni & Glatzel 2016; Turchanin 2008 (Al-Ni interaction dominates)",
    },
    {
        "name": "Al0.5CoCrFeNi", "nelements": 5,
        "composition": {"Al": 0.10, "Co": 0.225, "Cr": 0.225, "Fe": 0.225, "Ni": 0.225},
        "ref_eV_per_atom": -0.14,
        "source": "Senkov 2013 CALPHAD interpolated",
    },
    {
        "name": "Al2CoCrFeNi (Al-rich)", "nelements": 5,
        "composition": {"Al": 0.333, "Co": 0.167, "Cr": 0.167, "Fe": 0.167, "Ni": 0.167},
        "ref_eV_per_atom": -0.18,
        "source": "Huang 2019 DFT survey (elevated Al-Ni negative mixing)",
    },
    # ── Refractory HEAs (BCC) ────────────────────────────────────────────
    {
        "name": "TiZrNbHfTa", "nelements": 5,
        "composition": {"Ti": 0.20, "Zr": 0.20, "Nb": 0.20, "Hf": 0.20, "Ta": 0.20},
        "ref_eV_per_atom": -0.08,
        "source": "Senkov 2011 J.Alloys.Compd.",
    },
    {
        "name": "MoNbTaVW", "nelements": 5,
        "composition": {"Mo": 0.20, "Nb": 0.20, "Ta": 0.20, "V": 0.20, "W": 0.20},
        "ref_eV_per_atom": -0.02,
        "source": "Couzinie & Dirras 2019 (near-zero mixing — group 5-6 elements)",
    },
    {
        "name": "TiAlVCrNb (lightweight refractory)", "nelements": 5,
        "composition": {"Ti": 0.20, "Al": 0.20, "V": 0.20, "Cr": 0.20, "Nb": 0.20},
        "ref_eV_per_atom": -0.12,
        "source": "Huang 2019 npj Comput. Mater. DFT survey",
    },
    {
        "name": "TiNbMoTaW (refractory-5)", "nelements": 5,
        "composition": {"Ti": 0.20, "Nb": 0.20, "Mo": 0.20, "Ta": 0.20, "W": 0.20},
        "ref_eV_per_atom": -0.04,
        "source": "Senkov 2018 CALPHAD",
    },
]


def run_hea_benchmark() -> dict[str, Any]:
    """M3GNet formation energy on 10 canonical HEA compositions.

    Returns the same ``evaluate()`` schema as mp_formation_benchmark — MAE,
    by_nelements (all nelements=5), worst-10, in_envelope_pct.

    Expectation:
        M3GNet accuracy on 5-component HEAs is expected to be worse than on
        binary/ternary systems (Appendices C/D) — these compositions are far from
        the training distribution.  The goal is to measure how far, not to claim
        extrapolation accuracy.
    """
    from apps.api.ml.eval.mp_formation_benchmark import evaluate
    from apps.api.ml.featurizers import formation_energy_eV_per_atom

    result = evaluate(HEA_REFERENCES, formation_energy_eV_per_atom)
    result["n_hea_references"] = len(HEA_REFERENCES)
    result["reference_source"] = "CALPHAD assessments and DFT surveys (see module docstring)"
    return result


def run_consistency_check() -> dict[str, Any]:
    """Sign-agreement between CALPHAD-stable phases and M3GNet ΔHf.

    All 13 canonical intermetallics in ``canonical_phases.py`` are
    thermodynamically stable (ΔHf < 0 from both DFT and experiment).
    M3GNet should predict ΔHf < 0 for all of them — a sign disagreement
    means the model places a known stable compound above its constituent
    pure elements, which is a qualitative failure.

    Returns::

        {
            "n_total": 13,
            "n_consistent": 12,
            "consistency_pct": 92.3,
            "inconsistent": [...],   # list of phases where sign disagreed
            "all_results": [...],    # full per-phase table
        }
    """
    from apps.api.ml.eval.canonical_phases import CANONICAL_INTERMETALLICS
    from apps.api.ml.featurizers import formation_energy_eV_per_atom

    results: list[dict[str, Any]] = []
    for phase in CANONICAL_INTERMETALLICS:
        pred = formation_energy_eV_per_atom(phase["composition"])
        m3gnet_value = pred.get("value")
        # All canonical phases are stable by definition (e_above_hull = 0, ref < 0).
        m3gnet_stable = (m3gnet_value is not None) and (m3gnet_value < 0)
        results.append({
            "name": phase["name"],
            "ref_eV_per_atom": phase["ref_eV_per_atom"],
            "m3gnet_dHf": round(m3gnet_value, 4) if m3gnet_value is not None else None,
            "predictor_source": pred.get("source"),
            "sign_ok": m3gnet_stable,
        })

    n_total = len(results)
    n_ok = sum(r["sign_ok"] for r in results)
    return {
        "n_total": n_total,
        "n_consistent": n_ok,
        "consistency_pct": round(100 * n_ok / n_total, 1) if n_total else 0.0,
        "inconsistent": [r for r in results if not r["sign_ok"]],
        "all_results": results,
    }


def main() -> None:
    print("=== G1: HEA formation energy ===")
    print(json.dumps(run_hea_benchmark(), indent=2, default=str))
    print("\n=== G2: Cross-module consistency ===")
    print(json.dumps(run_consistency_check(), indent=2, default=str))


if __name__ == "__main__":
    main()
