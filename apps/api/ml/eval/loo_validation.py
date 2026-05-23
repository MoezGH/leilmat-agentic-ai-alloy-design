"""
Leave-one-out cross-validation for the small non-ferrous yield-strength models.

For each curated alloy in a family dataset, we refit the Random Forest on the
remaining N-1 alloys and predict the held-out one. The resulting residuals are
the most honest possible measure of the model's accuracy on its own data — no
training-set leakage.

This is too slow for the matbench_steels model (n=312, ~30 min) but cheap for
the hand-curated non-ferrous families (n ≈ 20-30, < 1 min each).

Output schema:
    {
      "family": "aluminum",
      "n": 29,
      "loo_mae": 71.2,
      "loo_std_residual": 89.4,
      "y_min": 105, "y_max": 700,
      "residuals": [
          {"name": "2014-T6", "y_true": 414, "y_pred": 402, "abs_err": 12},
          ...
      ],
    }
"""
from __future__ import annotations

from typing import Any

import numpy as np

from apps.api.ml.alloy_datasets import (
    ALUMINUM_ALLOYS,
    TITANIUM_ALLOYS,
    NICKEL_ALLOYS,
    weight_to_atomic,
)


_RF_PARAMS = dict(n_estimators=80, max_depth=6, min_samples_split=3, n_jobs=-1, random_state=42)


def _featurize(dataset: list[dict]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Convert a list of alloy entries to (X, y, names) matrices."""
    from matminer.featurizers.composition import ElementProperty
    from pymatgen.core import Composition

    ep = ElementProperty.from_preset("magpie")
    X, y, names = [], [], []
    for entry in dataset:
        try:
            at_pct = weight_to_atomic(entry["composition_wt"])
            feats = ep.featurize(Composition(at_pct))
            if not any(np.isnan(feats)):
                X.append(feats)
                y.append(entry["ys_MPa"])
                names.append(entry["name"])
        except Exception:
            continue
    return np.array(X), np.array(y), names


def loo_validate(family: str, dataset: list[dict]) -> dict[str, Any]:
    """Run leave-one-out cross-validation on a small alloy family."""
    from sklearn.ensemble import RandomForestRegressor

    X, y, names = _featurize(dataset)
    n = len(y)
    if n < 5:
        return {"family": family, "n": n, "error": "dataset too small for LOO"}

    residuals: list[dict[str, Any]] = []
    preds = np.zeros(n)
    for i in range(n):
        mask = np.arange(n) != i
        rf = RandomForestRegressor(**_RF_PARAMS)
        rf.fit(X[mask], y[mask])
        preds[i] = rf.predict(X[i:i + 1])[0]
        residuals.append({
            "name": names[i],
            "y_true": float(y[i]),
            "y_pred": round(float(preds[i]), 1),
            "abs_err": round(float(abs(preds[i] - y[i])), 1),
        })

    errs = np.abs(preds - y)
    return {
        "family": family,
        "n": n,
        "loo_mae": round(float(errs.mean()), 1),
        "loo_median_abs_err": round(float(np.median(errs)), 1),
        "loo_std_residual": round(float((preds - y).std()), 1),
        "loo_max_abs_err": round(float(errs.max()), 1),
        "y_min": float(y.min()),
        "y_max": float(y.max()),
        "residuals": sorted(residuals, key=lambda d: -d["abs_err"]),
    }


def loo_aluminum() -> dict[str, Any]:
    return loo_validate("aluminum", ALUMINUM_ALLOYS)


def loo_titanium() -> dict[str, Any]:
    return loo_validate("titanium", TITANIUM_ALLOYS)


def loo_nickel() -> dict[str, Any]:
    return loo_validate("nickel", NICKEL_ALLOYS)


def all_loo() -> dict[str, dict[str, Any]]:
    return {
        "aluminum": loo_aluminum(),
        "titanium": loo_titanium(),
        "nickel":   loo_nickel(),
    }


if __name__ == "__main__":
    import json
    results = all_loo()
    # Drop the per-alloy residuals when dumping for readability
    summary = {k: {kk: vv for kk, vv in v.items() if kk != "residuals"} for k, v in results.items()}
    print(json.dumps(summary, indent=2))
