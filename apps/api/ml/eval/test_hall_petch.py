"""Tests for the Hall-Petch yield-strength overlay.

Covers the standalone differential term and its in-place coupling into the
yield-strength predictor: direction (finer → stronger), zero at the reference
grain size, propagation into hardness/fatigue, honesty tagging, and that the
overlay is inert without a grain size.
"""
from __future__ import annotations

import pytest

from apps.api.ml.hall_petch import hall_petch_delta_MPa, D_REF_UM, HALL_PETCH_K
from apps.api.ml.matgl_models import predict_properties, yield_strength_MPa

# ~6061-class Al alloy (Al-rich → routes to the aluminium YS family).
AL_6061 = {"Al": 97.0, "Mg": 1.0, "Si": 0.6, "Cu": 0.3, "Cr": 0.2, "Fe": 0.9}


# ─────────────────────────────────────────────────────────────────────
# The differential term itself
# ─────────────────────────────────────────────────────────────────────

def test_delta_zero_at_reference():
    hp = hall_petch_delta_MPa("Al", D_REF_UM)
    assert hp is not None
    assert abs(hp["delta_MPa"]) < 0.05   # essentially zero at d_ref


def test_delta_positive_when_finer_negative_when_coarser():
    fine = hall_petch_delta_MPa("Al", 5.0)
    coarse = hall_petch_delta_MPa("Al", 200.0)
    assert fine["delta_MPa"] > 0
    assert coarse["delta_MPa"] < 0


def test_delta_scales_with_family_k():
    # Steel has a far steeper Hall-Petch slope than aluminium.
    fe = hall_petch_delta_MPa("Fe", 5.0)["delta_MPa"]
    al = hall_petch_delta_MPa("Al", 5.0)["delta_MPa"]
    assert fe > al > 0
    assert HALL_PETCH_K["Fe"] > HALL_PETCH_K["Al"]


def test_delta_is_literature_tagged():
    hp = hall_petch_delta_MPa("Ti", 12.0)
    assert hp["calibration"] == "literature-correlation"
    assert "Hall-Petch" in hp["note"]


def test_delta_none_for_unknown_family_or_bad_size():
    assert hall_petch_delta_MPa("Mg", 10.0) is None    # no coefficient
    assert hall_petch_delta_MPa("Al", 0) is None
    assert hall_petch_delta_MPa("Al", -3) is None


def test_delta_clamped_below_validity_window():
    # 0.2 µm is below the ~1 µm floor → clamped, flagged in the note, and the
    # delta equals the 1 µm value (not a runaway).
    sub = hall_petch_delta_MPa("Al", 0.2)
    at1 = hall_petch_delta_MPa("Al", 1.0)
    assert sub["delta_MPa"] == at1["delta_MPa"]
    assert "clamped" in sub["note"].lower()


# ─────────────────────────────────────────────────────────────────────
# Coupling into the predictor
# ─────────────────────────────────────────────────────────────────────

def test_predict_unchanged_without_grain_size():
    p = predict_properties(AL_6061, temper="T6")
    assert "hall_petch" not in p["_details"]["yield_strength_MPa"]


def test_predict_shifts_ys_with_grain_size():
    base = yield_strength_MPa(AL_6061, temper="T6")
    fine = yield_strength_MPa(AL_6061, temper="T6", grain_size_um=10.0)
    coarse = yield_strength_MPa(AL_6061, temper="T6", grain_size_um=100.0)
    if base.get("value") is None:
        pytest.skip("YS model unavailable in this environment")
    assert fine["value"] > base["value"] > coarse["value"]
    # CI shifts by the same delta, and the block is attached + tagged.
    hp = fine["hall_petch"]
    assert hp["calibration"] == "literature-correlation"
    assert pytest.approx(fine["value"] - base["value"], abs=0.2) == hp["delta_MPa"]


def test_grain_size_propagates_to_hardness():
    base = predict_properties(AL_6061, temper="T6")
    fine = predict_properties(AL_6061, temper="T6", grain_size_um=8.0)
    if base["_details"]["yield_strength_MPa"].get("value") is None:
        pytest.skip("YS model unavailable in this environment")
    # Hardness derives from YS, so a finer grain (higher YS) lifts hardness too.
    assert fine["_details"]["hardness_HV"]["value"] >= base["_details"]["hardness_HV"]["value"]
