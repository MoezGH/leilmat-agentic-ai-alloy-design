"""
Out-of-distribution (OOD) gate for the yield-strength predictors.

Why this exists:
    matbench_steels (the training set for the Fe-based YS model) contains 312
    *high-strength* steels — every alloy has YS in 1000-2510 MPa, every alloy
    has at least trace amounts of Mn+Si+Cr+Ni+Mo+Co+Al. When a user asks the
    model about a mild structural steel (AISI 1018) or austenitic stainless
    (304SS), those compositions are far outside the training envelope and the
    model returns nonsense (e.g. 2331 MPa for 304 SS — real value is 215 MPa).

    This module fits a k-nearest-neighbor distance estimator on the training
    features. At inference time, we compute the test point's distance to its
    K nearest training neighbors; if that distance exceeds a percentile of
    within-training distances, the prediction is flagged as out-of-domain.

Storage:
    The OOD detector is a small dict stored alongside the model bundle:
        bundle["ood"] = {
            "scaler_mean":   np.ndarray (132,) — feature centring
            "scaler_scale":  np.ndarray (132,) — feature scaling (std)
            "knn":           sklearn.NearestNeighbors fit on standardized X
            "threshold":     float — distance above which a point is OOD
            "threshold_quantile": float — which percentile we used (e.g. 0.95)
            "k":             int — neighbors used for distance averaging
        }
"""
from __future__ import annotations

from typing import Any

import numpy as np


def fit_ood_detector(
    X: np.ndarray,
    k: int = 5,
    threshold_quantile: float = 0.95,
) -> dict[str, Any]:
    """
    Fit a KNN-distance OOD detector on training features.

    For each training point, compute the mean distance to its K nearest
    neighbors (excluding itself). The threshold is set to the specified
    quantile of these distances — so by construction, ~5% of training
    points are at-or-above the threshold (consistent with a 95% in-domain
    expectation).
    """
    from sklearn.neighbors import NearestNeighbors

    # Standardize features (essential — Magpie features have very different scales).
    # Features with effectively zero training variance carry no OOD signal:
    # contribute 0 to the standardized distance rather than dividing by ~0.
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    eps = 1e-6
    safe_std = np.where(std > eps, std, 1.0)
    Xs = np.where(std > eps, (X - mean) / safe_std, 0.0)

    # Fit KNN on standardized features, K+1 to skip the self-match
    knn = NearestNeighbors(n_neighbors=k + 1, n_jobs=-1)
    knn.fit(Xs)

    # In-training distances: average distance to K neighbors (skip self)
    dists, _ = knn.kneighbors(Xs)
    in_train_dists = dists[:, 1:].mean(axis=1)   # mean over K, skip self at idx 0

    threshold = float(np.quantile(in_train_dists, threshold_quantile))

    return {
        "scaler_mean":  mean.tolist(),
        "scaler_scale": std.tolist(),
        "knn":          knn,
        "threshold":    threshold,
        "threshold_quantile": threshold_quantile,
        "k":            k,
        "in_train_dist_min":  float(in_train_dists.min()),
        "in_train_dist_p50":  float(np.median(in_train_dists)),
        "in_train_dist_p95":  float(np.percentile(in_train_dists, 95)),
        "in_train_dist_max":  float(in_train_dists.max()),
    }


def fit_element_bounds(alloys: list[dict[str, Any]]) -> dict[str, float]:
    """
    Record the maximum **atomic-%** of each element across a family's training rows.

    Training data is stored as ``composition_wt`` (weight %), but the inference
    path (``matgl_models._predict_one_family``) receives atomic %, so the bounds
    are converted here — comparing a wt% cap against an at% query would silently
    mis-scale every ratio for light/heavy element pairs.

    Companion to the KNN detector, which works in *feature* space.  This works
    in *composition* space, and the two catch different failure modes — see
    ``check_element_bounds`` for why both are needed.
    """
    from apps.api.ml.alloy_datasets import weight_to_atomic

    bounds: dict[str, float] = {}
    for entry in alloys:
        comp_wt = entry.get("composition_wt") or {}
        if not comp_wt:
            continue
        try:
            comp_at = weight_to_atomic(comp_wt)
        except Exception:
            continue  # one malformed row must not kill training
        for el, at in comp_at.items():
            try:
                a = float(at)
            except (TypeError, ValueError):
                continue
            if a > bounds.get(el, 0.0):
                bounds[el] = a
    return bounds


