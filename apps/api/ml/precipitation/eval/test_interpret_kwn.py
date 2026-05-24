"""
Regression tests for the KWN precipitation interpretation.

Run:
    pytest apps/api/ml/precipitation/eval/test_interpret_kwn.py -v
"""
from __future__ import annotations

import asyncio

from apps.api.ml.precipitation.interpret import (
    analyse_precipitation,
    interpret_precipitation,
    _orowan_estimate,
    _aging_regime,
    PHASE_PEAK_REFERENCE,
)


# ─────────────────────────────────────────────────────────────────────
# Orowan estimator
# ─────────────────────────────────────────────────────────────────────

def test_orowan_zero_for_zero_inputs():
    assert _orowan_estimate(0.0, 10.0, "aluminum") == 0.0
    assert _orowan_estimate(0.05, 0.0, "aluminum") == 0.0


def test_orowan_zero_for_unknown_family():
    assert _orowan_estimate(0.05, 10.0, "exotic") == 0.0


def test_orowan_capped_at_1000():
    """Very small precipitates should saturate at the 1000 MPa cap."""
    out = _orowan_estimate(0.10, 0.50, "aluminum")
    assert 0 < out <= 1000


def test_orowan_positive_for_peak_6061_T6():
    """β″ peak-age values give a sensible Δσ in the 100-300 MPa range."""
    out = _orowan_estimate(0.012, 5.0, "aluminum")
    assert 50 < out < 500


# ─────────────────────────────────────────────────────────────────────
# Aging-regime classifier
# ─────────────────────────────────────────────────────────────────────

def _build_trajectory(times: list[float], vfs: list[float], rs: list[float]) -> dict:
    return {"times_s": times, "vf": vfs, "r_bar_nm": rs}


def test_regime_unknown_without_trajectory():
    out, _ = _aging_regime(0.02, 10.0, None, None)
    assert out == "unknown"


def test_regime_unknown_too_few_frames():
    """Need ≥ 5 trajectory samples to compute a late-half slope."""
    traj = _build_trajectory([0, 1, 2], [0.001, 0.002, 0.005], [1, 2, 5])
    out, _ = _aging_regime(0.005, 5, traj, None)
    assert out == "unknown"


def test_regime_under_aged_when_vf_still_growing():
    """A trajectory where vf is still climbing fast → under_aged."""
    times = list(range(20))
    vfs   = [0.0001 * (i + 1) for i in range(20)]   # linear growth
    rs    = [0.5 + i * 0.1 for i in range(20)]      # slow r growth
    final_vf = vfs[-1]
    out, _ = _aging_regime(final_vf, rs[-1], _build_trajectory(times, vfs, rs), None)
    assert out == "under_aged"


def test_regime_peak_aged_when_balanced():
    """Trajectory plateau'd at peak ref → peak_aged.

    The classifier's "under_aged" trip-wire is relative vf growth ≥ 10 %
    over the late half of the trajectory; we make the late half truly
    flat by setting vf/r̄ to constant values once we're past the
    growth phase."""
    ref = PHASE_PEAK_REFERENCE["Mg2Si_beta_doubleprime"]
    times = list(range(20))
    # Early growth, then a flat plateau on the late half — that's what
    # a peak-aged trajectory actually looks like.
    vfs = ([ref["vf_peak"] * 0.5 + i * (ref["vf_peak"] * 0.05) for i in range(10)]
           + [ref["vf_peak"]] * 10)
    rs  = ([ref["r_nm_peak"] * 0.5 + i * (ref["r_nm_peak"] * 0.05) for i in range(10)]
           + [ref["r_nm_peak"]] * 10)
    out, _ = _aging_regime(vfs[-1], rs[-1],
                           _build_trajectory(times, vfs, rs), ref)
    assert out in ("peak_aged", "transitional")


# ─────────────────────────────────────────────────────────────────────
# Full analyse_precipitation
# ─────────────────────────────────────────────────────────────────────

def test_analyse_precipitation_full_schema():
    """6061-T6 β″ at the canonical 175 °C / 8 h."""
    times = [0.0, 100, 1000, 10000, 28800]
    vfs   = [0.0, 0.005, 0.018, 0.022, 0.0222]
    rs    = [1.0, 3.0, 8.0, 11.0, 12.3]
    kwn = {
        "value": {
            "volume_fraction":      0.0222,
            "mean_radius_nm":       12.3,
            "number_density_per_m3":2.86e25,
            "aging_temperature_C":  175.0,
            "aging_time_s":         28800.0,
        },
        "phase":      "Mg2Si_beta_doubleprime",
        "morphology": "needle",
        "source":     "kwn_robson_2004",
        "trajectory": {"times_s": times, "vf": vfs, "r_bar_nm": rs},
    }
    out = analyse_precipitation(kwn,
                                composition={"Al": 97.9, "Mg": 1.0, "Si": 0.6,
                                             "Cu": 0.28, "Cr": 0.2})

    for k in ("regime", "phase", "vf_predicted", "r_nm_predicted",
              "vf_reference", "r_nm_reference", "orowan_MPa",
              "aging_T_C", "aging_time_s", "trajectory_diagnostics",
              "quality_warnings", "source"):
        assert k in out

    assert out["phase"]          == "Mg2Si_beta_doubleprime"
    assert out["matrix_family"]  == "aluminum"
    assert out["vf_reference"]   == 0.012
    assert out["r_nm_reference"] == 5.0
    assert out["orowan_MPa"]     > 0
    assert out["alloy_example"]  == "6061-T6"
    assert out["source"]         == "precipitation_kinetics_analysis_v1"


def test_analyse_unknown_phase_falls_through():
    """A phase without a canonical reference still produces a valid record,
    but without ratio-to-peak diagnostics."""
    kwn = {
        "value": {"volume_fraction": 0.01, "mean_radius_nm": 5.0,
                  "number_density_per_m3": 1e22, "aging_temperature_C": 200,
                  "aging_time_s": 3600},
        "phase":      "Made_Up_Phase",
        "morphology": "sphere",
        "source":     "kwn_robson_2004",
    }
    out = analyse_precipitation(kwn)
    assert out["vf_reference"] is None
    assert out["matrix_family"] == "aluminum"   # default
    assert any("no canonical" in w for w in out["quality_warnings"])


def test_analyse_empty_kwn():
    out = analyse_precipitation({"error": "undersaturated"})
    assert out["regime"] == "no_data"
    assert out["vf_predicted"] is None
    assert "undersaturated" in out["quality_warnings"][0]


# ─────────────────────────────────────────────────────────────────────
# Layer 2 — deterministic fallback
# ─────────────────────────────────────────────────────────────────────

def test_fallback_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(
        "apps.api.ml.interpret_common.settings.openrouter_api_key", "",
        raising=False,
    )
    kwn = {
        "value": {"volume_fraction": 0.022, "mean_radius_nm": 12.0,
                  "number_density_per_m3": 1e25, "aging_temperature_C": 175,
                  "aging_time_s": 28800},
        "phase": "Mg2Si_beta_doubleprime", "morphology": "needle",
        "source": "kwn_robson_2004",
    }
    out = asyncio.run(interpret_precipitation(
        composition={"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2},
        kwn_result=kwn,
    ))
    assert out["source"] == "deterministic_fallback"
    assert out["interpretation"]
    # The fallback should always recommend cross-checking against
    # equilibrium phase fractions.
    titles = " ".join(r["title"].lower() for r in out["recommendations"])
    assert "equilibrium" in titles or "calphad" in titles or "phase" in titles
