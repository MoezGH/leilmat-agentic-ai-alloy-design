"""
Case Study 2 — Al-Li alloy for aerospace stringers.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from apps.api.ml.inverse import (
    run_inverse_design, InverseDesignRequest, PropertyTarget,
)
from case_studies._helpers import (
    predict_for_literature, save_candidates_csv, save_summary_json,
    compare_table, plot_pareto_scatter, plot_property_bars,
    plot_radar_comparison,
)

OUT = Path(__file__).parent / "results"
OUT.mkdir(exist_ok=True)


LITERATURE = {
    "2090-T84":  {"Al": 95.4, "Cu": 2.7, "Li": 2.1, "Zr": 0.12},
    "2050-T84":  {"Al": 94.2, "Cu": 3.6, "Li": 1.0, "Mg": 0.4, "Mn": 0.35, "Ag": 0.4, "Zr": 0.11},
    "2099-T83":  {"Al": 94.0, "Cu": 2.7, "Li": 1.75, "Zn": 0.7, "Mg": 0.3, "Mn": 0.3, "Zr": 0.09},
    "2024-T3 (legacy)":  {"Al": 93.5, "Cu": 4.4, "Mg": 1.5, "Mn": 0.6},
    "7075-T6 (legacy)":  {"Al": 90.0, "Zn": 5.6, "Mg": 2.5, "Cu": 1.6, "Cr": 0.23},
}

LITERATURE_PROPS = {
    "2090-T84":         {"yield_strength_MPa": 520, "density_g_cm3": 2.59},
    "2050-T84":         {"yield_strength_MPa": 515, "density_g_cm3": 2.71},
    "2099-T83":         {"yield_strength_MPa": 505, "density_g_cm3": 2.63},
    "2024-T3 (legacy)": {"yield_strength_MPa": 345, "density_g_cm3": 2.78},
    "7075-T6 (legacy)": {"yield_strength_MPa": 503, "density_g_cm3": 2.81},
}


def run_inverse():
    request = InverseDesignRequest(
        elements=["Al", "Cu", "Li", "Mg", "Zr", "Ag", "Mn"],
        targets=[
            # Modern Al-Li stringer targets — light + strong + weldable
            PropertyTarget(name="density_g_cm3",     max_val=2.70, optimize="minimize"),
            PropertyTarget(name="yield_strength_MPa", min_val=450, optimize="maximize"),
            PropertyTarget(name="weldability_score",  min_val=70,  optimize="maximize"),
        ],
        element_bounds={
            "Al": (10.0, 20.0),   # Force Al-majority (90%+ at%)
            "Cu": (1e-3, 0.6),
            "Li": (1e-3, 0.6),
            "Mg": (1e-3, 0.4),
            "Zr": (1e-3, 0.1),
            "Ag": (1e-3, 0.1),
            "Mn": (1e-3, 0.2),
        },
        n_candidates=12,
        n_iterations=5,
        n_init=16,
        batch_size=4,
        seed=42,
    )
    print("Running BoTorch qEHVI on Al-Cu-Li-Mg-Zr-Ag-Mn (Al-majority bias)…")
    candidates = run_inverse_design(request)
    # Keep only Al-rich candidates (≥ 80 at%)
    candidates = [c for c in candidates if (c.composition.get("Al", 0) / sum(c.composition.values())) >= 0.80]
    print(f"  → {len(candidates)} Al-rich candidates  ({sum(c.is_pareto for c in candidates)} on Pareto front)")
    return candidates


def main():
    candidates = run_inverse()

    save_candidates_csv(
        candidates,
        OUT / "pareto_candidates.csv",
        property_keys=["density_g_cm3", "yield_strength_MPa", "hardness_HV", "fatigue_endurance_MPa",
                       "weldability_score", "castability_score", "cost_score", "corrosion_rating"],
    )

    lit_predictions = predict_for_literature(LITERATURE)

    comparison_rows = []
    for name, ref in LITERATURE_PROPS.items():
        pred = lit_predictions.get(name, {})
        comparison_rows.append(compare_table(name, pred, ref, ["yield_strength_MPa", "density_g_cm3"]))

    plot_pareto_scatter(
        candidates,
        x_key="density_g_cm3", y_key="yield_strength_MPa",
        x_label="Density (g/cm³) — minimise", y_label="Yield strength (MPa) — maximise",
        literature={k: {"density_g_cm3": v["density_g_cm3"], "yield_strength_MPa": v["yield_strength_MPa"]} for k, v in LITERATURE_PROPS.items()},
        path=OUT / "pareto_plot.png",
        title="Pareto frontier: Al-Li aerospace stringer alloys",
    )

    plot_property_bars(
        [{"label": k, "predicted": lit_predictions[k].get("yield_strength_MPa"), "literature": v["yield_strength_MPa"]} for k, v in LITERATURE_PROPS.items()],
        property_label="Yield strength (MPa)",
        path=OUT / "ys_comparison.png",
        title="LeilMat YS prediction vs literature — Al-Li alloys",
    )

    plot_property_bars(
        [{"label": k, "predicted": lit_predictions[k].get("density_g_cm3"), "literature": v["density_g_cm3"]} for k, v in LITERATURE_PROPS.items()],
        property_label="Density (g/cm³)",
        path=OUT / "density_comparison.png",
        title="LeilMat density prediction vs literature — Al-Li alloys",
    )

    pareto = [c for c in candidates if c.is_pareto]
    top_candidate = min(pareto, key=lambda c: c.properties.get("density_g_cm3", 999)) if pareto else candidates[0]

    plot_radar_comparison(
        series=[
            {"label": f"LeilMat top: {top_candidate.composition}", "values": top_candidate.properties, "color": "#38bdf8"},
            {"label": "2099-T83",  "values": lit_predictions.get("2099-T83", {}), "color": "#facc15"},
            {"label": "2050-T84",  "values": lit_predictions.get("2050-T84", {}), "color": "#a78bfa"},
        ],
        property_keys=["yield_strength_MPa", "hardness_HV", "fatigue_endurance_MPa", "weldability_score", "castability_score"],
        property_labels=["YS", "HV", "σₑ", "Weld", "Cast"],
        path=OUT / "radar_comparison.png",
        title="Top LeilMat candidate vs modern Al-Li alloys",
    )

    summary = {
        "case_study": "02_aluminum_li_aerospace",
        "problem": {
            "application": "Aerospace fuselage stringer (lightweight)",
            "constraints": "YS ≥ 450 MPa, density ≤ 2.70 g/cm³, weldability ≥ 70",
            "elements": ["Al", "Cu", "Li", "Mg", "Zr", "Ag", "Mn"],
        },
        "method": "BoTorch qEHVI · 16 Sobol seed · 5 BO iterations · q=4",
        "n_candidates": len(candidates),
        "n_pareto": sum(c.is_pareto for c in candidates),
        "top_candidate": {
            "composition": top_candidate.composition,
            "is_pareto": top_candidate.is_pareto,
            "score": round(top_candidate.score, 3),
            "properties": {k: top_candidate.properties.get(k) for k in
                           ["density_g_cm3", "yield_strength_MPa", "hardness_HV",
                            "fatigue_endurance_MPa", "weldability_score", "castability_score",
                            "cost_score", "corrosion_rating", "manufacturability_score"]},
        },
        "literature_comparison": comparison_rows,
    }
    save_summary_json(summary, OUT / "summary.json")
    print(f"\nTop candidate: {top_candidate.composition}")
    print(f"  YS = {top_candidate.properties.get('yield_strength_MPa')} MPa")
    print(f"  ρ  = {top_candidate.properties.get('density_g_cm3')} g/cm³")
    print(f"  Weld = {top_candidate.properties.get('weldability_score')}")
    print(f"\nResults → {OUT}")


if __name__ == "__main__":
    main()
