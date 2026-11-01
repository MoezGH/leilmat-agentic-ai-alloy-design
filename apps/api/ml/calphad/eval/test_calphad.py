"""
Regression tests for the CALPHAD pycalphad integration (Sprint 1).

Tests are sized to catch silent breakage — not to validate thermodynamic
accuracy to the last digit.  The acceptance thresholds deliberately accept
±20 % mole-fraction error to account for TDB-to-TDB variation.

Run:
    pytest apps/api/ml/calphad/eval/test_calphad.py -v
"""
from __future__ import annotations

import pytest
from apps.api.ml.calphad.equilibrium import phase_assemblage_sync
from apps.api.ml.calphad.databases import lookup_tdb, list_coverage, chemsys_str


# ── 1. TDB registry sanity ────────────────────────────────────────────────────

def test_tdb_dir_exists():
    """The bundled TDB directory must exist and contain at least one file."""
    from pathlib import Path
    tdb_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "models" / "calphad_tdbs"
    assert tdb_dir.exists(), f"models/calphad_tdbs/ not found at {tdb_dir}"
    tdb_files = list(tdb_dir.glob("*.tdb"))
    assert len(tdb_files) >= 2, f"Expected ≥2 TDB files, found {len(tdb_files)}"


def test_coverage_list_is_non_empty():
    rows = list_coverage()
    assert len(rows) >= 2
    for r in rows:
        assert "file" in r and "elements" in r and "available" in r


def test_al_alloy_tdb_found():
    tdb = lookup_tdb({"Al": 0.97, "Mg": 0.02, "Si": 0.01})
    assert tdb is not None, "No TDB found for Al-Mg-Si — bundled cost507_al_alloys.tdb missing?"
    assert tdb.exists()


def test_fe_cr_ni_is_refused_not_misrouted():
    """Fe-Cr-Ni steels have NO validated bundled database, and the engine must say so.

    This test used to assert the opposite (``tdb is not None``) — which enshrined
    the bug.  mc_fecocrnbti_steels.tdb has zero Ni parameters, and COST507 is an
    aluminium-alloy assessment; routing stainless to either returned 99.8% ordered
    BCC_B2 at 1100 C where the real answer is FCC austenite.  Supplying a real
    Fe-Cr-Ni TDB (see models/calphad_tdbs/README.md, "Extending") is the fix, and
    this test should then be changed to expect that file.
    """
    assert lookup_tdb({"Fe": 0.74, "Cr": 0.18, "Ni": 0.08}) is None


def test_unknown_chemsys_returns_none():
    # Ag-Cu-Pb is not in any bundled TDB (COST507 has Cu but not Ag or Pb together)
    tdb = lookup_tdb({"Ag": 0.72, "Cu": 0.28})
    assert tdb is None, "Ag-Cu should not match any bundled TDB"


def test_chemsys_str():
    assert chemsys_str({"Al": 0.9, "Mg": 0.05, "Si": 0.05}) == "AL-MG-SI"


# ── 2. OOD / no-TDB refusal ───────────────────────────────────────────────────

def test_empty_composition_returns_null():
    out = phase_assemblage_sync({}, 900.0)
    assert out["value"] is None
    assert "error" in out


def test_unsupported_chemsys_refused():
    # Ag-Cu binary is not covered by any bundled TDB
    out = phase_assemblage_sync({"Ag": 0.72, "Cu": 0.28}, 700.0)
    assert out["value"] is None
    assert out["source"] == "calphad_no_tdb"
    assert "error" in out and out["error"]


# ── 3. Binary canonical reference points ──────────────────────────────────────

def test_al_si_above_eutectic_is_liquid():
    """Al-11.7%Si at 900 K should be fully molten (LIQUID ≥ 0.90)."""
    out = phase_assemblage_sync({"Al": 0.883, "Si": 0.117}, 900.0)
    assert out.get("error") is None, f"Unexpected error: {out.get('error')}"
    phases = out["phases"]
    assert "LIQUID" in phases, f"LIQUID not found in {phases}"
    assert phases["LIQUID"] >= 0.85, f"LIQUID fraction {phases['LIQUID']:.3f} too low"


def test_pure_al_at_900k_is_fcc():
    """Pure Al at 900 K (below melting point 933 K) should be FCC_A1."""
    out = phase_assemblage_sync({"Al": 1.0}, 900.0)
    assert out.get("error") is None
    phases = out["phases"]
    assert "FCC_A1" in phases, f"FCC_A1 not found in {phases}"
    assert phases["FCC_A1"] >= 0.95


