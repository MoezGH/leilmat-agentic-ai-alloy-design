"""
Case Study 3 — Ni-based superalloy for AM (laser powder-bed fusion) turbine blade.
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
    "Inconel 718":   {"Ni": 53.0, "Cr": 19.0, "Fe": 18.5, "Nb": 5.0, "Mo": 3.0, "Ti": 0.9, "Al": 0.5},
    "Inconel 625":   {"Ni": 61.0, "Cr": 21.5, "Mo": 9.0, "Nb": 3.7, "Fe": 4.0},
    "Inconel 738 LC":{"Ni": 61.0, "Cr": 16.0, "Co": 8.5, "W": 2.6, "Mo": 1.75, "Ta": 1.75, "Nb": 0.9, "Al": 3.4, "Ti": 3.4},
    "Hastelloy X":   {"Ni": 47.0, "Cr": 22.0, "Fe": 18.5, "Mo": 9.0, "Co": 1.5, "W": 0.6},
    "CMSX-4":        {"Ni": 61.5, "Co": 9.0, "Cr": 6.5, "W": 6.0, "Mo": 0.6, "Ta": 6.5, "Al": 5.6, "Ti": 1.0, "Re": 3.0, "Hf": 0.1},
}

LITERATURE_PROPS = {
    "Inconel 718":    {"yield_strength_MPa": 1100, "density_g_cm3": 8.19, "hardness_HV": 360},
    "Inconel 625":    {"yield_strength_MPa": 460,  "density_g_cm3": 8.44, "hardness_HV": 190},
    "Inconel 738 LC": {"yield_strength_MPa": 950,  "density_g_cm3": 8.11, "hardness_HV": 430},
    "Hastelloy X":    {"yield_strength_MPa": 345,  "density_g_cm3": 8.22, "hardness_HV": 230},
    "CMSX-4":         {"yield_strength_MPa": 945,  "density_g_cm3": 8.70, "hardness_HV": 430},
}


def run_inverse():
    request = InverseDesignRequest(
        elements=["Ni", "Cr", "Co", "Mo", "W", "Ta", "Al", "Ti", "Nb", "Fe"],
        targets=[
            PropertyTarget(name="yield_strength_MPa",      min_val=900, optimize="maximize"),
            PropertyTarget(name="manufacturability_score", min_val=40,  optimize="maximize"),
            PropertyTarget(name="cost_score",              min_val=40,  optimize="maximize"),
        ],
        element_bounds={
            "Ni": (8.0, 15.0),     # Force Ni-dominant
            "Cr": (1e-3, 3.0),
            "Co": (1e-3, 2.5),
            "Mo": (1e-3, 1.0),
            "W":  (1e-3, 1.0),
            "Ta": (1e-3, 1.0),
            "Al": (1e-3, 1.0),
            "Ti": (1e-3, 0.8),
            "Nb": (1e-3, 0.8),
            "Fe": (1e-3, 2.0),
        },
        n_candidates=12,
        n_iterations=5,
        n_init=16,
        batch_size=4,
        seed=42,
    )
    print("Running BoTorch qEHVI on 10-element Ni superalloy space (Ni-majority bias)…")
    candidates = run_inverse_design(request)
    candidates = [c for c in candidates if (c.composition.get("Ni", 0) / sum(c.composition.values())) >= 0.40]
    print(f"  → {len(candidates)} Ni-rich candidates  ({sum(c.is_pareto for c in candidates)} on Pareto front)")
    return candidates


def main():
    candidates = run_inverse()

    save_candidates_csv(
        candidates,
        OUT / "pareto_candidates.csv",
        property_keys=["density_g_cm3", "yield_strength_MPa", "hardness_HV", "fatigue_endurance_MPa",
                       "manufacturability_score", "weldability_score", "castability_score",
                       "cost_score", "corrosion_rating"],
    )

    lit_predictions = predict_for_literature(LITERATURE)

    comparison_rows = []
    for name, ref in LITERATURE_PROPS.items():
        pred = lit_predictions.get(name, {})
        comparison_rows.append(compare_table(name, pred, ref, ["yield_strength_MPa", "density_g_cm3", "hardness_HV"]))

    plot_pareto_scatter(
        candidates,
        x_key="cost_score", y_key="yield_strength_MPa",
        x_label="Cost score (higher = cheaper) — maximise", y_label="Yield strength (MPa) — maximise",
        literature={k: {"cost_score": lit_predictions[k].get("cost_score"), "yield_strength_MPa": v["yield_strength_MPa"]} for k, v in LITERATURE_PROPS.items()},
        path=OUT / "pareto_plot.png",
        title="Pareto: cost vs strength for AM-targeted Ni superalloys",
    )

    plot_property_bars(
        [{"label": k, "predicted": lit_predictions[k].get("yield_strength_MPa"), "literature": v["yield_strength_MPa"]} for k, v in LITERATURE_PROPS.items()],
        property_label="Yield strength (MPa)",
        path=OUT / "ys_comparison.png",
        title="LeilMat YS prediction vs literature — Ni superalloys",
    )

    pareto = [c for c in candidates if c.is_pareto]
    top_candidate = max(pareto, key=lambda c: (c.properties.get("yield_strength_MPa") or 0)) if pareto else candidates[0]

    plot_radar_comparison(
        series=[
            {"label": f"LeilMat top: {top_candidate.composition}", "values": top_candidate.properties, "color": "#38bdf8"},
            {"label": "Inconel 718",    "values": lit_predictions.get("Inconel 718", {}), "color": "#facc15"},
            {"label": "Inconel 625",    "values": lit_predictions.get("Inconel 625", {}), "color": "#a78bfa"},
            {"label": "Inconel 738 LC", "values": lit_predictions.get("Inconel 738 LC", {}), "color": "#34d399"},
        ],
        property_keys=["yield_strength_MPa", "hardness_HV", "fatigue_endurance_MPa",
                       "manufacturability_score", "weldability_score", "cost_score"],
        property_labels=["YS", "HV", "σₑ", "Manuf.", "Weld", "Cost"],
        path=OUT / "radar_comparison.png",
        title="Top LeilMat candidate vs Ni superalloys",
    )

    summary = {
        "case_study": "03_nickel_am_turbine",
        "problem": {
            "application": "AM-fabricated turbine blade (laser powder-bed fusion)",
            "constraints": "YS ≥ 900 MPa, manufacturability ≥ 40, cost score ≥ 40",
            "elements": ["Ni", "Cr", "Co", "Mo", "W", "Ta", "Al", "Ti", "Nb", "Fe"],
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
                            "fatigue_endurance_MPa", "manufacturability_score",
                            "weldability_score", "castability_score", "cost_score",
                            "corrosion_rating"]},
        },
        "literature_comparison": comparison_rows,
    }
    save_summary_json(summary, OUT / "summary.json")
    print(f"\nTop candidate: {top_candidate.composition}")
    print(f"  YS = {top_candidate.properties.get('yield_strength_MPa')} MPa")
    print(f"  Manuf. = {top_candidate.properties.get('manufacturability_score')}")
    print(f"  Cost = {top_candidate.properties.get('cost_score')} (${top_candidate.properties.get('cost_per_kg_USD', '?')}/kg)")
    print(f"\nResults → {OUT}")


if __name__ == "__main__":
    main()
