"""
Real property prediction with provenance.

Each property returns {value, uncertainty, source} so the UI can render
confidence and trust the user appropriately.

Sources used:
- rule_of_mixtures: closed-form mass-weighted density formula (Phase 1.1)
- magpie_mean: composition-weighted elemental property from Magpie descriptors
- miedema_heuristic: empirical formation energy (Phase 1.1 placeholder)
- rf_matbench_steels: Random Forest trained on 312 steel alloys (CV MAE ~110 MPa)
"""
from __future__ import annotations

import functools
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from apps.api.ml.featurizers import (
    density_rule_of_mixtures,
    melting_point_K,
    electronegativity_mean,
    valence_electrons_mean,
    formation_energy_eV_per_atom,
    elastic_modulus_VRH,
    magpie_features,
)
from apps.api.ml.manufacturability import manufacturability
from apps.api.ml.secondary_properties import (
    hardness_HV,
    fatigue_endurance_MPa,
    corrosion_resistance,
    phase_stability_warnings,
)

MODELS_DIR = Path(__file__).parent.parent.parent.parent / "models"


# ─────────────────────────────────────────────────────────────────────────
# Lazy-loaded trained models (one per alloy family)
# ─────────────────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=8)
def _ys_model(filename: str) -> dict[str, Any] | None:
    path = MODELS_DIR / filename
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


# Routing thresholds and source labels per family
_YS_FAMILIES = [
    {"element": "Fe", "threshold": 0.50, "model_file": "yield_strength_rf.pkl",   "source": "rf_matbench_steels"},
    {"element": "Al", "threshold": 0.80, "model_file": "aluminum_ys_rf.pkl",     "source": "rf_aluminum"},
    {"element": "Ti", "threshold": 0.50, "model_file": "titanium_ys_rf.pkl",     "source": "rf_titanium"},
    {"element": "Ni", "threshold": 0.40, "model_file": "nickel_ys_rf.pkl",       "source": "rf_nickel"},
]


