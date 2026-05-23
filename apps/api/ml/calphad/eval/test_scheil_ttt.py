"""
Regression tests for Sprint 2 — Scheil-Gulliver solidification + Fe-C TTT.

Scheil tests are marked slow because each invocation takes ~10–50 s.  TTT
tests are essentially free (closed-form arithmetic).

Run only the fast suite:
    pytest apps/api/ml/calphad/eval/test_scheil_ttt.py -v -k "not slow"

Run everything (≈ 2 min):
    pytest apps/api/ml/calphad/eval/test_scheil_ttt.py -v
"""
from __future__ import annotations

import pytest

from apps.api.ml.calphad.ttt import (
    ttt_diagram, _Ms_andrews_C, _A1_C, _A3_C, _Bs_C,
)


# ── 1. Andrews Ms (closed-form sanity) ───────────────────────────────────────

@pytest.mark.parametrize("wt,ref_Ms,tol", [
    ({"Fe": 98.5, "C": 0.45, "Mn": 0.75},                              330, 30),
    ({"Fe": 96.7, "C": 0.40, "Cr": 1.0, "Mo": 0.2, "Mn": 0.85},        320, 30),
    ({"Fe": 95.7, "C": 0.40, "Ni": 1.8, "Cr": 0.8, "Mo": 0.25, "Mn": 0.70}, 285, 30),
    ({"Fe": 98.85,"C": 0.80, "Mn": 0.75},                              200, 30),
])
def test_andrews_Ms(wt, ref_Ms, tol):
    """Andrews (1965) Ms must reproduce ASM Handbook values."""
    Ms = _Ms_andrews_C(wt)
    assert abs(Ms - ref_Ms) <= tol, f"Ms {Ms:.1f}°C off from {ref_Ms}°C by >{tol}°C"


# ── 2. Equilibrium critical temperatures (sanity) ────────────────────────────

def test_A1_below_A3_below_910C_for_eutectoid():
    """A1 = 723°C, A3 = 727°C for a near-eutectoid steel."""
    wt = {"Fe": 99.0, "C": 0.77}
    A1 = _A1_C(wt); A3 = _A3_C(wt)
    assert 700 <= A1 <= 740
    assert 700 <= A3 <= 740      # at eutectoid A1=A3


def test_Bs_decreases_with_alloying():
    """Bainite-start temperature must drop with Cr and Mo additions."""
    plain = _Bs_C({"Fe": 99.0, "C": 0.4})
    alloy = _Bs_C({"Fe": 96.0, "C": 0.4, "Cr": 1.0, "Mo": 0.2, "Ni": 1.5})
    assert plain > alloy, f"Alloy Bs={alloy:.1f} should be below plain Bs={plain:.1f}"


# ── 3. TTT — composition gates ───────────────────────────────────────────────

def test_ttt_refuses_non_steel():
    """Al-Cu alloy must be refused by the TTT gate (not a steel)."""
    out = ttt_diagram({"Al": 95.0, "Cu": 5.0})
    assert out["value"] is None
    assert "error" in out and out["error"]


def test_ttt_refuses_cast_iron():
    """High-C cast iron (C > 1 %) must be refused."""
    out = ttt_diagram({"Fe": 95.0, "C": 3.0, "Si": 2.0})
    assert out["value"] is None


def test_ttt_refuses_stainless():
    """Highly-alloyed stainless must be refused by *either* gate."""
    # 304 stainless trips the Fe<80% gate; H13 tool steel trips total-alloy gate.
    out_304 = ttt_diagram({"Fe": 70.0, "Cr": 18.0, "Ni": 8.0, "Mn": 2.0, "C": 0.08})
    assert out_304["value"] is None
    assert out_304["error"]   # any refusal message is OK

    # M2 high-speed steel: total alloying ~17 % >> 12 % gate
    out_m2 = ttt_diagram({"Fe": 81.0, "C": 0.85, "Cr": 4.0, "V": 1.9,
                          "W": 6.0, "Mo": 5.0, "Mn": 0.3})
    assert out_m2["value"] is None
    assert "out of domain" in out_m2["error"].lower()


# ── 4. TTT — physical sanity ──────────────────────────────────────────────────

def test_ttt_noses_below_critical_temps():
    """All transformation noses must sit below their relevant equilibrium T."""
    out = ttt_diagram({"Fe": 96.7, "C": 0.40, "Cr": 1.0, "Mo": 0.2,
                      "Mn": 0.85, "Si": 0.25})
    assert out["value"] is not None
    A1 = out["critical_T_C"]["Ae1"]
    Bs = out["critical_T_C"]["Bs"]
    Ms = out["critical_T_C"]["Ms"]
    assert out["noses_ttt"]["pearlite"]["T_nose_C"] < A1 + 20
    assert out["noses_ttt"]["bainite"]["T_nose_C"]  < Bs + 5
    assert out["noses_ttt"]["bainite"]["T_nose_C"]  > Ms - 5


