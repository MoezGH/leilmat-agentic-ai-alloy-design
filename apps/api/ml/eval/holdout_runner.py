"""
Run the production yield-strength predictor against the held-out canonical
alloys (which are NOT in any training dataset).

This is the most realistic measure of how the model performs in production:
- Uses the saved .pkl model (not a refit)
- Goes through the family-routing logic in matgl_models.py
- Converts wt% → at% the same way the API does

Output schema:
    {
        "family": "aluminum",
        "n_total": 5,
        "n_predicted": 5,
        "predictions": [
            {"name": "2618-T651", "y_true": 372, "y_pred": 391, "abs_err": 19, "source": "rf_aluminum"},
            ...
        ],
        "mae": 28.4,
        "median_abs_err": 19.0,
        "max_abs_err": 67.2,
        "in_uncertainty_envelope_pct": 80,   # share of predictions where |err| ≤ uncertainty
    }
"""
from __future__ import annotations

from typing import Any

import numpy as np

from apps.api.ml.alloy_datasets import weight_to_atomic
from apps.api.ml.matgl_models import yield_strength_MPa
from apps.api.ml.eval.holdout_alloys import (
    ALUMINUM_HOLDOUT,
    TITANIUM_HOLDOUT,
    NICKEL_HOLDOUT,
    STEEL_REFERENCES,
)


def _run_family(family: str, alloys: list[dict]) -> dict[str, Any]:
    """Predict each held-out alloy with the production model.

    Reports per-alloy outcome with three categories:
        - "correct_in_domain":  expected in-domain, model predicted (success)
        - "correct_out_of_domain": expected OOD, model refused (success)
        - "unexpected_ood":     expected in-domain, model refused (false-negative)
        - "unexpected_predict": expected OOD, model predicted (false-positive — most dangerous)
    """
    predictions: list[dict[str, Any]] = []
    refusals:    list[dict[str, Any]] = []

    for entry in alloys:
        at_pct = weight_to_atomic(entry["composition_wt"])
        pred = yield_strength_MPa(at_pct)
        y_pred = pred.get("value")
        expected_in = entry.get("expected_in_domain", True)
        is_refused = y_pred is None and "out_of_domain" in (pred.get("source") or "")

        row = {
            "name": entry["name"],
            "y_true": float(entry["ys_MPa"]),
            "expected_in_domain": expected_in,
            "ood_ratio": pred.get("ood_ratio"),
            "source": pred.get("source"),
        }
        if y_pred is not None:
            abs_err = abs(y_pred - entry["ys_MPa"])
            unc = pred.get("uncertainty", 0) or 0
            ci_low  = pred.get("ci_low")
            ci_high = pred.get("ci_high")
            in_ci = (ci_low is not None and ci_high is not None
                     and ci_low <= entry["ys_MPa"] <= ci_high)
            row.update({
                "y_pred": float(y_pred),
                "abs_err": round(abs_err, 1),
                "uncertainty": float(unc),
                "ci_low":  ci_low,
                "ci_high": ci_high,
                "in_envelope": bool(abs_err <= unc * 1.5),
                "in_ci": in_ci,
                "coverage_target": pred.get("coverage"),
                "outcome": "correct_predict" if expected_in else "unexpected_predict",
            })
            predictions.append(row)
        else:
            row.update({
                "reason": pred.get("error", "no prediction"),
                "outcome": "correct_refuse" if (not expected_in and is_refused) else "unexpected_refuse",
            })
            refusals.append(row)

    # Compute MAE only over in-domain alloys that produced predictions
    in_domain_preds = [p for p in predictions if p.get("outcome") == "correct_predict"]
    errs = np.array([p["abs_err"] for p in in_domain_preds]) if in_domain_preds else np.array([])
    in_env = sum(p.get("in_envelope", False) for p in in_domain_preds)
    in_ci  = sum(p.get("in_ci",       False) for p in in_domain_preds)

    correct_refuse  = sum(r["outcome"] == "correct_refuse"  for r in refusals)
    unexpected_refuse = sum(r["outcome"] == "unexpected_refuse" for r in refusals)
    unexpected_predict = sum(p["outcome"] == "unexpected_predict" for p in predictions)

    return {
        "family": family,
        "n_total": len(alloys),
        "n_predictions": len(predictions),
        "n_refusals":   len(refusals),
        "n_correct_predict":   len(in_domain_preds),
        "n_correct_refuse":    correct_refuse,
        "n_unexpected_refuse": unexpected_refuse,
        "n_unexpected_predict": unexpected_predict,
        "mae": round(float(errs.mean()), 1) if len(errs) else None,
        "median_abs_err": round(float(np.median(errs)), 1) if len(errs) else None,
        "max_abs_err":    round(float(errs.max()), 1) if len(errs) else None,
        "in_envelope_pct": round(100 * in_env / len(in_domain_preds), 1) if in_domain_preds else None,
        "ci_coverage_pct": round(100 * in_ci  / len(in_domain_preds), 1) if in_domain_preds else None,
        "predictions": sorted(predictions, key=lambda d: -d.get("abs_err", 0)),
        "refusals":    refusals,
    }


def run_aluminum() -> dict[str, Any]:
    return _run_family("aluminum", ALUMINUM_HOLDOUT)


def run_titanium() -> dict[str, Any]:
    return _run_family("titanium", TITANIUM_HOLDOUT)


def run_nickel() -> dict[str, Any]:
    return _run_family("nickel", NICKEL_HOLDOUT)


def run_steel() -> dict[str, Any]:
    return _run_family("steel", STEEL_REFERENCES)


def run_all() -> dict[str, dict[str, Any]]:
    return {
        "aluminum": run_aluminum(),
        "titanium": run_titanium(),
        "nickel":   run_nickel(),
        "steel":    run_steel(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_all(), indent=2))