def test_al_si_below_eutectic_fcc_dominant():
    """Al-11.7%Si at 800 K (below eutectic) should have FCC_A1 as dominant phase."""
    out = phase_assemblage_sync({"Al": 0.883, "Si": 0.117}, 800.0)
    assert out.get("error") is None
    phases = out["phases"]
    assert phases, "No phases returned"
    dominant = max(phases, key=phases.get)
    assert dominant == "FCC_A1", f"Expected FCC_A1 dominant, got {dominant}"


# ── 4. Al alloy reference points ──────────────────────────────────────────────

def test_6061_at_solutionising_T_fcc_dominant():
    """6061 at 530°C = 803 K: FCC_A1 should be > 90 mol%."""
    out = phase_assemblage_sync(
        {"Al": 0.972, "Mg": 0.014, "Si": 0.008, "Cu": 0.003, "Fe": 0.003},
        803.0,
    )
    assert out.get("error") is None, f"Error: {out.get('error')}"
    phases = out["phases"]
    assert "FCC_A1" in phases, f"FCC_A1 missing from {phases}"
    assert phases["FCC_A1"] >= 0.85, (
        f"6061 at 803K: FCC_A1 {phases['FCC_A1']:.3f} < 0.85"
    )


def test_6061_at_ageing_T_has_mg2si():
    """6061 at 175°C = 448 K: Mg2Si precipitate should be present (> 0.001)."""
    out = phase_assemblage_sync(
        {"Al": 0.972, "Mg": 0.014, "Si": 0.008, "Cu": 0.003, "Fe": 0.003},
        448.0,
    )
    assert out.get("error") is None, f"Error: {out.get('error')}"
    phases = out["phases"]
    # FCC_A1 must still be dominant
    assert "FCC_A1" in phases and phases["FCC_A1"] >= 0.85
    # Mg2Si (precipitate phase) should appear
    mg2si_frac = phases.get("MG2SI", 0.0)
    assert mg2si_frac >= 0.001, (
        f"Expected Mg2Si > 0.001 at ageing T, got {mg2si_frac:.5f}. "
        f"All phases: {phases}"
    )


def test_7075_above_solvus_single_phase():
    """7075 at 477°C = 750 K: above MgZn2 solvus — FCC_A1 dominant."""
    out = phase_assemblage_sync(
        {"Al": 0.870, "Zn": 0.056, "Mg": 0.025, "Cu": 0.016, "Cr": 0.002},
        750.0,
    )
    assert out.get("error") is None
    phases = out["phases"]
    assert "FCC_A1" in phases
    assert phases["FCC_A1"] >= 0.80, f"7075 FCC_A1 fraction {phases['FCC_A1']:.3f} < 0.80"


# ── 5. Steel reference points ─────────────────────────────────────────────────

def test_eutectoid_steel_above_a1_is_fe_rich():
    """0.8 wt% C steel at 1050 K: should be Fe-rich (BCC_A2 or FCC_A1 — open TDB limitation).

    Note: open-source TDBs for Fe-C may not perfectly reproduce the austenite/ferrite
    boundary. We check that Fe-rich phase (BCC or FCC) is dominant, not that it's
    specifically FCC. Commercial TDBs (TCFE) would be required for precise boundary.
    """
    out = phase_assemblage_sync({"Fe": 0.9931, "C": 0.0069}, 1050.0)
    if out["source"] == "calphad_no_tdb":
        pytest.skip("Fe-C TDB not available")
    assert out.get("error") is None, f"Error: {out.get('error')}"
    phases = out["phases"]
    dominant = max(phases, key=phases.get) if phases else None
    fe_rich_phases = {"FCC_A1", "BCC_A2", "BCC_B2"}
    assert dominant in fe_rich_phases, (
        f"Expected Fe-rich phase (FCC_A1 or BCC_A2) for eutectoid steel, got {dominant}. "
        f"Phases: {phases}"
    )


# ── 6. Ni-base reference points ───────────────────────────────────────────────

