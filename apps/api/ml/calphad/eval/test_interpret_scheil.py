"""
Regression tests for the Scheil-Gulliver solidification interpretation.

Run:
    pytest apps/api/ml/calphad/eval/test_interpret_scheil.py -v
"""
from __future__ import annotations

import asyncio

from apps.api.ml.calphad.interpret_scheil import (
    analyse_solidification,
    _mushy_bucket,
    _hot_tearing_bucket,
    _last_phase,
    _terminal_segregation,
    interpret_solidification,
)


# ─────────────────────────────────────────────────────────────────────
# Bucket classifiers
# ─────────────────────────────────────────────────────────────────────

def test_mushy_bucket_eutectic():
    assert _mushy_bucket(5) == "eutectic"


def test_mushy_bucket_narrow():
    assert _mushy_bucket(25) == "narrow"


def test_mushy_bucket_medium():
    assert _mushy_bucket(60) == "medium"


def test_mushy_bucket_wide():
    assert _mushy_bucket(100) == "wide"


def test_mushy_bucket_very_wide():
    assert _mushy_bucket(150) == "very_wide"


def test_hot_tearing_bucket():
    assert _hot_tearing_bucket(None) == "unknown"
    assert _hot_tearing_bucket(15)   == "low"
    assert _hot_tearing_bucket(50)   == "medium"
    assert _hot_tearing_bucket(100)  == "high"


# ─────────────────────────────────────────────────────────────────────
# Terminal-segregation ranking
# ─────────────────────────────────────────────────────────────────────

def test_terminal_segregation_ranks_enrichment():
    """An Al alloy where Cu and Mg segregate hard should rank them above Al itself."""
    terminal = {"AL": 0.77, "CU": 0.09, "MG": 0.04, "SI": 0.09, "CR": 0.0}
    nominal  = {"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2}
    seg = _terminal_segregation(terminal, nominal)
    assert len(seg["top_segregants"]) == 3
    # All top segregants should have enrichment > 1 (got concentrated)
    assert all(s["enrichment_ratio"] > 1 for s in seg["top_segregants"])
    # Cu should be one of the heaviest segregants given how little there is
    # in the nominal composition relative to the terminal liquid.
    assert "Cu" in [s["element"] for s in seg["top_segregants"]]


def test_terminal_segregation_empty():
    assert _terminal_segregation(None, None) == {"top_segregants": []}
    assert _terminal_segregation({}, {})     == {"top_segregants": []}


# ─────────────────────────────────────────────────────────────────────
# Last-to-freeze phase
# ─────────────────────────────────────────────────────────────────────

def test_last_phase_picks_dominant():
    out = _last_phase({"FCC_A1": 0.39, "MG2SI": 0.001, "DIAMOND_A4": 0.0005})
    assert out == "FCC_A1"


def test_last_phase_none_for_empty():
    assert _last_phase(None) is None
    assert _last_phase({}) is None


# ─────────────────────────────────────────────────────────────────────
# Full analyse_solidification
# ─────────────────────────────────────────────────────────────────────

def test_analyse_solidification_full_schema():
    """6061 with a wide mushy zone + medium HTI → needs_care castability."""
    scheil = {
        "liquidus_K": 925, "solidus_K": 791, "mushy_zone_K": 134,
        "hot_tearing_index": 67,
        "terminal_liquid":   {"AL": 0.77, "CU": 0.09, "MG": 0.04, "SI": 0.09, "CR": 0.0},
        "terminal_eutectic": {"FCC_A1": 0.39, "MG2SI": 0.001, "DIAMOND_A4": 0.0005},
    }
    nominal = {"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2}
    out = analyse_solidification(scheil, nominal)

    for k in ("mushy_bucket", "hot_tearing_bucket", "castability_category",
              "last_to_freeze_phase", "top_segregants", "quality_warnings",
              "source", "calibration"):
        assert k in out

    assert out["mushy_bucket"]         == "very_wide"
    assert out["hot_tearing_bucket"]   == "medium"
    assert out["castability_category"] in ("needs_care", "hot_tearing_risk")
    assert out["last_to_freeze_phase"] == "FCC_A1"
    assert out["source"]               == "scheil_solidification_analysis_v1"


def test_analyse_solidification_eutectic_alloy():
    """A356 castability: eutectic Al-Si should classify excellent."""
    scheil = {
        "liquidus_K": 850, "solidus_K": 845, "mushy_zone_K": 5,
        "hot_tearing_index": 8,
        "terminal_liquid":   {"AL": 0.88, "SI": 0.12},
        "terminal_eutectic": {"FCC_A1": 0.30, "DIAMOND_A4": 0.04},
    }
    out = analyse_solidification(scheil, {"Al": 92.4, "Si": 7.0, "Mg": 0.3, "Fe": 0.2, "Cu": 0.1})
    assert out["mushy_bucket"]         == "eutectic"
    assert out["hot_tearing_bucket"]   == "low"
    assert out["castability_category"] == "excellent_for_casting"


def test_analyse_solidification_error_input():
    out = analyse_solidification({"error": "no TDB"}, None)
    assert out["mushy_bucket"] == "no_data"
    assert "no TDB" in out["quality_warnings"][0]


# ─────────────────────────────────────────────────────────────────────
# Layer 2 — deterministic fallback
# ─────────────────────────────────────────────────────────────────────

def test_fallback_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(
        "apps.api.ml.interpret_common.settings.openrouter_api_key", "",
        raising=False,
    )
    out = asyncio.run(interpret_solidification(
        composition={"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2},
        scheil_result={
            "liquidus_K": 925, "solidus_K": 791, "mushy_zone_K": 134,
            "hot_tearing_index": 67,
            "terminal_liquid":   {"AL": 0.77, "CU": 0.09},
            "terminal_eutectic": {"FCC_A1": 0.39},
        },
    ))
    assert out["source"] == "deterministic_fallback"
    assert out["interpretation"]
    # A wide-mushy + medium-HTI alloy should at least suggest reducing a
    # heavy segregant or cross-checking equilibrium.
    titles = " ".join(r["title"].lower() for r in out["recommendations"])
    assert "segregant" in titles or "equilibrium" in titles or "thin-wall" in titles
