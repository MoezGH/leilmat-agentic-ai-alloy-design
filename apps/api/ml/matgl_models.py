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


# Routing: list of (matching-rule, model-file, source-label). Multiple
# entries may match the same composition — they're tried in order and the
# first to return a non-null (in-domain) prediction wins. This lets us
# chain matbench_steels (ultra-high-strength only) → general_steel for
# mild/stainless steels that matbench_steels OOD-refuses.
_YS_FAMILIES = [
    {"element": "Fe", "threshold": 0.50, "model_file": "yield_strength_rf.pkl",
     "source": "rf_matbench_steels", "temper_family": None},
    {"element": "Fe", "threshold": 0.50, "model_file": "general_steel_ys_rf.pkl",
     "source": "rf_general_steel",   "temper_family": "general_steel"},
    {"element": "Al", "threshold": 0.80, "model_file": "aluminum_ys_rf.pkl",
     "source": "rf_aluminum",        "temper_family": "aluminum"},
    {"element": "Ti", "threshold": 0.50, "model_file": "titanium_ys_rf.pkl",
     "source": "rf_titanium",        "temper_family": "titanium"},
    {"element": "Ni", "threshold": 0.40, "model_file": "nickel_ys_rf.pkl",
     "source": "rf_nickel",          "temper_family": "nickel"},
]