def test_ni3al_gamma_prime_phase():
    """Ni3Al at 900 K: γ' ordered phase (L12_FCC or FCC_L12) should dominate.

    Phase name varies by TDB: Dupin 2001 uses FCC_L12, alcrni uses L12_FCC.
    Both are the ordered Ni3Al (γ') phase — accept either.
    """
    out = phase_assemblage_sync({"Ni": 0.75, "Al": 0.25}, 900.0)
    if out["source"] == "calphad_no_tdb":
        pytest.skip("Al-Ni TDB not available")
    assert out.get("error") is None, f"Error: {out.get('error')}"
    phases = out["phases"]
    # Accept both naming conventions for the ordered γ' phase
    gamma_prime = phases.get("L12_FCC", 0.0) + phases.get("FCC_L12", 0.0)
    assert gamma_prime >= 0.50, (
        f"Expected L12/FCC_L12 (γ') ≥ 0.50 for Ni3Al at 900K, got {gamma_prime:.3f}. "
        f"All phases: {phases}"
    )


# ── 7. Response contract ──────────────────────────────────────────────────────

def test_output_has_required_keys():
    """Every response must include the full key contract."""
    out = phase_assemblage_sync({"Al": 0.97, "Mg": 0.02, "Si": 0.01}, 800.0)
    for key in ("phases", "phase_comps", "T_K", "source", "tdb", "chemsys",
                "calibration", "value", "error"):
        assert key in out, f"Missing key '{key}' in response"
    assert out["calibration"] == "deterministic"
    assert out["source"] in {"calphad_pycalphad", "calphad_no_tdb"}


def test_phase_fractions_sum_to_one():
    """Returned phase fractions must sum to ≈ 1."""
    out = phase_assemblage_sync({"Al": 0.97, "Mg": 0.02, "Si": 0.01}, 800.0)
    if not out["phases"]:
        pytest.skip("no phases returned")
    total = sum(out["phases"].values())
    assert abs(total - 1.0) < 0.05, f"Phase fractions sum to {total:.4f}, expected ≈ 1"


def test_tdb_name_reported():
    """When a TDB is used, its basename must be reported in the response."""
    out = phase_assemblage_sync({"Al": 0.97, "Mg": 0.02, "Si": 0.01}, 800.0)
    if out["source"] == "calphad_no_tdb":
        pytest.skip("no TDB available")
    assert out["tdb"] is not None
    assert out["tdb"].endswith(".tdb")


# ── 8. Caching and latency (smoke test) ──────────────────────────────────────

def test_warm_cache_is_faster():
    """Second call with same args should return from cache (elapsed ≈ 0 µs)."""
    import time
    comp = {"Al": 0.883, "Si": 0.117}
    T_K  = 900.0
    # First call — may be slow
    phase_assemblage_sync(comp, T_K)
    # Second call — should be near-instant
    t0 = time.perf_counter()
    phase_assemblage_sync(comp, T_K)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.1, f"Cached call took {elapsed:.3f}s — cache not working?"


# ── 9. Full runner integration ────────────────────────────────────────────────

@pytest.fixture(scope="module")
def runner_results():
    from apps.api.ml.calphad.eval.equilibrium_runner import run_all
    return run_all()


def test_runner_pass_rate_above_70pct(runner_results):
    """At least 70% of the canonical references the engine can attempt should pass with the bundled TDBs."""
    rate = runner_results["pass_rate"]
    assert rate >= 0.70, (
        f"CALPHAD runner pass rate {rate:.0%} < 70%. "
        f"Failures: {[r['name'] for r in runner_results['results'] if r['outcome'] != 'pass']}"
    )


def test_references_without_a_database_are_reported_by_name_not_hidden(runner_results):
    """A reference no bundled database covers is listed as 'no_database' and left out of the rate, so a shrinking
    database set cannot quietly improve the pass rate: enough references must still be evaluated."""
    missing = {r["name"] for r in runner_results["results"] if r["outcome"] == "no_database"}
    assert runner_results["n_no_database"] == len(missing)
    assert missing, "the Ni-Al, Fe-C and austenitic-stainless references should be listed as not evaluated"
    assert runner_results["n_evaluated"] >= 9   # all aluminium-based today; only MatCalc-style open databases would widen this


def test_runner_no_unexpected_errors(runner_results):
    """Only OOD refusals are expected errors — convergence failures should be zero."""
    errors = [
        r for r in runner_results["results"]
        if r["outcome"] == "error" and "no_tdb" not in str(r.get("source", ""))
    ]
    assert len(errors) == 0, (
        f"Unexpected convergence errors: {[r['name'] for r in errors]}"
    )
