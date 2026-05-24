"""
Regression tests for the CALPHAD phase-assemblage interpretation pipeline.

Layer 1 (analyse_phase_assemblage) is fully tested.  Layer 2 (LLM) gets a
structural fallback-path check only — real LLM responses are
non-deterministic and CI must not make network calls.

Run:
    pytest apps/api/ml/calphad/eval/test_interpret_phases.py -v
"""
from __future__ import annotations

import asyncio

import pytest

from apps.api.ml.calphad.interpret import (
    analyse_phase_assemblage,
    _classify_regime,
    _unwanted_flags,
    interpret_phase_assemblage,
)


# ─────────────────────────────────────────────────────────────────────
# Layer 1 — regime classification
# ─────────────────────────────────────────────────────────────────────

def test_regime_single_phase():
    """A pure FCC system maps to single_phase."""
    assert _classify_regime({"FCC_A1": 0.99}) == "single_phase"


def test_regime_matrix_with_minor():
    """Dominant matrix > 90 % triggers the strengthening-precipitate label."""
    assert _classify_regime({
        "FCC_A1":  0.96, "MG2SI": 0.02, "ALCU_THETA": 0.015, "AL13CR2": 0.005
    }) == "matrix_with_minor_precipitates"


def test_regime_dual_phase():
    """Two significant phases neither dominating triggers dual_phase."""
    assert _classify_regime({"FCC_A1": 0.55, "BCC_A2": 0.45}) == "dual_phase"


def test_regime_multi_phase():
    """≥ 3 phases with no dominant matrix triggers multi_phase."""
    assert _classify_regime({
        "FCC_A1": 0.40, "BCC_A2": 0.30, "MG2SI": 0.15, "AL3FE": 0.15
    }) == "multi_phase"


def test_regime_trace_only():
    """All phases below 1 % is the convergence-warning bucket."""
    assert _classify_regime({"FCC_A1": 0.005, "MG2SI": 0.003}) == "trace_only"


def test_regime_no_phases():
    """Empty dict is no_phases_returned."""
    assert _classify_regime({}) == "no_phases_returned"


# ─────────────────────────────────────────────────────────────────────
# Layer 1 — unwanted-phase flags
# ─────────────────────────────────────────────────────────────────────

def test_unwanted_flags_detects_sigma():
    """σ-phase at > 0.1 % triggers a flag."""
    flags = _unwanted_flags({"FCC_A1": 0.95, "SIGMA": 0.05})
    assert len(flags) == 1
    assert flags[0]["phase"] == "SIGMA"
    assert "σ-phase" in flags[0]["concern"] or "brittle" in flags[0]["concern"].lower()


def test_unwanted_flags_skips_below_threshold():
    """Phases below 0.1 % are ignored as numerical noise."""
    flags = _unwanted_flags({"FCC_A1": 0.999, "SIGMA": 0.0005})
    assert flags == []


def test_unwanted_flags_detects_laves():
    flags = _unwanted_flags({"FCC_L12": 0.6, "LAVES_C14": 0.05})
    assert any("Laves" in f["concern"] for f in flags)


# ─────────────────────────────────────────────────────────────────────
# Layer 1 — full analyse_phase_assemblage
# ─────────────────────────────────────────────────────────────────────

def test_analyse_phase_assemblage_full_schema():
    """6061-T6 at aging temperature: expect FCC_A1 dominant, MG2SI present."""
    out = analyse_phase_assemblage(
        {"FCC_A1": 0.961, "MG2SI": 0.015, "ALCU_THETA": 0.008, "AL13CR2": 0.015},
        T_K=448.15,
        composition={"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2},
    )
    # Schema completeness
    for k in ("regime", "dominant_phase", "dominant_fraction",
              "secondary_phases", "unwanted_flags", "n_phases_significant",
              "T_K", "T_C", "quality_warnings", "source", "calibration"):
        assert k in out, f"missing key {k}"
    # Values
    assert out["dominant_phase"] == "FCC_A1"
    assert out["dominant_fraction"] >= 0.95
    assert out["regime"] == "matrix_with_minor_precipitates"
    assert out["T_C"] == 175.0
    assert out["n_phases_significant"] == 4   # all 4 ≥ 1 mole-%
    assert out["unwanted_flags"] == []        # nothing brittle in 6061
    assert out["source"] == "phase_assemblage_analysis_v1"


def test_analyse_empty_phases():
    out = analyse_phase_assemblage({}, T_K=600)
    assert out["regime"] == "no_data"
    assert out["dominant_phase"] is None
    assert "no phase fractions" in out["quality_warnings"][0].lower()


def test_analyse_with_sigma_phase_raises_warning():
    """σ-phase detection bubbles into quality_warnings."""
    out = analyse_phase_assemblage(
        {"FCC_A1": 0.80, "SIGMA": 0.20},
        T_K=900,
    )
    assert any("detrimental" in w.lower() for w in out["quality_warnings"])
    assert len(out["unwanted_flags"]) == 1


# ─────────────────────────────────────────────────────────────────────
# Layer 2 — deterministic fallback (no LLM in CI)
# ─────────────────────────────────────────────────────────────────────

def test_fallback_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(
        "apps.api.ml.interpret_common.settings.openrouter_api_key",
        "",
        raising=False,
    )
    out = asyncio.run(interpret_phase_assemblage(
        composition={"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2},
        T_K=448.15,
        phases={"FCC_A1": 0.96, "MG2SI": 0.02, "ALCU_THETA": 0.01, "AL13CR2": 0.01},
    ))
    assert out["source"] == "deterministic_fallback"
    assert out["interpretation"]
    assert isinstance(out["recommendations"], list)
    # The fallback should suggest KWN cross-check when there's a strengthening
    # precipitate distribution
    titles = " ".join(r["title"].lower() for r in out["recommendations"])
    assert "kwn" in titles or "precipitation" in titles or "kinetic" in titles
