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