def _predict_one_family(family: dict, composition: dict[str, float],
                        temper: str | None = None,
                        aging_T_C: float | None = None,
                        aging_time_s: float | None = None) -> dict[str, Any]:
    """Run a single family's predictor on the composition + optional temper.

    Returns either a dict with `value` populated (in-domain hit) or a dict
    with `value: None` plus a source ending in `_out_of_domain` (OOD refusal)
    or a generic error. The caller is expected to iterate over matching
    families until either a hit is found or all OOD-refuse.

    Sprint 4: if the bundle is temper-aware, the temper is normalised via
    ``apps.api.ml.temper.encoding`` and appended to the feature vector.
    When the bundle is old-style (composition-only) we pass through with
    no temper feature, preserving backward compatibility.
    """
    bundle = _ys_model(family["model_file"])
    if bundle is None:
        return {"value": None, "source": family["source"], "error": "model file missing — run training first"}

    try:
        feats = magpie_features(composition)
        ep_labels = [k for k in feats.keys() if k.startswith("MagpieData")]
        x_comp = np.array([feats[k] for k in ep_labels]).reshape(1, -1)
        x = x_comp                       # default: composition only
        applied_temper: str | None = None

        # ── Sprint 4: append temper features if the model is temper-aware ─
        if bundle.get("temper_aware") and family.get("temper_family"):
            from apps.api.ml.temper.encoding import (
                encode_temper, canonicalise_temper,
            )
            fam = family["temper_family"]
            applied_temper = canonicalise_temper(fam, temper)
            t_feats = encode_temper(fam, temper).reshape(1, -1)
            x = np.concatenate([x_comp, t_feats], axis=1)

            # ── Sprint 6: physics features (must match training order) ──
            if bundle.get("physics_aware"):
                from apps.api.ml.alloy_datasets import atomic_to_weight
                from apps.api.ml.strengthening import physics_features
                # physics_features expects WEIGHT % — it does its own wt->at
                # conversion internally for the Labusch term, and training
                # feeds it `entry["composition_wt"]` directly.  This API
                # speaks atomic %, so convert.  Passing atomic % straight
                # through double-converts and skewed the solid-solution
                # feature by up to +29% (Ti-6Al-4V) relative to training —
                # a genuine train/inference mismatch, not a rounding detail.
                comp_wt = atomic_to_weight(composition)
                # Task #9: when the caller supplies an aging schedule the
                # precipitate radius is derived from it; otherwise fall back to
                # the median radius this model actually trained on for this
                # temper (stored in the bundle), which keeps the no-schedule
                # path inside the training distribution.
                from apps.api.ml.temper.encoding import canonicalise_temper as _canon
                med = (bundle.get("median_radius_nm_by_temper") or {}).get(
                    _canon(fam, temper)
                )
                phys = physics_features(
                    comp_wt, fam, temper,
                    aging_T_C, aging_time_s,
                    fallback_radius_nm=med,
                ).reshape(1, -1)
                x = np.concatenate([x, phys], axis=1)

        # ── Out-of-domain check — uses composition features ONLY ─────────
        # The OOD detector was fit on composition features only, so we
        # always evaluate it against x_comp (not x).  A novel composition
        # is flagged regardless of the user-supplied temper.
        # Composition-space guard, checked first: the KNN below scores aggregate
        # Magpie statistics, which barely shift when one element is swapped for a
        # chemically similar one.  Measured: Ti-20Cu (40x the 0.5 wt% training max)
        # scored 0.98x the KNN threshold and returned a confident 903 MPa.
        # Bundles trained before this existed have no "element_bounds" key and
        # simply skip the check.
        bounds = bundle.get("element_bounds")
        if bounds:
            from apps.api.ml.ood import check_element_bounds
            el_ood, el_ratio, offender = check_element_bounds(bounds, composition)
            if el_ood:
                cap = bounds.get(offender or "", 0.0)
                absent = cap <= 0
                return {
                    "value": None,
                    "source": f"{family['source']}_out_of_domain",
                    "ood_reason": "element_absent" if absent else "element_extrapolation",
                    "ood_element": offender,
                    "ood_element_ratio": None if absent else round(el_ratio, 1),
                    "domain": bundle.get("domain", ""),
                    "error": (
                        f"Composition is outside the training domain of this model: "
                        + (
                            f"{offender} does not appear in any training alloy for this family."
                            if absent else
                            f"{offender} is {el_ratio:.0f}x the maximum seen in training "
                            f"({cap:.2f} at%)."
                        )
                        + f" Trained on: {bundle.get('domain', family['source'])}."
                    ),
                }

        ood = bundle.get("ood")
        if ood is not None:
            from apps.api.ml.ood import is_out_of_domain
            is_ood, dist, ratio = is_out_of_domain(ood, x_comp[0])
            if is_ood:
                # A large share of these refusals are not exotic chemistry but
                # an under-specified composition: Magpie min/max/range stats are
                # computed over the elements PRESENT with no concentration
                # weighting, so omitting a 0.05 wt% carbon moves `minimum
                # AtomicWeight` from 52 to 12 and throws the vector out of the
                # training cloud.  Refusing is correct — measured on AISI 316,
                # dropping C and Si moves general_steel's own output from 218 MPa
                # (lit ~215) to 831 MPa.  But the user can only act on the reason,
                # so name the missing elements instead of quoting a distance.
                from apps.api.ml.ood import find_missing_ubiquitous
                missing = find_missing_ubiquitous(
                    bundle.get("ubiquitous_elements") or {}, composition
                )
                detail = (
                    f"(KNN distance {dist:.2f} vs threshold {ood['threshold']:.2f}, "
                    f"{ratio:.1f}× threshold)."
                )
                hint = ""
                if missing:
                    listed = ", ".join(
                        f"{el} (~{typ:g} wt% typical)"
                        for el, typ in sorted(missing.items(), key=lambda kv: -kv[1])
                    )
                    hint = (
                        f" This composition omits {listed} — element(s) present in"
                        f" almost every {family['source'].replace('rf_', '')} alloy"
                        f" used to train this model. Trace elements shift the"
                        f" descriptors sharply and materially change the answer,"
                        f" so add them and retry rather than treating this as an"
                        f" unsupported alloy."
                    )
                return {
                    "value": None,
                    "source": f"{family['source']}_out_of_domain",
                    "ood_reason": "missing_expected_elements" if missing else "knn_distance",
                    "ood_distance": round(dist, 3),
                    "ood_threshold": round(ood["threshold"], 3),
                    "ood_ratio": round(ratio, 2),
                    "missing_elements": {el: typ for el, typ in missing.items()} or None,
                    "domain": bundle.get("domain", ""),
                    "error": (
                        f"Composition is outside the training domain of this model "
                        f"{detail}{hint} "
                        f"Trained on: {bundle.get('domain', family['source'])}."
                    ),
                }

        rf = bundle["model"]
        tree_preds = np.array([t.predict(x)[0] for t in rf.estimators_])
        mean = float(tree_preds.mean())
        std = float(tree_preds.std())

        # ── Conformal interval ────────────────────────────────────────────
        cal_dict = bundle.get("conformal")
        if cal_dict is not None:
            from apps.api.ml.calibration import SplitConformalPredictor
            calibrator = SplitConformalPredictor.from_dict(cal_dict)
            sigma_for_interval = std if calibrator.heteroscedastic else None
            ci_low, ci_high, half = calibrator.interval(mean, sigma=sigma_for_interval)
            interval = {
                "ci_low":            round(ci_low, 0),
                "ci_high":           round(ci_high, 0),
                "uncertainty":       round(half, 0),
                "coverage":          round(1 - calibrator.alpha, 2),
                "calibration":       "conformal",
                "n_calibration":     calibrator.n_calibration,
            }
        else:
            mae_floor = bundle.get("cv_mae_MPa", 50.0)
            total_unc = max(std, mae_floor * 0.7)
            interval = {
                "ci_low":      round(mean - total_unc, 0),
                "ci_high":     round(mean + total_unc, 0),
                "uncertainty": round(total_unc, 0),
                "coverage":    None,
                "calibration": "tree_std_heuristic",
            }

        out: dict[str, Any] = {
            "value": round(mean, 0),
            **interval,
            "source": family["source"],
            "n_training": bundle.get("n_samples"),
            "cv_mae_MPa": round(bundle.get("cv_mae_MPa", 0), 0),
        }
        # Sprint 4: surface which temper the model actually used so the UI
        # can show "predicted at temper X" rather than guessing.
        if applied_temper is not None:
            out["temper_used"] = applied_temper
        if ood is not None:
            from apps.api.ml.ood import is_out_of_domain
            _, dist, ratio = is_out_of_domain(ood, x_comp[0])
            out["ood_ratio"] = round(ratio, 2)
        return out
    except Exception as exc:
        return {"value": None, "source": family["source"], "error": str(exc)}


