"""
One-shot training script for property prediction models.

Trains Random Forest regressors on bundled matbench datasets using matminer
Magpie features. Models are cached to `models/` directory and loaded lazily
at request time.

Usage:
    python -m apps.api.ml.training       # trains everything from scratch
    python -m apps.api.ml.training yield  # trains just yield strength model
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path
from typing import Any

import numpy as np

MODELS_DIR = Path(__file__).parent.parent.parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)


def _load_matbench_steels() -> tuple[list[str], list[float]]:
    """Load matminer's bundled matbench_steels dataset (312 steel alloys → yield strength in MPa)."""
    from matminer.datasets import load_dataset
    df = load_dataset("matbench_steels")
    # Columns: 'composition' (str like "Fe0.95Cr0.02..."), 'yield strength' (MPa)
    return df["composition"].tolist(), df["yield strength"].tolist()


def _featurize_compositions(comp_strs: list[str]) -> tuple[np.ndarray, list[int]]:
    """Convert list of composition strings → matrix of Magpie features. Returns (X, kept_indices)."""
    from pymatgen.core import Composition
    from matminer.featurizers.composition import ElementProperty

    ep = ElementProperty.from_preset("magpie")
    X, kept = [], []
    for i, s in enumerate(comp_strs):
        try:
            comp = Composition(s)
            feats = ep.featurize(comp)
            if not any(np.isnan(feats)):
                X.append(feats)
                kept.append(i)
        except Exception:
            continue
    return np.array(X), kept


def train_yield_strength():
    print("→ Loading matbench_steels…")
    comps, ys_targets = _load_matbench_steels()

    print(f"→ Featurizing {len(comps)} compositions with Magpie…")
    X, kept = _featurize_compositions(comps)
    y = np.array([ys_targets[i] for i in kept])
    print(f"   kept {len(kept)}/{len(comps)} valid samples, feature dim = {X.shape[1]}")

    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import cross_val_score, KFold
    from apps.api.ml.ood import fit_ood_detector

    rf = RandomForestRegressor(n_estimators=200, max_depth=None, n_jobs=-1, random_state=42)
    print("→ 5-fold CV…")
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(rf, X, y, cv=kf, scoring="neg_mean_absolute_error", n_jobs=-1)
    mae = -scores.mean()
    std = scores.std()
    print(f"   MAE = {mae:.1f} ± {std:.1f} MPa  (matbench_steels YS range {y.min():.0f}-{y.max():.0f} MPa — high-strength only)")

    print("→ Fitting final model on all data…")
    rf.fit(X, y)

    print("→ Fitting OOD detector (KNN distance in standardized Magpie space)…")
    ood = fit_ood_detector(X, k=5, threshold_quantile=0.95)
    print(f"   in-train distance p50={ood['in_train_dist_p50']:.2f}, p95={ood['in_train_dist_p95']:.2f}, threshold={ood['threshold']:.2f}")

    out = {
        "model": rf,
        "target": "yield_strength_MPa",
        "training_set": "matbench_steels",
        "domain": "high-strength steels (martensitic, maraging, AHSS) — 62-86 at% Fe with multi-alloy additions",
        "n_samples": len(y),
        "cv_mae_MPa": float(mae),
        "cv_std_MPa": float(std),
        "y_min": float(y.min()),
        "y_max": float(y.max()),
        "y_mean": float(y.mean()),
        "ood": ood,
    }
    path = MODELS_DIR / "yield_strength_rf.pkl"
    with open(path, "wb") as f:
        pickle.dump(out, f)
    print(f"✓ Saved → {path}  ({path.stat().st_size / 1024:.1f} KB)")
    return out


def _train_alloy_family(family_name: str, dataset: list[dict], model_filename: str) -> dict:
    """
    Generic small-dataset RF trainer for non-ferrous YS models.
    Uses shallow trees and small ensembles since training data is hand-curated
    (~20-30 samples).
    """
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import KFold, cross_val_score
    from apps.api.ml.alloy_datasets import weight_to_atomic
    from matminer.featurizers.composition import ElementProperty
    from pymatgen.core import Composition

    print(f"→ {family_name}: {len(dataset)} alloys")
    ep = ElementProperty.from_preset("magpie")

    X, y, names = [], [], []
    for entry in dataset:
        try:
            at_pct = weight_to_atomic(entry["composition_wt"])
            comp = Composition(at_pct)
            feats = ep.featurize(comp)
            if not any(np.isnan(feats)):
                X.append(feats)
                y.append(entry["ys_MPa"])
                names.append(entry["name"])
        except Exception as exc:
            print(f"  skipped {entry['name']}: {exc}")
    X = np.array(X)
    y = np.array(y)
    print(f"   kept {len(y)}/{len(dataset)} valid samples, feature dim = {X.shape[1]}")

    # Small dataset → shallow + few trees + cross-validated MAE
    rf = RandomForestRegressor(n_estimators=80, max_depth=6, min_samples_split=3, n_jobs=-1, random_state=42)
    kf = KFold(n_splits=min(5, len(y)), shuffle=True, random_state=42)
    scores = cross_val_score(rf, X, y, cv=kf, scoring="neg_mean_absolute_error", n_jobs=-1)
    mae = -scores.mean()
    std = scores.std()
    print(f"   CV MAE = {mae:.0f} ± {std:.0f} MPa  (over range {y.min():.0f}-{y.max():.0f} MPa)")

    rf.fit(X, y)

    # OOD detector — use a more permissive quantile for small datasets
    # since the in-training distance distribution is sparse.
    from apps.api.ml.ood import fit_ood_detector
    ood = fit_ood_detector(X, k=min(5, len(y) - 1), threshold_quantile=0.97)

    out = {
        "model": rf,
        "target": f"yield_strength_MPa_{family_name}",
        "training_set": family_name,
        "domain": f"hand-curated {family_name}-based alloys (engineering tempers)",
        "n_samples": len(y),
        "cv_mae_MPa": float(mae),
        "cv_std_MPa": float(std),
        "y_min": float(y.min()),
        "y_max": float(y.max()),
        "y_mean": float(y.mean()),
        "alloys": names,
        "ood": ood,
    }
    path = MODELS_DIR / model_filename
    with open(path, "wb") as f:
        pickle.dump(out, f)
    print(f"   ✓ Saved → {path}  ({path.stat().st_size / 1024:.1f} KB)\n")
    return out


def train_aluminum_ys():
    from apps.api.ml.alloy_datasets import ALUMINUM_ALLOYS
    return _train_alloy_family("aluminum", ALUMINUM_ALLOYS, "aluminum_ys_rf.pkl")


def train_titanium_ys():
    from apps.api.ml.alloy_datasets import TITANIUM_ALLOYS
    return _train_alloy_family("titanium", TITANIUM_ALLOYS, "titanium_ys_rf.pkl")


def train_nickel_ys():
    from apps.api.ml.alloy_datasets import NICKEL_ALLOYS
    return _train_alloy_family("nickel", NICKEL_ALLOYS, "nickel_ys_rf.pkl")


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    if arg in ("all", "yield", "steels"):
        train_yield_strength()
    if arg in ("all", "aluminum", "al"):
        train_aluminum_ys()
    if arg in ("all", "titanium", "ti"):
        train_titanium_ys()
    if arg in ("all", "nickel", "ni"):
        train_nickel_ys()


if __name__ == "__main__":
    main()
