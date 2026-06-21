"""Tests for the DAMASK CPFEM stress-strain job builder + parser.

Exercises the dependency-free parts (no DAMASK / no sandbox): family gating,
the emitted job script shape, the closed-form Hill modulus, flow-curve metric
derivation, and the calibration honesty contract.  The full solve was validated
end-to-end on the leilmat-damask-v1 snapshot during development.
"""
from __future__ import annotations

import json

import pytest

from apps.api.ml.microstructure.cpfem import (
    family_for_composition,
    build_cpfem_script,
    parse_cpfem_result,
    _hill_youngs_modulus_GPa,
    _derive_metrics,
    DEFAULT_CELLS,
    MAX_CELLS,
)


# ── family gating ──────────────────────────────────────────────────────

def test_family_fcc_for_al_ni_cu():
    assert family_for_composition({"Al": 97, "Mg": 1, "Si": 0.6}) == "fcc"
    assert family_for_composition({"Ni": 60, "Cr": 20, "Fe": 20}) == "fcc"
    assert family_for_composition({"Cu": 90, "Zn": 10}) == "fcc"


def test_family_none_for_bcc_hcp_and_empty():
    assert family_for_composition({"Fe": 98, "C": 2}) is None      # BCC steel — gated
    assert family_for_composition({"Ti": 90, "Al": 6, "V": 4}) is None  # HCP — gated
    assert family_for_composition({}) is None
    assert family_for_composition(None) is None


def test_build_script_rejects_non_fcc():
    with pytest.raises(ValueError):
        build_cpfem_script({"composition": {"Fe": 99}})


# ── emitted job script ───────────────────────────────────────────────

def test_script_has_pipeline_and_clamps():
    body = build_cpfem_script({
        "composition": {"Al": 97, "Mg": 1, "Si": 0.6},
        "cells": 999, "n_grains": 8, "max_strain": 0.02, "n_increments": 30,
    })
    # The full DAMASK pipeline is present.
    assert "from_Voronoi_tessellation" in body
    assert "DAMASK_grid" in body
    assert "phenopowerlaw" in body and "lattice: cF" in body
    assert "/tmp/cpfem_result.json" in body
    # cells clamped to MAX_CELLS (999 → 32) — appears in the embedded params.
    assert f'"cells": {MAX_CELLS}' in body


def test_script_picks_dominant_fcc_param_set():
    body_cu = build_cpfem_script({"composition": {"Cu": 95, "Al": 5}})
    assert "phase: Cu" in body_cu or '"phase_name": "Cu"' in body_cu


# ── Hill modulus (closed form) ─────────────────────────────────────────

def test_hill_modulus_matches_handbook():
    # Al ≈ 70 GPa, Cu ≈ 110-130, Ni ≈ 200-220 (polycrystal Hill averages).
    assert 65 <= _hill_youngs_modulus_GPa("Al") <= 75
    assert 110 <= _hill_youngs_modulus_GPa("Cu") <= 135
    assert 195 <= _hill_youngs_modulus_GPa("Ni") <= 230
    assert _hill_youngs_modulus_GPa("Xx") is None


# ── metric derivation ──────────────────────────────────────────────────

def test_derive_metrics_yield_and_flow():
    # Synthetic curve: linear elastic to 0.2 %, then plateau ~ 80 MPa.
    strain = [0.0, 0.001, 0.002, 0.005, 0.01, 0.02]
    stress = [0.0, 35.0, 70.0, 78.0, 80.0, 82.0]
    m = _derive_metrics(strain, stress, modulus_GPa=70.0)
    assert m["youngs_modulus_GPa"] == 70.0
    assert 60 <= m["yield_strength_MPa"] <= 85
    assert m["flow_stress_MPa"] == 82.0
    assert m["peak_stress_MPa"] == 82.0


# ── parse + honesty contract ───────────────────────────────────────────

def _good_result_bytes():
    return json.dumps({
        "ok": True, "family": "fcc", "phase": "Al", "cells": 16, "n_grains": 20,
        "max_strain": 0.02,
        "strain": [0.0, 0.0007, 0.0013, 0.002, 0.005, 0.01, 0.02],
        "stress_MPa": [0.0, 47.0, 72.0, 78.0, 80.0, 82.0, 83.6],
        "calibration": "literature-correlation",
    }).encode()


def test_parse_full_result():
    res = parse_cpfem_result({"result": _good_result_bytes()}, composition={"Al": 97})
    assert res["source"] == "damask_cpfem"
    assert res["calibration"] == "literature-correlation"   # never 'validated'
    assert res["youngs_modulus_GPa"] == _hill_youngs_modulus_GPa("Al")
    assert res["yield_strength_MPa"] is not None
    assert res["stress_strain"]["strain"] and res["stress_strain"]["stress_MPa"]
    # Honesty warnings present.
    blob = " ".join(res["warnings"]).lower()
    assert "literature" in blob and "not a validated" in blob


def test_parse_handles_failed_solve():
    bad = json.dumps({"ok": False, "error": "did not converge"}).encode()
    res = parse_cpfem_result({"result": bad})
    assert "error" in res
    assert res["calibration"] == "literature-correlation"


def test_parse_handles_missing_artifact():
    res = parse_cpfem_result({})
    assert "error" in res


# ── Neper-RVE coupling (use the user's actual grain structure) ─────────

def test_script_uses_neper_seeds_when_provided():
    seeds = [[0.1, 0.2, 0.3], [0.5, 0.5, 0.5], [0.9, 0.1, 0.7]]
    body = build_cpfem_script({"composition": {"Al": 97}, "cells": 16, "seeds": seeds})
    # The job branches onto the provided seeds (rebuilds the Neper tessellation).
    assert '"seeds"' in body and "0.1" in body
    assert "P.get(\"seeds\")" in body              # the seed branch in the template


def test_script_synthetic_when_no_seeds():
    body = build_cpfem_script({"composition": {"Al": 97}, "n_grains": 12})
    assert '"seeds": null' in body                 # no Neper seeds → random RVE


def test_parse_reports_neper_rve_source():
    raw = json.dumps({
        "ok": True, "family": "fcc", "phase": "Al", "cells": 16, "n_grains": 12,
        "max_strain": 0.02, "rve_source": "neper",
        "strain": [0.0, 0.0007, 0.002, 0.02], "stress_MPa": [0.0, 47.0, 78.0, 83.6],
    }).encode()
    res = parse_cpfem_result({"result": raw}, composition={"Al": 97})
    assert res["rve_source"] == "neper"
    assert any("your Neper grain structure" in w for w in res["warnings"])


def test_neper_seed_parser():
    from apps.api.ml.microstructure.grain_tessellation import _parse_seeds
    tess = (b"**cell\n 3\n *id\n 1 2 3\n *seed\n"
            b"   1 0.191751 0.291733 0.211349 0.0\n"
            b"   2 0.308081 0.316197 0.846611 0.0\n"
            b"   3 0.299754 0.352014 0.625805 0.0\n"
            b" *ori\n  rodrigues:passive\n   0 0 0\n")
    seeds = _parse_seeds(tess)
    assert len(seeds) == 3
    assert seeds[0] == [0.19175, 0.29173, 0.21135]
    assert _parse_seeds(None) == []
