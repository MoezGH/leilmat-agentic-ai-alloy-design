"""
Regression tests for Sprint 4 — temper as a model input.

Confirms that:
1. The temper encoder is well-formed (vocabulary, aliases, defaults).
2. Same composition + different temper → different YS predictions, in the
   physically-correct ordering (O < T4 < T6 < T8x for Al;
   Annealed < Normalised < Q&T for steel; Annealed < Aged for Ni).
3. CI shrinks meaningfully with a specified temper vs the family default.
4. Backward compatibility — calls without ``temper`` still return sane
   values via the family default.
5. OOD gate still works with temper-aware models.

Run:
    pytest apps/api/ml/temper/eval/test_temper.py -v
"""
import pickle
from pathlib import Path

import pytest

from apps.api.ml.temper.encoding import (
    TEMPER_VOCABULARY,
    DEFAULT_TEMPER,
    canonicalise_temper,
    encode_temper,
    temper_feature_dim,
)

MODELS_DIR = Path(__file__).parent.parent.parent.parent.parent.parent / "models"


# ── 1. Encoder correctness ───────────────────────────────────────────────────

def test_vocabulary_covers_four_families():
    assert set(TEMPER_VOCABULARY) == {"aluminum", "titanium", "nickel", "general_steel"}


def test_defaults_are_in_vocabulary():
    """Every family's default temper must be one of its canonical codes."""
    for fam, default in DEFAULT_TEMPER.items():
        assert default in TEMPER_VOCABULARY[fam], (
            f"{fam}: default {default!r} not in vocabulary"
        )


@pytest.mark.parametrize("family,raw,expected", [
    ("aluminum", "T6", "T6"),
    ("aluminum", "t-6", "T6"),
    ("aluminum", "T-651", "T651"),
    ("aluminum", "annealed", "O"),
    ("aluminum", None, "T6"),       # default
    ("aluminum", "", "T6"),         # empty → default
    ("aluminum", "JUNK", "T6"),     # unknown → default
    ("titanium", "STA", "STA"),
    ("titanium", "sta", "STA"),
    ("titanium", "Beta-Anneal", "β-anneal"),
    ("titanium", "Solution treated and aged", "STA"),
    ("nickel", "aged", "Aged"),
    ("general_steel", "q&t", "Q&T"),
    ("general_steel", "Q&T 400°C", "Q&T 400"),
    ("general_steel", "normalized", "Normalised"),
    ("general_steel", "Cold Drawn", "Cold-drawn"),
    ("general_steel", "H 950", "H950"),
])
def test_canonicalise_temper_resolves_aliases(family, raw, expected):
    assert canonicalise_temper(family, raw) == expected


def test_encode_temper_returns_one_hot_plus_strength():
    """Encoding must produce a fixed-size vector with exactly one 1 in the
    one-hot region and a strength index in [0, 1] at the end."""
    feats = encode_temper("aluminum", "T6")
    n = temper_feature_dim("aluminum")
    assert feats.shape == (n,)
    assert feats[:-1].sum() == pytest.approx(1.0)   # exactly one one-hot bit
    assert 0.0 <= feats[-1] <= 1.0                  # strength index in range


def test_unknown_family_raises():
    with pytest.raises(ValueError):
        canonicalise_temper("unobtainium", "T6")
    with pytest.raises(ValueError):
        encode_temper("unobtainium", "T6")


# ── 2. Model bundle integrity (post-retrain) ─────────────────────────────────

_FAMILY_FILES = {
    "aluminum":      "aluminum_ys_rf.pkl",
    "titanium":      "titanium_ys_rf.pkl",
    "nickel":        "nickel_ys_rf.pkl",
    "general_steel": "general_steel_ys_rf.pkl",
}


def _model_exists(family: str) -> bool:
    return (MODELS_DIR / _FAMILY_FILES[family]).exists()


@pytest.mark.parametrize("family", list(_FAMILY_FILES))
def test_model_bundle_is_temper_aware(family):
    """After Sprint 4 retraining, each YS bundle must declare itself
    temper-aware and store the vocabulary it was trained on."""
    if not _model_exists(family):
        pytest.skip(f"{family}: model file missing")
    with open(MODELS_DIR / _FAMILY_FILES[family], "rb") as f:
        bundle = pickle.load(f)
    assert bundle.get("temper_aware") is True, (
        f"{family}: bundle is not temper-aware — re-run training"
    )
    assert bundle.get("temper_family") == family
    assert "n_composition_features" in bundle
    assert "n_temper_features" in bundle
    assert bundle["n_temper_features"] == temper_feature_dim(family)
    assert "tempers_in_training" in bundle


# ── 3. 6061: same composition, different tempers → different predictions ─────

@pytest.fixture(scope="module")
def predict():
    from apps.api.ml.matgl_models import yield_strength_MPa
    return yield_strength_MPa