def test_ttt_mo_retards_pearlite():
    """Adding Mo must increase the pearlite nose time."""
    base   = ttt_diagram({"Fe": 98.5, "C": 0.40, "Mn": 0.85})
    moly   = ttt_diagram({"Fe": 98.3, "C": 0.40, "Mn": 0.85, "Mo": 0.2})
    assert moly["noses_ttt"]["pearlite"]["t_nose_s"] > base["noses_ttt"]["pearlite"]["t_nose_s"]


def test_ttt_C_lowers_Ms():
    """Carbon must lower Ms (Andrews coefficient is -423)."""
    low_C  = ttt_diagram({"Fe": 99.0, "C": 0.20, "Mn": 0.7})
    high_C = ttt_diagram({"Fe": 99.0, "C": 0.80, "Mn": 0.7})
    assert high_C["critical_T_C"]["Ms"] < low_C["critical_T_C"]["Ms"] - 200


# ── 5. TTT — full runner integration ─────────────────────────────────────────

@pytest.fixture(scope="module")
def ttt_runner_results():
    from apps.api.ml.calphad.eval.ttt_runner import run_all
    return run_all()


def test_ttt_runner_pass_rate_above_70pct(ttt_runner_results):
    rate = ttt_runner_results["pass_rate"]
    assert rate >= 0.70, (
        f"TTT runner pass rate {rate:.0%} < 70%. "
        f"Failures: {[r['name'] for r in ttt_runner_results['results'] if r['outcome'] != 'pass']}"
    )


# ── 6. Scheil — fast smoke tests (skipped if Scheil unavailable) ──────────────

def test_scheil_refuses_unsupported_chemsys():
    """Brass should be refused (no TDB)."""
    from apps.api.ml.calphad.scheil import scheil_solidification_sync
    out = scheil_solidification_sync({"Ag": 0.72, "Cu": 0.28}, 1300.0)
    assert out["value"] is None
    assert out["source"] == "scheil_no_tdb"


def test_scheil_empty_composition():
    from apps.api.ml.calphad.scheil import scheil_solidification_sync
    out = scheil_solidification_sync({}, 1300.0)
    assert out["value"] is None


# ── 7. Scheil — slow integration tests (real pycalphad calls) ─────────────────

@pytest.mark.slow
def test_scheil_alSi_eutectic_narrow_freezing_range():
    """Al-Si eutectic must have a narrow Scheil freezing range (< 15 K)."""
    from apps.api.ml.calphad.scheil import scheil_solidification_sync
    out = scheil_solidification_sync({"Al": 0.883, "Si": 0.117}, 1100.0)
    assert out["value"] is not None
    assert out["mushy_zone_K"] < 15, (
        f"Eutectic Al-Si should freeze nearly isothermally, "
        f"got mushy zone {out['mushy_zone_K']} K"
    )


@pytest.mark.slow
def test_scheil_2024_wide_freezing_range():
    """2024 wrought alloy must have a wide Scheil freezing range (> 80 K)."""
    from apps.api.ml.calphad.scheil import scheil_solidification_sync
    from apps.api.ml.calphad.eval.solidification_runner import _wt_to_mol
    out = scheil_solidification_sync(
        _wt_to_mol({"Al": 93.5, "Cu": 4.4, "Mg": 1.5, "Mn": 0.6}),
        1100.0,
    )
    assert out["value"] is not None
    assert out["mushy_zone_K"] > 80, (
        f"2024 should have wide mushy zone (hot-tearing prone), "
        f"got {out['mushy_zone_K']} K"
    )


@pytest.mark.slow
def test_scheil_response_contract():
    """Every Scheil response must carry the full key contract."""
    from apps.api.ml.calphad.scheil import scheil_solidification_sync
    out = scheil_solidification_sync({"Al": 0.883, "Si": 0.117}, 1100.0)
    for key in ("liquidus_K", "solidus_K", "mushy_zone_K", "fraction_solid_curve",
                "active_phases", "terminal_liquid", "hot_tearing_index",
                "source", "tdb", "chemsys", "calibration", "value", "error"):
        assert key in out, f"missing key '{key}'"
    assert out["source"] == "scheil_gulliver"
    assert out["calibration"] == "deterministic"


@pytest.mark.slow
def test_scheil_runner_pass_rate_above_70pct():
    """Full Scheil runner must hit ≥ 70 % pass rate on canonical castings."""
    from apps.api.ml.calphad.eval.solidification_runner import run_all
    summary = run_all()
    assert summary["pass_rate"] >= 0.70, (
        f"Scheil runner pass rate {summary['pass_rate']:.0%} < 70%. "
        f"Failures: {[r['name'] for r in summary['results'] if r['outcome'] != 'pass']}"
    )