def yield_strength_MPa(composition: dict[str, float],
                       temper: str | None = None,
                       grain_size_um: float | None = None,
                       precipitate_state: dict | None = None,
                       aging_T_C: float | None = None,
                       aging_time_s: float | None = None) -> dict[str, Any]:
    """
    Yield-strength prediction with fall-through family routing.

    Routing matches each family whose threshold rule fits the composition,
    then tries them in priority order. The first non-OOD prediction wins.
    For Fe-rich compositions this means matbench_steels (ultra-high-strength)
    is tried first; if its OOD gate refuses (mild/structural/stainless steel),
    we fall through to the general_steel model which covers 100-1900 MPa.

    Families:
      Fe ≥ 50%  → matbench_steels (n=312, 1000-2500 MPa, ultra-high-strength)
                  → general_steel  (n≈36, mild/low-alloy/stainless/PH, 170-1900 MPa)
      Al ≥ 80%  → curated Al set   (n=29, 105-700 MPa)
      Ti ≥ 50%  → curated Ti set   (n=20, 170-1380 MPa)
      Ni ≥ 40%  → curated Ni set   (n=23, 240-1100 MPa)

    Outside these families, returns null with a clear `rf_no_match` source.
    """
    total = sum(composition.values())
    if total <= 0:
        return {"value": None, "source": "rf_no_match", "error": "empty composition"}
    fracs = {el: v / total for el, v in composition.items()}

    # Collect all families whose composition rule matches, in priority order.
    matching = [f for f in _YS_FAMILIES if fracs.get(f["element"], 0) >= f["threshold"]]
    if not matching:
        majority = max(fracs, key=fracs.get)
        return {
            "value": None,
            "source": "rf_no_match",
            "error": f"No model for {majority}-base alloys. Trained families: Fe-, Al-, Ti-, Ni-based.",
        }

    # Try each matching family until one returns an in-domain prediction.
    # If all OOD-refuse, return the LAST attempted family's response (the
    # broader model, which still includes its OOD diagnostics so the user
    # sees the most useful error).
    last_response = None
    families_tried: list[str] = []
    for f in matching:
        result = _predict_one_family(f, composition, temper=temper,
                                     aging_T_C=aging_T_C,
                                     aging_time_s=aging_time_s)
        families_tried.append(f["source"])
        last_response = result
        if result.get("value") is not None:
            # In-domain hit. Note which families were tried so the UI can
            # surface "primary OOD → secondary hit" reasoning when relevant.
            if len(families_tried) > 1:
                result["families_tried"] = families_tried
            # Optional physics overlays from upstream sims, each a differential
            # adjustment to the value + CI with an honest literature-correlation
            # tag: Hall-Petch (grain size, when domain_um was set) and Orowan
            # (KWN-simulated precipitate state vs the canonical temper baseline).
            _apply_hall_petch(result, f["element"], grain_size_um)
            _apply_precipitation(result, f["element"], temper, precipitate_state)
            return result
    # All matching families OOD-refused. Annotate so the response is honest.
    if last_response is not None:
        last_response["families_tried"] = families_tried
    return last_response or {"value": None, "source": "rf_no_match"}


