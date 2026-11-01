"""
Unit tests for the calorimetry benchmark (Appendix E).

These tests use a stub predictor so they run without matgl, MP credentials, or
any network access.  They verify the benchmark harness wiring: every verified reference
is processed, the result schema is correct, and the DFT-gap note is present.
"""
from __future__ import annotations

import pytest


# ─────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def calori_references():
    from apps.api.ml.eval.calorimetry_benchmark import CALORI_REFERENCES
    return CALORI_REFERENCES


@pytest.fixture(scope="module")
def stub_result(calori_references):
    """Run the evaluate harness with a stub predictor (no matgl, no network)."""
    from apps.api.ml.eval.mp_formation_benchmark import evaluate

    def _stub(composition: dict) -> dict:
        # Mimic what M3GNet would return: -0.3 eV/atom with 0.15 uncertainty
        return {"value": -0.30, "source": "stub_m3gnet", "uncertainty": 0.15}

    return evaluate(calori_references, _stub)


# ─────────────────────────────────────────────────────────────────────────
# 1. Reference catalogue sanity checks
# ─────────────────────────────────────────────────────────────────────────

def test_reference_count(calori_references):
    """Only values checked against a published experimental compilation belong here: fewer, but true."""
    assert len(calori_references) >= 10, (
        f"Expected ≥10 verified calorimetry references, got {len(calori_references)}"
    )


def test_every_reference_names_its_published_source(calori_references):
    for entry in calori_references:
        assert any(k in entry["source"] for k in ("Kim", "JANAF", "Rzyman")), entry["name"]


def test_references_that_failed_verification_are_gone(calori_references):
    """These 13 had no independent experimental value (or a wrong one); they must not creep back unverified."""
    removed = {"Al3Ni", "γ-TiAl", "α2-Ti3Al", "Fe3Al (D03)", "Al3Fe", "Ti2Ni", "MgZn2 (C14 Laves)",
               "Al2Cu (θ)", "Cu3Au (L12)", "β-CuZn (brass)", "MoNi", "FeCo (B2)", "Al6Mn"}
    assert removed.isdisjoint({e["name"] for e in calori_references})


def test_no_value_is_implausibly_small_for_an_ordered_compound(calori_references):
    """The retired set halved real enthalpies; verified values for these compounds are all below -0.1 eV/atom."""
    for entry in calori_references:
        assert entry["ref_eV_per_atom"] < -0.1, entry["name"]


def test_all_references_have_required_keys(calori_references):
    required = {"name", "nelements", "composition", "ref_eV_per_atom", "source"}
    for entry in calori_references:
        missing = required - entry.keys()
        assert not missing, f"Entry '{entry.get('name')}' missing keys: {missing}"


def test_compositions_sum_to_one(calori_references):
    for entry in calori_references:
        total = sum(entry["composition"].values())
        assert abs(total - 1.0) < 0.01, (
            f"'{entry['name']}' composition sums to {total:.4f}, expected ~1.0"
        )


def test_all_references_are_binary(calori_references):
    """All hardcoded refs in the current catalogue are binary systems."""
    for entry in calori_references:
        assert entry["nelements"] == 2, (
            f"Expected nelements=2 for '{entry['name']}', got {entry['nelements']}"
        )


def test_all_ref_eV_negative(calori_references):
    """All stable intermetallics should have ΔHf < 0."""
    for entry in calori_references:
        assert entry["ref_eV_per_atom"] < 0, (
            f"'{entry['name']}' has ref_eV_per_atom={entry['ref_eV_per_atom']} (expected < 0)"
        )


# ─────────────────────────────────────────────────────────────────────────
# 2. Harness output schema (stub predictor — no network)
# ─────────────────────────────────────────────────────────────────────────

def test_stub_result_has_required_keys(stub_result):
    expected = {
        "n_evaluated", "n_skipped", "mae_meV_per_atom",
        "median_abs_err_meV", "max_abs_err_meV",
        "baseline_zero_mae_meV", "beats_baseline", "in_envelope_pct",
        "by_nelements", "worst", "skipped",
    }
    missing = expected - stub_result.keys()
    assert not missing, f"Result missing keys: {missing}"


def test_all_references_evaluated(stub_result, calori_references):
    assert stub_result["n_evaluated"] == len(calori_references), (
        f"Only {stub_result['n_evaluated']}/{len(calori_references)} evaluated. "
        f"Skipped: {stub_result.get('skipped')}"
    )


def test_stub_mae_is_finite(stub_result):
    mae = stub_result["mae_meV_per_atom"]
    assert isinstance(mae, float) and mae >= 0


def test_by_nelements_contains_binary(stub_result):
    assert "2" in stub_result["by_nelements"], (
        "by_nelements should contain '2' since all refs are binary"
    )


# ─────────────────────────────────────────────────────────────────────────
# 3. run_calorimetry_benchmark wrapper (stub can't be injected, skip matgl)
# ─────────────────────────────────────────────────────────────────────────

def test_run_calorimetry_benchmark_skips_gracefully(monkeypatch):
    """If M3GNet is unavailable, Miedema fallback runs and we still get results."""
    monkeypatch.setattr(
        "apps.api.ml.featurizers.formation_energy_eV_per_atom",
        lambda comp: {"value": -0.25, "source": "miedema_heuristic", "uncertainty": 0.20},
    )
    from apps.api.ml.eval.calorimetry_benchmark import run_calorimetry_benchmark
    result = run_calorimetry_benchmark()
    assert result.get("n_evaluated", 0) > 0
    assert "dft_gap_note" in result
    assert "reference_source" in result