def yield_strength_MPa(composition: dict[str, float]) -> dict[str, Any]:
    """
    Yield-strength prediction routed by majority element to a family-specific Random Forest.

    Routing rules (atomic-fraction thresholds):
      Fe ≥ 50%  → matbench_steels  (312 alloys, CV MAE ~110 MPa over 400-2500 MPa)
      Al ≥ 80%  → curated Al set    ( 29 alloys, CV MAE ~58  MPa over 105-700  MPa)
      Ti ≥ 50%  → curated Ti set    ( 20 alloys, CV MAE ~125 MPa over 170-1380 MPa)
      Ni ≥ 40%  → curated Ni set    ( 23 alloys, CV MAE ~151 MPa over 240-1100 MPa)

    Outside these families, returns None with explanation. Predictions show
    "(extrapolating)" + extra uncertainty when constituents fall outside the
    family's seen alloying space.
    """
    total = sum(composition.values())
    if total <= 0:
        return {"value": None, "source": "rf_no_match", "error": "empty composition"}
    fracs = {el: v / total for el, v in composition.items()}

    # Find the matching family (first one whose threshold is met)
    family = None
    for f in _YS_FAMILIES:
        if fracs.get(f["element"], 0) >= f["threshold"]:
            family = f
            break

    if family is None:
        majority = max(fracs, key=fracs.get)
        return {
            "value": None,
            "source": "rf_no_match",
            "error": f"No model for {majority}-base alloys. Trained families: Fe-, Al-, Ti-, Ni-based.",
        }

    bundle = _ys_model(family["model_file"])
    if bundle is None:
        return {"value": None, "source": family["source"], "error": "model file missing — run training first"}

    try:
        feats = magpie_features(composition)
        ep_labels = [k for k in feats.keys() if k.startswith("MagpieData")]
        x = np.array([feats[k] for k in ep_labels]).reshape(1, -1)

        # ── Out-of-domain check ──────────────────────────────────────────
        ood = bundle.get("ood")
        if ood is not None:
            from apps.api.ml.ood import is_out_of_domain
            is_ood, dist, ratio = is_out_of_domain(ood, x[0])
            if is_ood:
                return {
                    "value": None,
                    "source": f"{family['source']}_out_of_domain",
                    "ood_distance": round(dist, 3),
                    "ood_threshold": round(ood["threshold"], 3),
                    "ood_ratio": round(ratio, 2),
                    "domain": bundle.get("domain", ""),
                    "error": (
                        f"Composition is outside the training domain of this model "
                        f"(KNN distance {dist:.2f} vs threshold {ood['threshold']:.2f}, "
                        f"{ratio:.1f}× threshold). "
                        f"Trained on: {bundle.get('domain', family['source'])}."
                    ),
                }

        rf = bundle["model"]
        tree_preds = np.array([t.predict(x)[0] for t in rf.estimators_])
        mean = float(tree_preds.mean())
        std = float(tree_preds.std())

        # Add a model-MAE floor so total uncertainty isn't optimistic
        mae_floor = bundle.get("cv_mae_MPa", 50.0)
        total_unc = max(std, mae_floor * 0.7)

        out: dict[str, Any] = {
            "value": round(mean, 0),
            "uncertainty": round(total_unc, 0),
            "source": family["source"],
            "n_training": bundle.get("n_samples"),
            "cv_mae_MPa": round(bundle.get("cv_mae_MPa", 0), 0),
        }
        # Expose how close the input is to the training distribution, even when in-domain.
        if ood is not None:
            from apps.api.ml.ood import is_out_of_domain
            _, dist, ratio = is_out_of_domain(ood, x[0])
            out["ood_ratio"] = round(ratio, 2)
        return out
    except Exception as exc:
        return {"value": None, "source": family["source"], "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────
# Master predictor — what the API calls
# ─────────────────────────────────────────────────────────────────────────

def predict_properties(composition: dict[str, float]) -> dict[str, Any]:
    """
    Returns a dict of property predictions for the given composition.

    Each property is itself a dict {value, uncertainty?, source, error?}.
    The UI can render the value, uncertainty band, and source provenance.

    Backward-compatible flat shape is also included for legacy clients —
    each property's `value` is also exposed at the top level.
    """
    if not composition or sum(composition.values()) <= 0:
        return {"error": "empty composition", "composition": composition}

    ys_detail = yield_strength_MPa(composition)
    ys_value = ys_detail.get("value")

    detailed = {
        "density_g_cm3":                density_rule_of_mixtures(composition),
        "melting_point_K":              melting_point_K(composition),
        "electronegativity_mean":       electronegativity_mean(composition),
        "valence_electrons_mean":       valence_electrons_mean(composition),
        "formation_energy_eV_per_atom": formation_energy_eV_per_atom(composition),
        "yield_strength_MPa":           ys_detail,
        "hardness_HV":                  hardness_HV(composition, ys_value),
        "fatigue_endurance_MPa":        fatigue_endurance_MPa(composition, ys_value),
        "corrosion_resistance":         corrosion_resistance(composition),
        "elastic_modulus_GPa":          elastic_modulus_VRH(composition),
    }

    manuf  = manufacturability(composition)
    stab   = phase_stability_warnings(composition)

    # Backward-compatible flat fields (just the `value` from each)
    flat = {k: v.get("value") for k, v in detailed.items()}
    flat["corrosion_rating"]        = detailed["corrosion_resistance"].get("rating")
    flat["castability_score"]       = manuf["castability"].get("value")
    flat["weldability_score"]       = manuf["weldability"].get("value")
    flat["cost_score"]              = manuf["cost"].get("value")
    flat["manufacturability_score"] = manuf["overall"]

    return {
        **flat,
        "_details":        detailed,
        "manufacturability": manuf,
        "phase_stability": stab,
        "composition":     composition,
    }
