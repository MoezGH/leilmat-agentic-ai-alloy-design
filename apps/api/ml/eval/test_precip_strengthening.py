"""Tests for the differential Orowan precipitation→strength overlay.

Mirrors the Hall-Petch tests: direction (finer/more vol-fraction → stronger),
zero at the canonical temper (no double-counting against the ML baseline
feature), full Orowan when the baseline temper is un-aged, honesty tagging,
and propagation into the predictor + hardness.
"""
from __future__ import annotations

import pytest

from apps.api.ml.strengthening import (
    orowan_delta_MPa, orowan_from_vf_r, canonical_precipitate,
)
from apps.api.ml.matgl_models import predict_properties, yield_strength_MPa

AL_6061 = {"Al": 97.0, "Mg": 1.0, "Si": 0.6, "Cu": 0.3, "Cr": 0.2, "Fe": 0.9}


# ─────────────────────────────────────────────────────────────────────
# The differential term
# ─────────────────────────────────────────────────────────────────────

def test_orowan_from_vf_r_finer_is_stronger():
    # At fixed vf, a finer precipitate → smaller obstacle spacing → stronger.
    fine = orowan_from_vf_r("aluminum", 0.02, 4.0)
    coarse = orowan_from_vf_r("aluminum", 0.02, 40.0)
    assert fine > coarse > 0


def test_delta_zero_when_matching_canonical():
    # Canonical T6 Al is (0.015, 8 nm); feeding the same → ~zero overlay.
    canon = canonical_precipitate("aluminum", "T6")
    hp = orowan_delta_MPa("Al", "T6", canon[0], canon[1])
    assert abs(hp["delta_MPa"]) < 0.5


def test_delta_positive_when_finer_negative_when_coarser():
    fine = orowan_delta_MPa("Al", "T6", 0.02, 4.0)
    coarse = orowan_delta_MPa("Al", "T6", 0.015, 40.0)
    assert fine["delta_MPa"] > 0
    assert coarse["delta_MPa"] < 0


def test_delta_full_orowan_when_baseline_unaged():
    # Annealed Al has canonical vf=0 → baseline 0 → delta == the full sim Orowan.
    hp = orowan_delta_MPa("Al", "O", 0.02, 6.0)
    assert hp["orowan_baseline_MPa"] == 0.0
    assert hp["delta_MPa"] == pytest.approx(hp["orowan_sim_MPa"], abs=0.2)


def test_delta_is_literature_tagged():
    hp = orowan_delta_MPa("Ni", "Aged", 0.2, 15.0)
    assert hp["calibration"] == "literature-correlation"
    assert "Orowan" in hp["note"]


def test_delta_none_for_unknown_family_or_bad_inputs():
    assert orowan_delta_MPa("Mg", "T6", 0.02, 5.0) is None    # no family mapping
    assert orowan_delta_MPa("Al", "T6", 0, 5.0) is None
    assert orowan_delta_MPa("Al", "T6", 0.02, 0) is None
    assert orowan_delta_MPa("Al", "T6", 1.5, 5.0) is not None  # vf clamp is upstream


# ─────────────────────────────────────────────────────────────────────
# Coupling into the predictor
# ─────────────────────────────────────────────────────────────────────

def test_predict_unchanged_without_precipitate_state():
    p = predict_properties(AL_6061, temper="T6")
    assert "precipitation" not in p["_details"]["yield_strength_MPa"]


def test_predict_shifts_ys_with_precipitate_state():
    base = yield_strength_MPa(AL_6061, temper="T6")
    if base.get("value") is None:
        pytest.skip("YS model unavailable in this environment")
    peak = yield_strength_MPa(AL_6061, temper="T6", precipitate_state={"vf": 0.02, "r_nm": 4.0})
    over = yield_strength_MPa(AL_6061, temper="T6", precipitate_state={"vf": 0.015, "r_nm": 40.0})
    assert peak["value"] > base["value"] > over["value"]
    pp = peak["precipitation"]
    assert pp["calibration"] == "literature-correlation"
    assert pytest.approx(peak["value"] - base["value"], abs=0.2) == pp["delta_MPa"]


def test_precipitate_state_propagates_to_hardness():
    base = predict_properties(AL_6061, temper="T6")
    if base["_details"]["yield_strength_MPa"].get("value") is None:
        pytest.skip("YS model unavailable in this environment")
    peak = predict_properties(AL_6061, temper="T6", precipitate_state={"vf": 0.02, "r_nm": 4.0})
    assert peak["_details"]["hardness_HV"]["value"] >= base["_details"]["hardness_HV"]["value"]