def fit_ubiquitous_elements(
    alloys: list[dict[str, Any]], *, presence_threshold: float = 0.9,
) -> dict[str, float]:
    """
    Elements present in ≥ ``presence_threshold`` of a family's training rows,
    mapped to their median **weight %**.

    Purpose is diagnostic, not gating.  Magpie descriptors include
    min/max/range statistics computed over the elements *present*, with no
    concentration weighting — so a 0.05 wt% carbon in a steel moves
    ``minimum AtomicWeight`` from 52 to 12 exactly as hard as 50 wt% would.
    Omitting a trace element therefore throws the feature vector far outside
    the training cloud, and the KNN gate refuses.

    That refusal is CORRECT — measured on AISI 316, dropping C and Si moves
    the general_steel model's own output from 218 MPa (literature ~215) to
    831 MPa.  The prediction really is garbage without them.  What was wrong
    was the *explanation*: users saw an opaque "KNN distance 398 vs threshold
    16" when the actionable fact is "you left out carbon".

    This is what lets the refusal say that instead.
    """
    from collections import Counter

    counts: Counter = Counter()
    values: dict[str, list[float]] = {}
    n_rows = 0
    for entry in alloys:
        comp_wt = entry.get("composition_wt") or {}
        if not comp_wt:
            continue
        n_rows += 1
        for el, w in comp_wt.items():
            try:
                wv = float(w)
            except (TypeError, ValueError):
                continue
            if wv <= 0:
                continue
            counts[el] += 1
            values.setdefault(el, []).append(wv)
    if n_rows == 0:
        return {}

    out: dict[str, float] = {}
    for el, c in counts.items():
        if c / n_rows >= presence_threshold:
            vs = sorted(values[el])
            mid = len(vs) // 2
            median = vs[mid] if len(vs) % 2 else 0.5 * (vs[mid - 1] + vs[mid])
            out[el] = round(median, 4)
    return out


def find_missing_ubiquitous(
    ubiquitous: dict[str, float], composition: dict[str, float],
) -> dict[str, float]:
    """Elements the family almost always has that this composition lacks.

    Units-agnostic — only element presence is compared, so it is safe to pass
    either a weight-% or atomic-% composition.
    """
    if not ubiquitous:
        return {}
    present = {el for el, v in (composition or {}).items()
               if isinstance(v, (int, float)) and v > 0}
    return {el: typ for el, typ in ubiquitous.items() if el not in present}


def check_element_bounds(
    bounds: dict[str, float],
    composition_at: dict[str, float],
    *,
    max_extrapolation: float = 8.0,
    trace_floor_at: float = 0.05,
) -> tuple[bool, float, str | None]:
    """
    Flag compositions that push a single element far beyond its training range.

    Both ``bounds`` and ``composition_at`` are in **atomic %** (see
    ``fit_element_bounds``).

    Why this exists in addition to the KNN gate:
        The KNN detector scores the 132 *aggregate* Magpie statistics (mean
        atomic number, mean electronegativity, ...).  Substituting one element
        for a chemically similar one barely moves those averages, so a wildly
        off-spec alloy can sit well inside the training cloud in feature space.

        Measured example: Ti-20Cu (20 wt% Cu against a 0.5 wt% training max)
        scored 0.98x the KNN threshold and returned a confident 903 MPa.  Cu
        and Ti are close enough in Z (29 vs 22), mass, and electronegativity
        that the aggregate statistics barely shift.  Ti-50Cu was needed before
        the KNN gate refused.  This check catches Ti-20Cu at 40x.

    Two rules:
        * element absent from training entirely -> infinite ratio, always OOD
          (there is no basis for any prediction on it);
        * element content > ``max_extrapolation`` x the training max -> OOD.

    The 8x default was chosen from measured separation over all 39 holdout and
    external-OOD alloys: the worst *legitimate* alloy is Ti-LCB at 2.25x (or
    Ti-2.5Cu at 5.0x, which the model predicts to within 35 MPa), while the
    dangerous Ti-20Cu case sits at 40x.

    Elements below ``trace_floor_at`` are ignored — impurity-level entries
    (0.01 at% C, say) produce meaningless ratios against a sparse training
    table and would cause false refusals.

    Returns ``(is_ood, worst_ratio, offending_element)``.
    """
    if not bounds:
        return (False, 0.0, None)

    worst_ratio = 0.0
    offender: str | None = None
    for el, at in (composition_at or {}).items():
        try:
            a = float(at)
        except (TypeError, ValueError):
            continue
        if a <= trace_floor_at:
            continue
        cap = bounds.get(el, 0.0)
        ratio = float("inf") if cap <= 0 else a / cap
        if ratio > worst_ratio:
            worst_ratio, offender = ratio, el

    return (worst_ratio > max_extrapolation, worst_ratio, offender)


def is_out_of_domain(ood: dict[str, Any], x: np.ndarray) -> tuple[bool, float, float]:
    """
    Check whether a single feature vector is out-of-domain.

    Returns (is_ood, distance, ratio).
        - is_ood:   True if mean K-NN distance > threshold
        - distance: the computed mean K-NN distance for this point
        - ratio:    distance / threshold (1.0 = exactly at threshold)
    """
    mean = np.asarray(ood["scaler_mean"])
    scale = np.asarray(ood["scaler_scale"])
    eps = 1e-6
    safe_scale = np.where(scale > eps, scale, 1.0)
    xs = np.where(scale > eps, (x - mean) / safe_scale, 0.0).reshape(1, -1)

    knn = ood["knn"]
    k = ood["k"]
    dists, _ = knn.kneighbors(xs, n_neighbors=k)
    mean_dist = float(dists[0].mean())

    threshold = ood["threshold"]
    return (mean_dist > threshold, mean_dist, mean_dist / threshold)
