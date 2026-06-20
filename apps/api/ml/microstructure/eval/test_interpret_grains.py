"""Tests for the grain-structure / grain-growth post-sim interpreters.

These exercise the deterministic Layer-1 analysers and the Layer-2 *fallback*
paths (no live LLM needed), and assert the honesty contract:
  * Potts grain growth never claims physical time and always carries the
    MC-time caveat; few-grain boxes get a finite-size warning.
  * Neper structure stays geometry/stats and, when dimensionless, leads with a
    set-domain recommendation.
  * Every recommendation's executable.type is within the allowed vocabulary the
    frontend knows how to apply.
"""
from __future__ import annotations

import pytest

from apps.api.ml.microstructure.interpret_grains import (
    analyse_grain_growth,
    analyse_grain_structure,
    _growth_fallback,
    _structure_fallback,
)

# Executable types the frontend pill layer knows how to apply.
ALLOWED_EXEC_TYPES = {
    "set_grow_params", "set_tessellate_params",
    "scroll_to_card", "run_predict", "info_only",
}

# Words that would betray an over-claim of physical time for the Potts model.
PHYSICAL_TIME_WORDS = ("second", "minute", "hour", "anneal time", "physical time of")


def _growth_result(grain_count=56, sweeps=150, grid=(32, 32, 32), domain_um=None):
    r = {
        "grain_count": grain_count,
        "n_sweeps": sweeps,
        "grid": list(grid),
        "mean_grain_size_voxels": 8.1,
        "size_distribution_voxels": {
            "bin_edges": [0, 3, 6, 9, 12, 15, 18],
            "counts": [8, 14, 12, 10, 7, 5],
        },
        "calibration": "qualitative",
        "warnings": [],
    }
    if domain_um is not None:
        r["domain_um"] = domain_um
        r["mean_grain_size_um"] = 24.3
    return r


def _neper_result(grain_count=100, morpho="voronoi", domain_um=None):
    r = {
        "grain_count": grain_count,
        "morpho": morpho,
        "dimensionality": "3D",
        "mean_grain_size_normalized": 0.26,
        "std_grain_size_normalized": 0.09,
        "size_distribution_normalized": {
            "bin_edges": [0, 0.1, 0.2, 0.3, 0.4, 0.5],
            "counts": [10, 30, 35, 18, 7],
        },
        "calibration": "deterministic-geometry",
        "warnings": [],
    }
    if domain_um is not None:
        r["domain_um"] = domain_um
        r["mean_grain_size_um"] = 26.0
        r["astm_grain_number"] = 7.5
    return r


def _all_exec_types_allowed(payload):
    for rec in payload["recommendations"]:
        ex = rec.get("executable")
        if ex is not None:
            assert ex["type"] in ALLOWED_EXEC_TYPES, f"bad executable type: {ex['type']}"


# ─────────────────────────────────────────────────────────────────────
# Grain growth (Potts)
# ─────────────────────────────────────────────────────────────────────

def test_growth_analysis_regime_and_uniformity():
    a = analyse_grain_growth(_growth_result(), {"Al": 44.9})
    assert a["feature"] == "grain_growth"
    assert a["calibration"] == "qualitative"
    assert a["regime"] in ("early", "intermediate", "advanced")
    assert a["uniformity"] in ("tight", "moderate", "broad")
    # MC-time caveat is always present in Layer-1 warnings.
    assert any("not physical time" in w for w in a["quality_warnings"])


def test_growth_few_grains_warns_finite_size():
    a = analyse_grain_growth(_growth_result(grain_count=8), None)
    assert any("too few" in w for w in a["quality_warnings"])


def test_growth_fallback_is_honest_and_actionable():
    a = analyse_grain_growth(_growth_result(grain_count=56, sweeps=150), None)
    fb = _growth_fallback(a, "test")
    assert fb["source"] == "deterministic_fallback"
    # Never expresses physical time.
    blob = (fb["interpretation"] + " " + " ".join(fb["honest_limitations"])).lower()
    for w in PHYSICAL_TIME_WORDS:
        assert w not in blob, f"physical-time overclaim leaked: {w!r}"
    # Carries the MC-time caveat and offers a coarsen-further move.
    assert any("not physical time" in lim for lim in fb["honest_limitations"])
    titles = [r["title"] for r in fb["recommendations"]]
    assert "Coarsen further" in titles
    _all_exec_types_allowed(fb)


def test_growth_fallback_few_grains_suggests_bigger_lattice():
    a = analyse_grain_growth(_growth_result(grain_count=8, grid=(32, 32, 32)), None)
    fb = _growth_fallback(a, "test")
    grow = [r for r in fb["recommendations"]
            if r.get("executable", {}).get("type") == "set_grow_params"]
    assert any("grid" in (r["executable"]["value"] or {}) for r in grow)


def test_growth_sweeps_suggestion_in_bounds():
    a = analyse_grain_growth(_growth_result(sweeps=150), None)
    fb = _growth_fallback(a, "test")
    for r in fb["recommendations"]:
        ex = r.get("executable") or {}
        if ex.get("type") == "set_grow_params":
            val = ex["value"] or {}
            if "sweeps" in val:
                assert 50 <= val["sweeps"] <= 2000
            if "grid" in val:
                assert 16 <= val["grid"] <= 64


# ─────────────────────────────────────────────────────────────────────
# Grain structure (Neper)
# ─────────────────────────────────────────────────────────────────────

def test_structure_dimensionless_leads_with_set_domain():
    a = analyse_grain_structure(_neper_result(domain_um=None), None)
    assert a["regime"] == "dimensionless"
    assert a["has_domain_um"] is False
    fb = _structure_fallback(a, "test")
    first = fb["recommendations"][0]
    assert first["executable"]["type"] == "set_tessellate_params"
    assert "domain_um" in (first["executable"]["value"] or {})


def test_structure_with_domain_reports_astm_regime():
    a = analyse_grain_structure(_neper_result(domain_um=100.0), None)
    assert a["has_domain_um"] is True
    assert a["regime"] in ("coarse", "medium", "fine")


def test_structure_calibration_stays_deterministic_geometry():
    a = analyse_grain_structure(_neper_result(), None)
    assert a["calibration"] == "deterministic-geometry"
    # Always flags that Neper is geometry, not a formation predictor.
    assert any("not a physics predictor" in w for w in a["quality_warnings"])


def test_structure_fallback_exec_types_allowed():
    a = analyse_grain_structure(_neper_result(morpho="voronoi"), None)
    fb = _structure_fallback(a, "test")
    _all_exec_types_allowed(fb)
    # Voronoi result offers the graingrowth-morphology move.
    vals = [r["executable"]["value"] for r in fb["recommendations"]
            if r.get("executable", {}).get("type") == "set_tessellate_params"]
    assert any(isinstance(v, dict) and v.get("morpho") == "graingrowth" for v in vals)


# ─────────────────────────────────────────────────────────────────────
# Robustness
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [None, {}, {"error": "boom"}])
def test_analysers_tolerate_empty_or_error_results(bad):
    g = analyse_grain_growth(bad, None)
    s = analyse_grain_structure(bad, None)
    assert g["calibration"] == "qualitative"
    assert s["calibration"] == "deterministic-geometry"
    # Fallbacks still produce a usable envelope.
    assert _growth_fallback(g, "x")["recommendations"]
    assert _structure_fallback(s, "x")["recommendations"]