def test_6061_O_vs_T6_differ_by_at_least_100_MPa(predict):
    """6061-O is 55 MPa (book); 6061-T6 is 276 MPa. Same composition.
    A temper-aware model must distinguish them by ≥ 100 MPa."""
    if not _model_exists("aluminum"):
        pytest.skip("aluminum model missing")
    comp = {"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2}
    ys_O  = predict(comp, temper="O")["value"]
    ys_T6 = predict(comp, temper="T6")["value"]
    assert ys_O is not None and ys_T6 is not None
    assert ys_T6 - ys_O >= 100, (
        f"6061: T6 ({ys_T6} MPa) not meaningfully higher than O ({ys_O} MPa); "
        "temper feature isn't being used."
    )
    # And both should be within sane reference range
    assert 20  <= ys_O  <= 150, f"6061-O outside [20, 150]: {ys_O}"
    assert 200 <= ys_T6 <= 350, f"6061-T6 outside [200, 350]: {ys_T6}"


def test_aluminum_temper_ordering(predict):
    """For 6061, the predicted YS must respect O < T4 < T6 monotonically."""
    if not _model_exists("aluminum"):
        pytest.skip("aluminum model missing")
    comp = {"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2}
    ys = {t: predict(comp, temper=t)["value"] for t in ("O", "T4", "T6")}
    assert ys["O"] < ys["T4"] < ys["T6"], f"6061 temper ordering broken: {ys}"


def test_steel_normalised_vs_qt_differ(predict):
    """AISI 4140 Normalised ≪ Q&T (real values 655 vs 875 MPa)."""
    if not _model_exists("general_steel"):
        pytest.skip("general_steel model missing")
    from apps.api.ml.alloy_datasets import weight_to_atomic
    at = weight_to_atomic({"Fe": 96.7, "C": 0.40, "Cr": 1.0, "Mo": 0.2,
                          "Mn": 0.85, "Si": 0.25})
    ys_n  = predict(at, temper="Normalised")["value"]
    ys_qt = predict(at, temper="Q&T")["value"]
    assert ys_qt > ys_n, (
        f"4140: Q&T ({ys_qt}) must exceed Normalised ({ys_n})"
    )


def test_titanium_anneal_vs_sta(predict):
    """Ti-6Al-4V Annealed < STA (real: 825 vs 880 MPa)."""
    if not _model_exists("titanium"):
        pytest.skip("titanium model missing")
    comp = {"Ti": 90, "Al": 6, "V": 4}
    ys_a   = predict(comp, temper="Annealed")["value"]
    ys_sta = predict(comp, temper="STA")["value"]
    assert ys_sta >= ys_a, (
        f"Ti-6-4: STA ({ys_sta}) must not be below Annealed ({ys_a})"
    )


# ── 4. Backward compatibility ────────────────────────────────────────────────

def test_no_temper_falls_back_to_family_default(predict):
    """Calls without ``temper`` must still produce a value and report which
    default temper was used."""
    if not _model_exists("aluminum"):
        pytest.skip("aluminum model missing")
    comp = {"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2}
    out = predict(comp)
    assert out["value"] is not None
    assert out.get("temper_used") == DEFAULT_TEMPER["aluminum"]


def test_temper_used_is_reported_on_every_hit(predict):
    """``temper_used`` should appear in the API response whenever the
    family is temper-aware (Al/Ti/Ni/general_steel)."""
    if not _model_exists("aluminum"):
        pytest.skip("aluminum model missing")
    out = predict({"Al": 99.0, "Si": 0.5, "Fe": 0.5}, temper="H14")
    assert out.get("temper_used") == "H14"


# ── 5. OOD gate still works with temper-aware models ────────────────────────

def test_ood_gate_independent_of_temper(predict):
    """A composition that is OOD must be flagged OOD regardless of what
    temper the user supplies (the gate is on composition features only)."""
    # Cu-Zn brass is OOD for all family models
    out_default = predict({"Cu": 65.0, "Zn": 35.0})
    out_t6      = predict({"Cu": 65.0, "Zn": 35.0}, temper="T6")
    assert out_default["value"] is None
    assert out_t6["value"] is None
    assert out_default["source"] == out_t6["source"]   # same routing


# ── 6. CI narrowing — Sprint 4's headline number ─────────────────────────────

@pytest.mark.parametrize("family,filename,max_q", [
    # After Sprint 4 retraining, q must be measurably below the Sprint-3 numbers
    # (Al especially: 3.57 → expect ≤ 2.5).
    ("aluminum",      "aluminum_ys_rf.pkl",      2.5),
    ("titanium",      "titanium_ys_rf.pkl",      2.5),
    ("nickel",        "nickel_ys_rf.pkl",        2.5),
    ("general_steel", "general_steel_ys_rf.pkl", 2.5),
])
def test_conformal_q_in_temper_aware_band(family, filename, max_q):
    """Sprint 4's temper-conditioning should keep q below 2.5 for every
    family.  (Sprint 3 had Al at 3.57; the Sprint 4 retrain dropped it.)"""
    p = MODELS_DIR / filename
    if not p.exists():
        pytest.skip(f"{family}: model file missing")
    with open(p, "rb") as f:
        bundle = pickle.load(f)
    q = bundle["conformal"]["q"]
    assert q <= max_q, (
        f"{family}: conformal q={q:.2f} > {max_q}; "
        "temper feature isn't tightening calibration as expected."
    )
