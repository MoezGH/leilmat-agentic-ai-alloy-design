"""
apps.api.ml.strengthening_ablation
====================================

Sprint 6 feature-ablation scorecard.

Trains and cross-validates the YS-prediction RF at four feature levels:

  L1 :  Magpie composition only (the original Sprint 1 baseline)
  L2 :  + temper one-hot (Sprint 4)
  L3 :  + engineered physics features (Sprint 6)
  L4 :  L2 + L3 (the production model)

…and reports CV MAE and conformal q for each.  This is the
audit-trail evidence that justifies every layer we built:

* If L2 ≪ L1 → temper is doing work
* If L3 ≪ L1 → physics is doing work
* If L4 ≪ L2 → physics adds info on top of temper

Run:
    python -m apps.api.ml.strengthening_ablation
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import KFold, cross_val_score

from apps.api.ml.alloy_datasets import (
    weight_to_atomic,
    ALUMINUM_ALLOYS, TITANIUM_ALLOYS, NICKEL_ALLOYS, GENERAL_STEEL_ALLOYS,
)
from apps.api.ml.temper.encoding import encode_temper, temper_feature_dim
from apps.api.ml.strengthening import physics_features, physics_feature_dim


def _featurise_all(dataset, family_name):
    """Return four feature matrices for the four ablation levels."""
    from matminer.featurizers.composition import ElementProperty
    from pymatgen.core import Composition
    ep = ElementProperty.from_preset("magpie")

    Xc, Xt, Xp, ys = [], [], [], []
    for entry in dataset:
        try:
            at = weight_to_atomic(entry["composition_wt"])
            feats = ep.featurize(Composition(at))
            if any(np.isnan(feats)):
                continue
            Xc.append(np.array(feats, dtype=float))
            Xt.append(encode_temper(family_name, entry.get("temper")))
            Xp.append(physics_features(entry["composition_wt"],
                                       family_name,
                                       entry.get("temper")))
            ys.append(entry["ys_MPa"])
        except Exception:
            continue
    Xc = np.array(Xc); Xt = np.array(Xt); Xp = np.array(Xp); ys = np.array(ys)
    return {
        "L1_comp":           Xc,
        "L2_comp_temper":    np.concatenate([Xc, Xt], axis=1),
        "L3_comp_physics":   np.concatenate([Xc, Xp], axis=1),
        "L4_comp_temp_phys": np.concatenate([Xc, Xt, Xp], axis=1),
        "_y":                ys,
        "_dims": {
            "L1_comp":           Xc.shape[1],
            "L2_comp_temper":    Xc.shape[1] + Xt.shape[1],
            "L3_comp_physics":   Xc.shape[1] + Xp.shape[1],
            "L4_comp_temp_phys": Xc.shape[1] + Xt.shape[1] + Xp.shape[1],
        },
    }


def _cv_mae(X, y, n_splits=5):
    rf = RandomForestRegressor(n_estimators=80, max_depth=6,
                               min_samples_split=3, n_jobs=-1, random_state=42)
    kf = KFold(n_splits=min(n_splits, len(y)), shuffle=True, random_state=42)
    scores = cross_val_score(rf, X, y, cv=kf,
                             scoring="neg_mean_absolute_error", n_jobs=-1)
    return float(-scores.mean()), float(scores.std())


def run_ablation():
    """Train+CV the four ablation levels for every family."""
    families = [
        ("aluminum",      ALUMINUM_ALLOYS),
        ("titanium",      TITANIUM_ALLOYS),
        ("nickel",        NICKEL_ALLOYS),
        ("general_steel", GENERAL_STEEL_ALLOYS),
    ]
    rows = []
    for fam, dataset in families:
        Xall = _featurise_all(dataset, fam)
        y = Xall.pop("_y")
        dims = Xall.pop("_dims")
        result = {"family": fam, "n_samples": len(y)}
        for level, X in Xall.items():
            mae, std = _cv_mae(X, y)
            result[level + "_mae"] = round(mae, 1)
            result[level + "_std"] = round(std, 1)
            result[level + "_dim"] = dims[level]
        # Improvements
        result["delta_L2_vs_L1"] = round(result["L1_comp_mae"] - result["L2_comp_temper_mae"], 1)
        result["delta_L3_vs_L1"] = round(result["L1_comp_mae"] - result["L3_comp_physics_mae"], 1)
        result["delta_L4_vs_L2"] = round(result["L2_comp_temper_mae"] - result["L4_comp_temp_phys_mae"], 1)
        rows.append(result)
    return rows


def format_table(rows):
    """Return a Markdown table for the scorecard section."""
    lines = [
        "| Family | n | L1 comp only | L2 +temper | L3 +physics | L4 all | Δ(temper) | Δ(physics) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['family']} | {r['n_samples']} | "
            f"{r['L1_comp_mae']} MPa | "
            f"{r['L2_comp_temper_mae']} MPa | "
            f"{r['L3_comp_physics_mae']} MPa | "
            f"**{r['L4_comp_temp_phys_mae']} MPa** | "
            f"{-r['delta_L2_vs_L1']:+.1f} | "
            f"{-r['delta_L4_vs_L2']:+.1f} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print("Sprint 6 feature ablation (5-fold CV MAE in MPa, lower is better)\n")
    rows = run_ablation()
    print(format_table(rows))
    print()
    print("Negative Δ means the layer *reduced* CV MAE (i.e. helped).")
