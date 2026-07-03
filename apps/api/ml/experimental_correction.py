"""
Experimental bias correction for M3GNet formation energies.

M3GNet reproduces MP-PBE DFT values, and DFT systematically overbinds
transition-metal intermetallics — Appendix E of the scorecard measured a
232 meV/atom MAE between raw M3GNet output and experimental calorimetry
(NIST WebBook / Kubaschewski / CALPHAD, 25 reference phases).

This module provides a linear correction fitted on those 25 pairs:

    dHf_experimental ≈ slope * dHf_m3gnet + intercept

Honesty guards:
    * Accuracy is reported as leave-one-out CV MAE, not the in-sample fit.
    * The correction is only applied to multi-element compositions predicted
      by the real M3GNet path (``source == "m3gnet_dft"``) — pure elements
      have dHf ≡ 0 by definition and the Miedema fallback has different error
      structure, so both are left uncorrected.
    * The corrected value is exposed as a *separate* ``experimental_estimate``
      field; the primary ``value`` stays on the DFT scale that the rest of the
      stack (canonical-phase tests, conformal calibrator, MP benchmarks) is
      validated against.

Refit after changing CALORI_REFERENCES or upgrading the M3GNet weights:

    docker exec leilmat-api-1 python -m apps.api.ml.experimental_correction --fit

and paste the printed block over ``CORRECTION`` below.
"""
from __future__ import annotations

from typing import Any

# ─────────────────────────────────────────────────────────────────────────
# Frozen coefficients — output of `--fit` on the production box.
# Regenerate with the command in the module docstring; do not hand-edit.
# ─────────────────────────────────────────────────────────────────────────

CORRECTION: dict[str, Any] = {
    "slope": 0.2595,
    "intercept": -0.0427,
    "loo_mae_eV": 0.0543,   # leave-one-out CV MAE (raw M3GNet-vs-experiment: 0.2321)
    "loo_q90_eV": 0.1143,   # 90th percentile of |LOO residual| — interval half-width
    "n_fit": 25,
    "fitted_on": "calorimetry_benchmark.CALORI_REFERENCES",
    "fitted_at": "2026-07-03",
    "m3gnet_weights": "M3GNet-Eform-MP-2018.6.1",
}


def correct_to_experimental(m3gnet_eV_per_atom: float) -> float | None:
    """Map a raw M3GNet (DFT-scale) formation energy to the experimental scale."""
    a, b = CORRECTION.get("slope"), CORRECTION.get("intercept")
    if a is None or b is None:
        return None
    return a * m3gnet_eV_per_atom + b


def experimental_estimate(prediction: dict[str, Any],
                          composition: dict[str, float]) -> dict[str, Any] | None:
    """
    Build the ``experimental_estimate`` sub-field for a featurizer prediction.

    Returns None (field omitted) when the correction does not apply:
    coefficients not fitted, prediction missing, non-M3GNet source, or a
    pure-element composition (dHf ≡ 0 by definition — no correction needed).
    """
    value = prediction.get("value")
    if value is None or prediction.get("source") != "m3gnet_dft":
        return None
    n_elements = sum(1 for v in composition.values() if v > 0)
    if n_elements < 2:
        return None
    corrected = correct_to_experimental(float(value))
    if corrected is None:
        return None
    return {
        "value": round(corrected, 4),
        "uncertainty": CORRECTION["loo_q90_eV"],
        "basis": (
            f"linear correction to calorimetry, LOO-CV MAE "
            f"{CORRECTION['loo_mae_eV'] * 1000:.0f} meV/atom "
            f"(n={CORRECTION['n_fit']}, fitted {CORRECTION['fitted_at']})"
        ),
    }


# ─────────────────────────────────────────────────────────────────────────
# Offline fitting — run on a machine with matgl (the production box).
# ─────────────────────────────────────────────────────────────────────────

def fit_experimental_correction() -> dict[str, Any]:
    """
    Predict every calorimetry reference with the production M3GNet path,
    fit the linear correction, and report leave-one-out CV statistics.
    """
    import numpy as np

    from apps.api.ml.eval.calorimetry_benchmark import CALORI_REFERENCES
    from apps.api.ml.featurizers import formation_energy_eV_per_atom

    pairs: list[tuple[str, float, float]] = []   # (name, m3gnet, experiment)
    skipped: list[str] = []
    for ref in CALORI_REFERENCES:
        pred = formation_energy_eV_per_atom(ref["composition"])
        if pred.get("value") is None or pred.get("source") != "m3gnet_dft":
            skipped.append(f"{ref['name']} ({pred.get('source')})")
            continue
        pairs.append((ref["name"], float(pred["value"]), float(ref["ref_eV_per_atom"])))

    if len(pairs) < 10:
        return {"error": f"only {len(pairs)} M3GNet predictions — need the real "
                         f"model, not a fallback", "skipped": skipped}

    x = np.array([p[1] for p in pairs])
    y = np.array([p[2] for p in pairs])

    # Full-sample OLS → the frozen production coefficients.
    A = np.vstack([x, np.ones_like(x)]).T
    (slope, intercept), *_ = np.linalg.lstsq(A, y, rcond=None)

    # Leave-one-out CV → the honest accuracy number.
    loo_residuals = []
    for i in range(len(x)):
        mask = np.arange(len(x)) != i
        Ai = np.vstack([x[mask], np.ones(mask.sum())]).T
        (a_i, b_i), *_ = np.linalg.lstsq(Ai, y[mask], rcond=None)
        loo_residuals.append(abs((a_i * x[i] + b_i) - y[i]))
    loo = np.array(loo_residuals)

    raw_mae = float(np.mean(np.abs(x - y)))
    return {
        "slope": round(float(slope), 4),
        "intercept": round(float(intercept), 4),
        "raw_mae_eV": round(raw_mae, 4),
        "loo_mae_eV": round(float(loo.mean()), 4),
        "loo_median_eV": round(float(np.median(loo)), 4),
        "loo_q90_eV": round(float(np.quantile(loo, 0.90)), 4),
        "loo_max_eV": round(float(loo.max()), 4),
        "n_fit": len(pairs),
        "skipped": skipped,
        "pairs": [{"name": n, "m3gnet": round(m, 4), "experiment": e}
                  for n, m, e in pairs],
    }


if __name__ == "__main__":
    import json
    import sys

    if "--fit" in sys.argv:
        print(json.dumps(fit_experimental_correction(), indent=2))
    else:
        print(json.dumps(CORRECTION, indent=2))
