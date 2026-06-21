"""Tests for the heat-treatment (aging) optimizer."""
from __future__ import annotations

import numpy as np

from apps.api.ml.precipitation.aging_optimizer import (
    optimize_aging, family_for_aging, _ppt_strength, _R_STAR_NM,
)

AL_MGSI = {"Al": 97.0, "Mg": 1.0, "Si": 0.6, "Cu": 0.3}


def test_family_gating():
    assert family_for_aging(AL_MGSI) == "aluminum"
    assert family_for_aging({"Ni": 70, "Al": 10, "Cr": 20}) == "nickel"
    assert family_for_aging({"Fe": 98, "C": 2}) is None       # steel → not Orowan-supported
    assert family_for_aging(None) is None


def test_ppt_strength_peaks_at_r_star():
    # min(shearing, looping) → max at the family critical radius r*.
    fam = "aluminum"; r_star = _R_STAR_NM[fam]; vf = 0.02
    at_peak = _ppt_strength(fam, vf, r_star)
    under = _ppt_strength(fam, vf, r_star * 0.3)   # shearable, smaller
    over = _ppt_strength(fam, vf, r_star * 5.0)    # looping, coarser
    assert at_peak > under and at_peak > over       # genuine peak at r*
    assert _ppt_strength(fam, 0, 5) == 0.0


def test_optimizer_produces_peak_aging_curve():
    r = optimize_aging(AL_MGSI, "Mg2Si_beta_doubleprime", n_temps=5, max_time_h=48)
    assert r["calibration"] == "literature-correlation"
    assert r["family"] == "aluminum"
    assert len(r["curves"]) == 5
    # The global peak equals the max Δσ across every curve.
    all_d = [d for c in r["curves"] for d in c["delta_sigma_MPa"]]
    assert r["peak"]["delta_sigma_MPa"] == max(all_d)
    # A mid curve should rise then fall (classic aging response).
    mid = r["curves"][2]["delta_sigma_MPa"]
    ipk = int(np.argmax(mid))
    assert mid[0] < mid[ipk] and mid[-1] < mid[ipk]
    # Peak radius lands at the crossover r*.
    assert abs(r["peak"]["r_nm"] - _R_STAR_NM["aluminum"]) < 1.5
    assert "Age at" in r["recommendation"]
    assert r["png_base64"]


def test_lower_temp_gives_higher_peak():
    # Classic: lower aging T → higher peak strength (slower coarsening).
    r = optimize_aging(AL_MGSI, "Mg2Si_beta_doubleprime", n_temps=5, max_time_h=100)
    per_temp_peak = {c["T_C"]: max(c["delta_sigma_MPa"]) for c in r["curves"]}
    temps = sorted(per_temp_peak)
    assert per_temp_peak[temps[0]] >= per_temp_peak[temps[-1]]


def test_unsupported_family_returns_error():
    r = optimize_aging({"Fe": 98, "C": 2}, "Mg2Si_beta_doubleprime")
    assert "error" in r
