"""
Split-conformal prediction for calibrated uncertainty intervals.

References:
    Vovk, Gammerman, Shafer (2005). "Algorithmic Learning in a Random World"
    Lei & Wasserman (2014). "Distribution-free prediction sets" (locally-
    weighted variant)
    Romano, Patterson, Candès (2019). "Conformalized quantile regression"

Why conformal:
    Random Forests' tree-variance gives a *heuristic* uncertainty; it has
    no coverage guarantee. Conformal prediction wraps any point predictor
    in a procedure that produces intervals with a *provable* marginal
    coverage of (1−α) on exchangeable data — regardless of model quality
    or distribution.

What this class does:
    Given residuals `r_i = |y_i − ŷ_i|` on a calibration set (and optionally
    per-point heteroscedastic estimates σ̂_i, e.g. tree-variance), we store
    the (1−α)-quantile of the *normalised* residuals as `q`. At prediction
    time, the interval is `[ŷ − q·σ̂(x), ŷ + q·σ̂(x)]`.

    For α = 0.10 the interval contains the true value with marginal
    probability ≥ 0.90 on new exchangeable inputs.

What this class does NOT do:
    - Conditional coverage (intervals may be over/under-cover in *local*
      regions of feature space; only marginal coverage is guaranteed).
    - Distribution shift adjustment (assumes calibration data is exchangeable
      with future predictions).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class SplitConformalPredictor:
    """
    Split-conformal interval estimator.

    Use `.fit(residuals, sigmas=None)` once on calibration residuals, then
    `.interval(y_pred, sigma=None)` to wrap any new point prediction.

    Attributes:
        alpha:                Target miscoverage rate (0.10 for 90% bands).
        q:                    The fitted (1−α)-quantile of normalised residuals.
        heteroscedastic:      True when sigmas were supplied during fit.
        n_calibration:        Number of calibration points used.
        empirical_coverage:   Self-reported coverage on calibration set (sanity
                              check — should be ≈ 1−α; bigger gap = small n).
    """

    alpha: float = 0.10
    q: float = 0.0
    heteroscedastic: bool = False
    n_calibration: int = 0
    empirical_coverage: float = 0.0
    # Diagnostics from fit
    median_residual: float = 0.0
    mean_residual: float = 0.0
    max_residual: float = 0.0
    eps_sigma: float = 1e-6   # floor for the heteroscedastic estimate

    def fit(self, residuals: np.ndarray, sigmas: np.ndarray | None = None) -> "SplitConformalPredictor":
        """
        Fit the conformal quantile from calibration residuals.

        Args:
            residuals: array of |y_i − ŷ_i| from the calibration set.
            sigmas:    optional per-point heteroscedastic estimates (e.g.
                       RF tree-std). When supplied, the nonconformity score
                       is `|y − ŷ| / max(σ̂, eps)` and the returned interval
                       widens in proportion to σ̂(x) — giving tight bands
                       in low-variance regions and wide bands in high-
                       variance regions.
        """
        r = np.asarray(residuals, dtype=float)
        if r.size < 4:
            # Not enough data for a meaningful quantile.
            raise ValueError(f"need ≥4 calibration residuals, got {r.size}")

        if sigmas is not None:
            s = np.asarray(sigmas, dtype=float)
            if s.shape != r.shape:
                raise ValueError(f"shape mismatch: residuals {r.shape} vs sigmas {s.shape}")
            scores = r / np.maximum(s, self.eps_sigma)
            self.heteroscedastic = True
        else:
            scores = r
            self.heteroscedastic = False

        n = len(scores)
        # Standard split-conformal quantile level.
        # Capped at 1.0 in case (n+1)(1-α)/n > 1 for very small n.
        q_level = min(1.0, np.ceil((n + 1) * (1 - self.alpha)) / n)
        self.q = float(np.quantile(scores, q_level))
        self.n_calibration = n

        # Diagnostics: what fraction of calibration residuals would fall
        # inside the conformal interval? Should be ≈ 1−α.
        if self.heteroscedastic:
            widths = self.q * np.maximum(sigmas, self.eps_sigma)
        else:
            widths = np.full_like(r, self.q)
        in_interval = (r <= widths).sum()
        self.empirical_coverage = float(in_interval / n)

        self.median_residual = float(np.median(r))
        self.mean_residual = float(np.mean(r))
        self.max_residual = float(np.max(r))
        return self

    def interval(self, y_pred: float, sigma: float | None = None) -> tuple[float, float, float]:
        """
        Return (y_low, y_high, half_width) for a new point prediction.

        If the calibrator was fit with sigmas, you must pass sigma here; if
        it was fit without, sigma is ignored.
        """
        if self.heteroscedastic:
            if sigma is None:
                raise ValueError("calibrator was fit heteroscedastic; sigma required")
            half = self.q * max(float(sigma), self.eps_sigma)
        else:
            half = self.q
        return (float(y_pred) - half, float(y_pred) + half, half)

    def to_dict(self) -> dict[str, Any]:
        """Serialise for pickling alongside the model bundle."""
        return {
            "alpha": self.alpha,
            "q": self.q,
            "heteroscedastic": self.heteroscedastic,
            "n_calibration": self.n_calibration,
            "empirical_coverage": self.empirical_coverage,
            "median_residual": self.median_residual,
            "mean_residual": self.mean_residual,
            "max_residual": self.max_residual,
            "eps_sigma": self.eps_sigma,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SplitConformalPredictor":
        return cls(**d)


# ─────────────────────────────────────────────────────────────────────────
# Helper to fit a calibrator from leave-one-out residuals on an RF.
# ─────────────────────────────────────────────────────────────────────────

def fit_loo_conformal(
    X: np.ndarray,
    y: np.ndarray,
    rf_params: dict[str, Any],
    alpha: float = 0.10,
    heteroscedastic: bool = True,
) -> SplitConformalPredictor:
    """
    Build conformal residuals by leave-one-out cross-validation.

    For each training point, fit the model on the remaining n-1, predict
    that one, and record |y_i − ŷ_i| (and optionally the tree-variance σ̂_i).
    Then fit a conformal calibrator on the LOO scores.

    This is the recommended approach for the small (n ≈ 20-30) non-ferrous
    YS datasets — a held-out calibration split would be too noisy.

    Args:
        X, y: training data
        rf_params: kwargs for sklearn RandomForestRegressor
        alpha: target miscoverage (0.10 → 90% intervals)
        heteroscedastic: when True, the calibrator normalises by tree-variance
                         (tighter bands in confident regions). When False, the
                         interval is a constant ±q.

    Returns:
        Fitted SplitConformalPredictor.
    """
    from sklearn.ensemble import RandomForestRegressor

    n = len(y)
    residuals = np.zeros(n)
    sigmas = np.zeros(n)

    for i in range(n):
        mask = np.arange(n) != i
        rf = RandomForestRegressor(**rf_params)
        rf.fit(X[mask], y[mask])
        tree_preds = np.array([t.predict(X[i:i + 1])[0] for t in rf.estimators_])
        y_pred = float(tree_preds.mean())
        sigma  = float(tree_preds.std())
        residuals[i] = abs(y[i] - y_pred)
        sigmas[i]    = sigma

    cal = SplitConformalPredictor(alpha=alpha)
    cal.fit(residuals, sigmas=sigmas if heteroscedastic else None)
    return cal


def fit_simple_conformal(
    residuals: np.ndarray,
    sigmas: np.ndarray | None = None,
    alpha: float = 0.10,
) -> SplitConformalPredictor:
    """Convenience: fit conformal directly from precomputed residuals
    (e.g. canonical-phase residuals for M3GNet)."""
    cal = SplitConformalPredictor(alpha=alpha)
    cal.fit(residuals, sigmas=sigmas)
    return cal
