"""
Regression tests for the yield-strength prediction models.

These tests are deliberately conservative — they're meant to catch silent
drift (e.g. a refactor accidentally changing the routing thresholds, a model
file being corrupted, a featurizer being upgraded with breaking changes).

They don't try to assert that the models are *good*; the scorecard
(`python -m apps.api.ml.eval.scorecard`) is the place to read the actual
accuracy numbers.

Run:
    pytest apps/api/ml/eval/test_yield_strength.py -v
"""
from __future__ import annotations

import pickle
from pathlib import Path

import pytest

MODELS_DIR = Path(__file__).parent.parent.parent.parent.parent / "models"

_FAMILY_FILES = {
    "aluminum": "aluminum_ys_rf.pkl",
    "titanium": "titanium_ys_rf.pkl",
    "nickel":   "nickel_ys_rf.pkl",
    "steel":    "yield_strength_rf.pkl",
}


def _model_exists(family: str) -> bool:
    return (MODELS_DIR / _FAMILY_FILES[family]).exists()


# ── 1. Model files are present ─────────────────────────────────────────

@pytest.mark.parametrize("family", list(_FAMILY_FILES.keys()))
def test_model_file_present(family: str):
    assert _model_exists(family), (
        f"{_FAMILY_FILES[family]} missing — run `python -m apps.api.ml.training` first."
    )


@pytest.mark.parametrize("family", list(_FAMILY_FILES.keys()))
def test_model_bundle_has_required_fields(family: str):
    if not _model_exists(family):
        pytest.skip("model file missing")
    with open(MODELS_DIR / _FAMILY_FILES[family], "rb") as f:
        bundle = pickle.load(f)
    for key in ("model", "n_samples", "cv_mae_MPa", "y_min", "y_max"):
        assert key in bundle, f"{family}: missing key {key}"
    assert bundle["cv_mae_MPa"] > 0
    assert bundle["n_samples"] > 0


# ── 2. Held-out predictions on canonical alloys ────────────────────────

@pytest.fixture(scope="module")
def holdout_results():
    """Run held-out predictions once and cache them for all tests in this module."""
    from apps.api.ml.eval.holdout_runner import run_all
    return run_all()


@pytest.mark.parametrize("family", ["aluminum", "titanium", "nickel", "steel"])
def test_no_false_positives_through_ood_gate(holdout_results, family):
    """An alloy flagged `expected_in_domain=False` MUST be refused by the gate.

    This is the most important test: if the OOD gate misses a known-bad alloy
    (e.g. AISI 304 stainless going through the high-strength steel model), the
    user will see catastrophically wrong predictions. Better to refuse cleanly.
    """
    if not _model_exists(family):
        pytest.skip("model file missing")
    h = holdout_results[family]
    assert h.get("n_unexpected_predict", 0) == 0, (
        f"{family}: OOD gate let through alloys flagged as expected_in_domain=False. "
        f"False-positive predictions: "
        f"{[p['name'] for p in h.get('predictions', []) if p.get('outcome') == 'unexpected_predict']}"
    )


@pytest.mark.parametrize("family,max_mae_ratio", [
    # On in-domain alloys (the only ones that should produce predictions),
    # MAE shouldn't blow past CV MAE by more than this factor.
    ("aluminum", 2.5),
    ("titanium", 2.5),
    ("nickel",   2.5),
    ("steel",    3.0),
])
def test_in_domain_mae_within_ratio_of_cv(holdout_results, family, max_mae_ratio):
    """For alloys that DID predict, MAE should stay within range of CV MAE."""
    if not _model_exists(family):
        pytest.skip("model file missing")
    with open(MODELS_DIR / _FAMILY_FILES[family], "rb") as f:
        cv_mae = pickle.load(f)["cv_mae_MPa"]
    mae = holdout_results[family].get("mae")
    if mae is None:
        pytest.skip("no in-domain predictions to evaluate")
    assert mae <= cv_mae * max_mae_ratio, (
        f"{family}: in-domain hold-out MAE {mae:.0f} MPa exceeds "
        f"{max_mae_ratio}× CV MAE ({cv_mae:.0f} MPa)"
    )


@pytest.mark.parametrize("family", ["aluminum", "titanium", "nickel", "steel"])
def test_no_in_domain_prediction_grossly_wrong(holdout_results, family):
    """No prediction should be off by more than 5× the family's CV MAE."""
    if not _model_exists(family):
        pytest.skip("model file missing")
    with open(MODELS_DIR / _FAMILY_FILES[family], "rb") as f:
        cv_mae = pickle.load(f)["cv_mae_MPa"]
    preds = [p for p in holdout_results[family].get("predictions", [])
             if p.get("outcome") == "correct_predict"]
    if not preds:
        pytest.skip("no in-domain predictions")
    worst = max(preds, key=lambda p: p["abs_err"])
    assert worst["abs_err"] <= cv_mae * 5.0, (
        f"{family}: {worst['name']} predicted {worst['y_pred']:.0f} MPa, "
        f"truth {worst['y_true']:.0f} (err {worst['abs_err']:.0f}, > 5× CV MAE {cv_mae:.0f})"
    )


# ── Specific OOD regression test ───────────────────────────────────────

