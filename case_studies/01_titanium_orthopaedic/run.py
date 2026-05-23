"""
Case Study 1 — V-free Ti alloy for orthopaedic implant.

Reproduces all results in this directory. Run:
    source .venv/bin/activate
    python case_studies/01_titanium_orthopaedic/run.py
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


# ── Reference orthopaedic Ti alloys from literature ─────────────────────
# Compositions in weight % (converted to atomic % via pymatgen during predict)
LITERATURE = {
    "Ti-6Al-4V ELI (F136)": {"Ti": 90.0, "Al": 6.0, "V": 4.0},
    "Ti-6Al-7Nb (F1295)":   {"Ti": 87.0, "Al": 6.0, "Nb": 7.0},
    "Ti-13Nb-13Zr (F1713)": {"Ti": 74.0, "Nb": 13.0, "Zr": 13.0},
    "Ti-15Mo (F2066)":      {"Ti": 85.0, "Mo": 15.0},
    "Ti-35Nb-7Zr-5Ta":      {"Ti": 53.0, "Nb": 35.0, "Zr": 7.0, "Ta": 5.0},
}

# Literature mechanical / physical data (handbook values)
LITERATURE_PROPS = {
    "Ti-6Al-4V ELI (F136)":  {"yield_strength_MPa": 795, "density_g_cm3": 4.43, "hardness_HV": 330},
    "Ti-6Al-7Nb (F1295)":    {"yield_strength_MPa": 800, "density_g_cm3": 4.52, "hardness_HV": 320},
    "Ti-13Nb-13Zr (F1713)":  {"yield_strength_MPa": 880, "density_g_cm3": 4.96, "hardness_HV": 280},
    "Ti-15Mo (F2066)":       {"yield_strength_MPa": 875, "density_g_cm3": 4.95, "hardness_HV": 270},
    "Ti-35Nb-7Zr-5Ta":       {"yield_strength_MPa": 530, "density_g_cm3": 5.06, "hardness_HV": 220},
}


def run_inverse():
    """BoTorch qEHVI: Ti-majority biased search, density in Ti range, YS maximised."""
    request = InverseDesignRequest(
        elements=["Ti", "Al", "Nb", "Mo", "Zr"],     # V deliberately excluded — cytotoxic
        targets=[
            # Density in the Ti-alloy range — orthopaedic implants need stiffness-matched 4.4-5.0 g/cm³
            PropertyTarget(name="density_g_cm3",     min_val=4.2, max_val=5.0, optimize="range"),
            PropertyTarget(name="yield_strength_MPa", min_val=800, optimize="maximize"),
        ],
        # Bias Ti to dominate via large raw-bound (post-normalisation Ti will be 60-90 at%)
        element_bounds={
            "Ti": (5.0, 10.0),
            "Al": (1e-3, 1.5),
            "Nb": (1e-3, 1.5),
            "Mo": (1e-3, 1.0),
            "Zr": (1e-3, 1.0),
        },
        n_candidates=12,
        n_iterations=5,
        n_init=16,
        batch_size=4,
        seed=42,
    )
    print("Running BoTorch qEHVI on Ti-Al-Nb-Mo-Zr (Ti-majority bias)…")
    candidates = run_inverse_design(request)
    # Hard filter — must actually be a Ti-rich alloy
    candidates = [c for c in candidates if (c.composition.get("Ti", 0) / sum(c.composition.values())) >= 0.5]
    print(f"  → {len(candidates)} Ti-rich candidates  ({sum(c.is_pareto for c in candidates)} on Pareto front)")
    return candidates


def main():
    candidates = run_inverse()

    # ── Save raw candidates as CSV ──
    save_candidates_csv(
        candidates,
        OUT / "pareto_candidates.csv",
        property_keys=["density_g_cm3", "yield_strength_MPa", "hardness_HV", "fatigue_endurance_MPa", "corrosion_rating", "cost_per_kg_USD"],
    )

    # ── Predict properties for literature alloys via LeilMat ──
    lit_predictions = predict_for_literature(LITERATURE)

    # ── Build comparison table ──
    comparison_rows = []
    for name, ref in LITERATURE_PROPS.items():
        pred = lit_predictions.get(name, {})
        comparison_rows.append(compare_table(name, pred, ref, ["yield_strength_MPa", "density_g_cm3", "hardness_HV"]))

    # ── Figures ──
    plot_pareto_scatter(
        candidates,
        x_key="density_g_cm3", y_key="yield_strength_MPa",
        x_label="Density (g/cm³) — minimise", y_label="Yield Strength (MPa) — maximise",
        literature={k: {"density_g_cm3": v["density_g_cm3"], "yield_strength_MPa": v["yield_strength_MPa"]} for k, v in LITERATURE_PROPS.items()},
        path=OUT / "pareto_plot.png",
        title="Pareto frontier: V-free Ti orthopaedic alloys",
    )

    plot_property_bars(
        [{"label": k.split(" (")[0], "predicted": lit_predictions[k].get("yield_strength_MPa"), "literature": v["yield_strength_MPa"]} for k, v in LITERATURE_PROPS.items()],
        property_label="Yield strength (MPa)",
        path=OUT / "ys_comparison.png",
        title="LeilMat YS prediction vs literature — Ti orthopaedic alloys",
    )

    # Top Pareto candidate (lowest density on the front meeting YS ≥ 800)
    pareto_meeting_spec = [c for c in candidates if c.is_pareto and (c.properties.get("yield_strength_MPa") or 0) >= 800]
    top_candidate = min(pareto_meeting_spec, key=lambda c: c.properties.get("density_g_cm3", 999)) if pareto_meeting_spec else candidates[0]

    plot_radar_comparison(
        series=[
            {"label": f"LeilMat top: {top_candidate.composition}", "values": top_candidate.properties, "color": "#38bdf8"},
            {"label": "Ti-6Al-4V ELI",   "values": lit_predictions.get("Ti-6Al-4V ELI (F136)", {}), "color": "#facc15"},
            {"label": "Ti-6Al-7Nb",      "values": lit_predictions.get("Ti-6Al-7Nb (F1295)", {}), "color": "#a78bfa"},
            {"label": "Ti-13Nb-13Zr",    "values": lit_predictions.get("Ti-13Nb-13Zr (F1713)", {}), "color": "#34d399"},
        ],
        property_keys=["yield_strength_MPa", "hardness_HV", "fatigue_endurance_MPa", "melting_point_K", "manufacturability_score"],
        property_labels=["YS", "HV", "σₑ", "Tₘ", "Manuf."],
        path=OUT / "radar_comparison.png",
        title="Top LeilMat candidate vs orthopaedic Ti alloys",
    )

    # ── Summary JSON ──
    summary = {
        "case_study": "01_titanium_orthopaedic",
        "problem": {
            "application": "Orthopaedic implant (hip stem)",
            "constraints": "YS ≥ 800 MPa, density ≤ 4.7 g/cm³, V-free (cytotoxicity)",
            "elements": ["Ti", "Al", "Nb", "Mo", "Zr"],
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
                            "fatigue_endurance_MPa", "corrosion_rating",
                            "manufacturability_score", "cost_per_kg_USD"]},
        },
        "literature_comparison": comparison_rows,
    }
    save_summary_json(summary, OUT / "summary.json")
    print(f"\nTop candidate: {top_candidate.composition}")
    print(f"  YS = {top_candidate.properties.get('yield_strength_MPa')} MPa")
    print(f"  ρ  = {top_candidate.properties.get('density_g_cm3')} g/cm³")
    print(f"  HV = {top_candidate.properties.get('hardness_HV')} HV")
    print(f"  Corrosion = {top_candidate.properties.get('corrosion_rating')}")
    print(f"\nResults → {OUT}")


if __name__ == "__main__":
    main()
