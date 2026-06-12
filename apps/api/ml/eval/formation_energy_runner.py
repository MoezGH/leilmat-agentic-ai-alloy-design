"""
Run the production formation-energy predictor against canonical references.

The production path goes:
    composition (at%) → M3GNet random supercell (N=3 replicas) → mean ± std

We compare predicted ΔH_f against MP-computed PBE-DFT values. M3GNet was
trained on MP-PBE data, so MP values are the "ground truth" the model
should reproduce — published bench-mark MAE is ~50 meV/atom on stoichiometric
materials.

Our random-substitution supercell biases the prediction upward (configurational
disorder costs energy vs. the perfectly-ordered MP entry), so we expect
larger residuals — typically 100-300 meV/atom for ordered intermetallics.

Output schema mirrors holdout_runner:
    {
        "n_total": 18,
        "n_predicted": 18,
        "predictions": [
            {"name": "γ'-Ni3Al", "y_true": -0.4264, "y_pred": -0.401, "abs_err": 0.025, ...},
            ...
        ],
        "mae_eV_per_atom": 0.087,
        "median_abs_err": 0.064,
        "max_abs_err": 0.231,
        "by_class": {
            "pure_element":   {"n": 5,  "mae": 0.002},
            "intermetallic":  {"n": 13, "mae": 0.118},
        },
    }
"""
from __future__ import annotations

from typing import Any

import numpy as np

from apps.api.ml.eval.canonical_phases import (
    PURE_ELEMENTS,
    CANONICAL_INTERMETALLICS,
    ALL_REFERENCES,
)


def _classify(entry: dict) -> str:
    """Return 'pure_element' or 'intermetallic' for grouping."""
    return "pure_element" if entry.get("source") == "by_definition" else "intermetallic"


def run_formation_energy() -> dict[str, Any]:
    """Predict ΔH_f for each canonical reference and report residuals."""
    from apps.api.ml.featurizers import formation_energy_eV_per_atom

    predictions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for entry in ALL_REFERENCES:
        try:
            pred = formation_energy_eV_per_atom(entry["composition"])
        except Exception as exc:
            skipped.append({"name": entry["name"], "reason": str(exc)})
            continue

        y_pred = pred.get("value")
        if y_pred is None:
            skipped.append({"name": entry["name"], "reason": pred.get("error", "no prediction")})
            continue

        y_true = entry["ref_eV_per_atom"]
        abs_err = abs(y_pred - y_true)
        unc = pred.get("uncertainty", 0) or 0
        predictions.append({
            "name": entry["name"],
            "y_true": round(float(y_true), 4),
            "y_pred": round(float(y_pred), 4),
            "abs_err": round(float(abs_err), 4),
            "uncertainty": round(float(unc), 4),
            "in_envelope": bool(abs_err <= unc * 1.5),
            "source": pred.get("source"),
            "n_replicas": pred.get("n_replicas"),
            "class": _classify(entry),
            "mp_id": entry.get("mp_id"),
        })

    if not predictions:
        return {"error": "no predictions produced", "skipped": skipped}

    errs = np.array([p["abs_err"] for p in predictions])
    in_env = sum(p["in_envelope"] for p in predictions)

    by_class: dict[str, dict[str, Any]] = {}
    for cls in ("pure_element", "intermetallic"):
        cls_preds = [p for p in predictions if p["class"] == cls]
        if not cls_preds:
            continue
        cls_errs = np.array([p["abs_err"] for p in cls_preds])
        by_class[cls] = {
            "n": len(cls_preds),
            "mae_eV_per_atom":      round(float(cls_errs.mean()), 4),
            "median_abs_err":       round(float(np.median(cls_errs)), 4),
            "max_abs_err":          round(float(cls_errs.max()), 4),
        }

    # Headline accuracy is the INTERMETALLIC MAE.  Pure elements have
    # ΔH_f ≡ 0 by definition, so predicting ~0 for them is a tautology, not a
    # model success — folding them into the overall mean deflates it.  We
    # surface the intermetallic figure explicitly so the scorecard can't quote
    # the padded number as the benchmark result.
    inter = by_class.get("intermetallic")
    headline = inter["mae_eV_per_atom"] if inter else None

    return {
        "n_total":     len(ALL_REFERENCES),
        "n_predicted": len(predictions),
        "n_skipped":   len(skipped),
        "mae_eV_per_atom":  round(float(errs.mean()), 4),
        "headline_mae_intermetallic_eV_per_atom": headline,
        "median_abs_err":   round(float(np.median(errs)), 4),
        "max_abs_err":      round(float(errs.max()), 4),
        "in_envelope_pct":  round(100 * in_env / len(predictions), 1),
        "note": ("Headline accuracy = intermetallic MAE; pure-element "
                 "references have ΔH_f ≡ 0 by definition and are sanity "
                 "checks, not benchmark points.  The blended mae_eV_per_atom "
                 "is deflated by those zeros."),
        "by_class": by_class,
        "predictions": sorted(predictions, key=lambda p: -p["abs_err"]),
        "skipped":     skipped,
    }


if __name__ == "__main__":
    import json
    result = run_formation_energy()
    print(json.dumps(result, indent=2))