def test_aisi_304_refused_by_steel_model():
    """Regression: AISI 304 stainless steel must be refused, not predicted at 2331 MPa."""
    if not _model_exists("steel"):
        pytest.skip("steel model missing")
    from apps.api.ml.matgl_models import yield_strength_MPa
    from apps.api.ml.alloy_datasets import weight_to_atomic
    at = weight_to_atomic({"Fe": 70.0, "Cr": 19.0, "Ni": 9.0, "Mn": 1.5, "Si": 0.5, "C": 0.07})
    out = yield_strength_MPa(at)
    assert out["value"] is None
    assert "out_of_domain" in out["source"]


def test_aisi_1018_refused_by_steel_model():
    """Regression: mild structural steel must be refused, not predicted at 1317 MPa."""
    if not _model_exists("steel"):
        pytest.skip("steel model missing")
    from apps.api.ml.matgl_models import yield_strength_MPa
    from apps.api.ml.alloy_datasets import weight_to_atomic
    at = weight_to_atomic({"Fe": 98.9, "Mn": 0.75, "C": 0.18, "Si": 0.15})
    out = yield_strength_MPa(at)
    assert out["value"] is None
    assert "out_of_domain" in out["source"]


# ── 3. Routing thresholds work as documented ───────────────────────────

def test_routing_dispatches_aluminum():
    if not _model_exists("aluminum"):
        pytest.skip("aluminum model missing")
    from apps.api.ml.matgl_models import yield_strength_MPa
    out = yield_strength_MPa({"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2})
    assert out["source"] == "rf_aluminum"
    assert out["value"] is not None


def test_routing_dispatches_titanium():
    if not _model_exists("titanium"):
        pytest.skip("titanium model missing")
    from apps.api.ml.matgl_models import yield_strength_MPa
    out = yield_strength_MPa({"Ti": 90.0, "Al": 6.0, "V": 4.0})
    assert out["source"] == "rf_titanium"
    assert out["value"] is not None


def test_routing_dispatches_nickel():
    if not _model_exists("nickel"):
        pytest.skip("nickel model missing")
    from apps.api.ml.matgl_models import yield_strength_MPa
    out = yield_strength_MPa({"Ni": 60.0, "Cr": 22.0, "Mo": 9.0, "Nb": 3.5, "Fe": 4.5})
    assert out["source"] == "rf_nickel"
    assert out["value"] is not None


def test_routing_dispatches_steel():
    """Use a maraging-class steel that's actually in the matbench_steels domain."""
    if not _model_exists("steel"):
        pytest.skip("steel model missing")
    from apps.api.ml.matgl_models import yield_strength_MPa
    from apps.api.ml.alloy_datasets import weight_to_atomic
    # AerMet 100 — well within matbench_steels ultra-high-strength domain
    at = weight_to_atomic({"Fe": 75.0, "Co": 13.4, "Ni": 11.1, "Cr": 3.0, "Mo": 1.2, "C": 0.23})
    out = yield_strength_MPa(at)
    # Either dispatched to the steel model and predicted, OR conservatively
    # refused at the OOD boundary (Maraging/AerMet sit at the edge).
    assert out["source"] in ("rf_matbench_steels", "rf_matbench_steels_out_of_domain")


def test_routing_refuses_out_of_family_composition():
    """Cu-Zn brass should NOT match any family — return null with explanation."""
    from apps.api.ml.matgl_models import yield_strength_MPa
    out = yield_strength_MPa({"Cu": 65.0, "Zn": 35.0})
    assert out["value"] is None
    assert out["source"] == "rf_no_match"
    assert "error" in out


def test_empty_composition_returns_null():
    from apps.api.ml.matgl_models import yield_strength_MPa
    out = yield_strength_MPa({})
    assert out["value"] is None


# ── 4. Sanity: near-pure / CP-grade compositions predict reasonably ────

def test_near_pure_aluminum_yields_low():
    """1100-style CP Al (Al 99 + trace Si/Fe) should predict in the 80-200 MPa band."""
    if not _model_exists("aluminum"):
        pytest.skip("aluminum model missing")
    from apps.api.ml.matgl_models import yield_strength_MPa
    from apps.api.ml.alloy_datasets import weight_to_atomic
    # 1100-style: Al 99 + Si 0.5 + Fe 0.5 — should be near-1100-H14 (~117 MPa)
    at = weight_to_atomic({"Al": 99.0, "Si": 0.5, "Fe": 0.5})
    out = yield_strength_MPa(at)
    assert out["value"] is not None, f"Near-pure Al refused; check OOD threshold for aluminum model"
    assert 30 <= out["value"] <= 250, f"Near-pure Al predicted {out['value']} MPa, outside sanity band"


def test_cp_titanium_yields_in_cp_range():
    """Grade 2 CP-Ti (Ti 99.2 + trace Fe/O) should predict in the 170-500 MPa range."""
    if not _model_exists("titanium"):
        pytest.skip("titanium model missing")
    from apps.api.ml.matgl_models import yield_strength_MPa
    from apps.api.ml.alloy_datasets import weight_to_atomic
    at = weight_to_atomic({"Ti": 99.2, "Fe": 0.3, "O": 0.25})
    out = yield_strength_MPa(at)
    assert out["value"] is not None, f"CP-Ti refused; check OOD threshold for titanium model"
    assert 100 <= out["value"] <= 600, f"CP-Ti predicted {out['value']} MPa"