def _apply_hall_petch(result: dict[str, Any], family_element: str,
                      grain_size_um: float | None) -> None:
    """In-place: shift a YS prediction by the differential Hall-Petch term."""
    if grain_size_um is None or result.get("value") is None:
        return
    from apps.api.ml.hall_petch import hall_petch_delta_MPa
    hp = hall_petch_delta_MPa(family_element, grain_size_um)
    if hp is None:
        return
    delta = hp["delta_MPa"]
    result["value"] = round(result["value"] + delta, 1)
    for k in ("ci_low", "ci_high"):
        if result.get(k) is not None:
            result[k] = round(result[k] + delta, 1)
    result["hall_petch"] = hp


def _apply_precipitation(result: dict[str, Any], family_element: str,
                         temper: str | None, precipitate_state: dict | None) -> None:
    """In-place: shift a YS prediction by the differential Orowan term derived
    from a KWN-simulated precipitate state (vf, r̄)."""
    if not precipitate_state or result.get("value") is None:
        return
    from apps.api.ml.strengthening import orowan_delta_MPa
    pp = orowan_delta_MPa(
        family_element, temper,
        precipitate_state.get("vf"), precipitate_state.get("r_nm"),
    )
    if pp is None:
        return
    delta = pp["delta_MPa"]
    result["value"] = round(result["value"] + delta, 1)
    for k in ("ci_low", "ci_high"):
        if result.get(k) is not None:
            result[k] = round(result[k] + delta, 1)
    result["precipitation"] = pp


# ─────────────────────────────────────────────────────────────────────────
# Master predictor — what the API calls
# ─────────────────────────────────────────────────────────────────────────

def predict_properties(composition: dict[str, float],
                       temper: str | None = None,
                       grain_size_um: float | None = None,
                       precipitate_state: dict | None = None) -> dict[str, Any]:
    """
    Returns a dict of property predictions for the given composition.

    Each property is itself a dict {value, uncertainty?, source, error?}.
    The UI can render the value, uncertainty band, and source provenance.

    Backward-compatible flat shape is also included for legacy clients —
    each property's `value` is also exposed at the top level.

    Sprint 4: ``temper`` is passed through to the YS predictor.  When None,
    the YS model falls back to its family-default temper (and reports
    which temper it used via ``yield_strength_MPa._details.temper_used``).
    """
    if not composition or sum(composition.values()) <= 0:
        return {"error": "empty composition", "composition": composition}

    # Upstream sims shift YS via differential overlays — grain size
    # (Hall-Petch) and KWN precipitate state (Orowan).  Hardness + fatigue
    # derive from this adjusted YS below, so the effects propagate downstream.
    ys_detail = yield_strength_MPa(composition, temper=temper,
                                   grain_size_um=grain_size_um,
                                   precipitate_state=precipitate_state)
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
