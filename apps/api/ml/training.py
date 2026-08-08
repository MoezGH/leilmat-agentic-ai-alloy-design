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

    print("→ Fitting conformal calibrator (split-conformal via held-out fold residuals)…")
    # For the large steel dataset, use a single 80/20 split (LOO would be ~30 min).
    from apps.api.ml.calibration import SplitConformalPredictor
    from sklearn.model_selection import train_test_split
    X_tr, X_cal, y_tr, y_cal = train_test_split(X, y, test_size=0.20, random_state=42)
    rf_cal = RandomForestRegressor(n_estimators=200, max_depth=None, n_jobs=-1, random_state=42)
    rf_cal.fit(X_tr, y_tr)
    cal_residuals, cal_sigmas = [], []
    for xi, yi in zip(X_cal, y_cal):
        tree_preds = np.array([t.predict(xi.reshape(1, -1))[0] for t in rf_cal.estimators_])
        cal_residuals.append(abs(yi - float(tree_preds.mean())))
        cal_sigmas.append(float(tree_preds.std()))
    calibrator = SplitConformalPredictor(alpha=0.10).fit(
        np.array(cal_residuals), sigmas=np.array(cal_sigmas)
    )
    print(f"   conformal q={calibrator.q:.2f}, "
          f"empirical coverage on cal set = {calibrator.empirical_coverage:.1%} "
          f"(target 90%, n_cal={calibrator.n_calibration})")

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
        "conformal": calibrator.to_dict(),
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
    (~20-100 samples).

    Sprint 4: temper is included as an auxiliary feature.  Each training row
    becomes ``[magpie_composition_features..., temper_one_hot..., strength_index]``,
    letting the model learn that 6061-O and 6061-T6 are different points in
    feature space despite identical composition.
    """
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import KFold, cross_val_score
    from apps.api.ml.alloy_datasets import weight_to_atomic
    from apps.api.ml.temper.encoding import (
        encode_temper, canonicalise_temper, temper_feature_dim, TEMPER_VOCABULARY,
    )
    from apps.api.ml.strengthening import (
        physics_features, physics_feature_dim, PHYSICS_FEATURE_NAMES,
        precipitate_radius_nm,
    )
    from apps.api.ml.datasets.aging_schedules import schedule_for
    from matminer.featurizers.composition import ElementProperty
    from pymatgen.core import Composition

    print(f"→ {family_name}: {len(dataset)} alloys")
    ep = ElementProperty.from_preset("magpie")

    X, y, names, tempers_seen = [], [], [], []
    # Task #9: schedule-derived precipitate radii actually used, per temper.
    # Persisted on the bundle so inference (which usually has no schedule) can
    # fall back to the centre of the training distribution instead of the
    # canonical constant — otherwise the no-schedule path is a train/inference
    # skew of exactly the kind fixed in 18bf983.
    radii_by_temper: dict[str, list[float]] = {}
    for entry in dataset:
        try:
            at_pct = weight_to_atomic(entry["composition_wt"])
            comp = Composition(at_pct)
            comp_feats = ep.featurize(comp)
            if any(np.isnan(comp_feats)):
                continue
            # Sprint 4: append temper features
            temper_canonical = canonicalise_temper(family_name, entry.get("temper"))
            temper_feats = encode_temper(family_name, entry.get("temper"))
            # Sprint 6: append engineered physics features
            sched = schedule_for(entry["name"])
            age_T = sched["T_C"] if sched else None
            age_t = sched["time_s"] if sched else None
            r_used = precipitate_radius_nm(family_name, age_T, age_t)
            if r_used is not None:
                radii_by_temper.setdefault(temper_canonical, []).append(r_used)
            phys_feats = physics_features(
                entry["composition_wt"], family_name, entry.get("temper"),
                age_T, age_t,
            )
            row = np.concatenate([comp_feats, temper_feats, phys_feats])
            X.append(row)
            y.append(entry["ys_MPa"])
            names.append(entry["name"])
            tempers_seen.append(temper_canonical)
        except Exception as exc:
            print(f"  skipped {entry['name']}: {exc}")
    X = np.array(X)
    y = np.array(y)
    n_temper_dims = temper_feature_dim(family_name)
    n_phys_dims   = physics_feature_dim()
    n_comp_dims   = X.shape[1] - n_temper_dims - n_phys_dims
    from collections import Counter
    temper_counts = Counter(tempers_seen)
    print(f"   kept {len(y)}/{len(dataset)} valid samples; "
          f"feature dim = {X.shape[1]} "
          f"({n_comp_dims} composition + {n_temper_dims} temper + {n_phys_dims} physics)")
    print(f"   temper coverage: {len(temper_counts)} unique  "
          f"top 5: {dict(temper_counts.most_common(5))}")

    # Small dataset → shallow + few trees + cross-validated MAE
    rf = RandomForestRegressor(n_estimators=80, max_depth=6, min_samples_split=3, n_jobs=-1, random_state=42)
    kf = KFold(n_splits=min(5, len(y)), shuffle=True, random_state=42)
    scores = cross_val_score(rf, X, y, cv=kf, scoring="neg_mean_absolute_error", n_jobs=-1)
    mae = -scores.mean()
    std = scores.std()
    print(f"   CV MAE = {mae:.0f} ± {std:.0f} MPa  (over range {y.min():.0f}-{y.max():.0f} MPa)")

    rf.fit(X, y)

    # OOD detector — fit on **composition features only** so a novel
    # composition gets correctly flagged even when the user supplies a
    # well-known temper.  Otherwise the temper one-hot would dominate the
    # KNN distance and mask OOD compositions.
    from apps.api.ml.ood import (
        fit_element_bounds, fit_ood_detector, fit_ubiquitous_elements,
    )
    X_comp = X[:, :n_comp_dims]
    ood = fit_ood_detector(X_comp, k=min(5, len(y) - 1), threshold_quantile=0.97)

    # Composition-space companion to the KNN gate.  The KNN scores aggregate
    # Magpie statistics, which barely move when one element is swapped for a
    # chemically similar one — so a single-element blowup (Ti-20Cu against a
    # 0.5 wt% training max) can score in-domain.  See ood.check_element_bounds.
    element_bounds = fit_element_bounds(dataset)

    # Diagnostic only, never a gate: elements this family almost always has.
    # Lets an OOD refusal say "you left out C and Si" instead of quoting a
    # KNN distance nobody can act on.  See ood.fit_ubiquitous_elements.
    ubiquitous_elements = fit_ubiquitous_elements(dataset)

    # Conformal calibrator — LOO on the *full* feature matrix (temper
    # included).  Heteroscedastic via tree-variance σ̂.  Conditioning on
    # temper is the whole point of Sprint 4: the residuals at fixed temper
    # are smaller than across all tempers.
    print(f"   fitting conformal calibrator via LOO …")
    from apps.api.ml.calibration import fit_loo_conformal
    rf_params_for_cal = dict(n_estimators=80, max_depth=6, min_samples_split=3, n_jobs=-1, random_state=42)
    calibrator = fit_loo_conformal(X, y, rf_params_for_cal, alpha=0.10, heteroscedastic=True)
    print(f"   conformal q={calibrator.q:.2f}, "
          f"empirical coverage on LOO set = {calibrator.empirical_coverage:.1%} "
          f"(target 90%, n_cal={calibrator.n_calibration})")

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
        "element_bounds": element_bounds,
        "ubiquitous_elements": ubiquitous_elements,
        "conformal": calibrator.to_dict(),
        # Sprint 4 — temper-aware model bundle
        "temper_aware": True,
        "temper_family": family_name,
        "n_composition_features": int(n_comp_dims),
        "n_temper_features": int(n_temper_dims),
        "temper_vocabulary": list(TEMPER_VOCABULARY[family_name]),
        "tempers_in_training": dict(temper_counts),
        # Sprint 6 — engineered physics features (concatenated last)
        "physics_aware": True,
        "n_physics_features": int(n_phys_dims),
        "physics_feature_names": list(PHYSICS_FEATURE_NAMES),
        # Task #9 — median schedule-derived radius per temper, for the
        # no-schedule inference fallback.  Absent for families/tempers where
        # no training row carried a schedule; callers must handle None.
        "median_radius_nm_by_temper": {
            t: float(np.median(v)) for t, v in radii_by_temper.items() if v
        },
        "n_rows_with_aging_schedule": int(sum(len(v) for v in radii_by_temper.values())),
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


def train_general_steel_ys():
    """Train the general-engineering-steels model — covers the gap that
    matbench_steels (ultra-high-strength only) leaves below 1000 MPa."""
    from apps.api.ml.alloy_datasets import GENERAL_STEEL_ALLOYS
    return _train_alloy_family("general_steel", GENERAL_STEEL_ALLOYS, "general_steel_ys_rf.pkl")


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
    if arg in ("all", "general_steel", "gen_steel"):
        train_general_steel_ys()


if __name__ == "__main__":
    main()
