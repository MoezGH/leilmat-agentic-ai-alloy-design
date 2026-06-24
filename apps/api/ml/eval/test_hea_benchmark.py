"""
Unit tests for the HEA benchmark (Appendix G).

Both sub-tests (G1: HEA formation energy, G2: cross-module consistency) are
exercised with stub predictors so nothing needs matgl, MP credentials, or a
network connection.
"""
from __future__ import annotations

import pytest


# ─────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def hea_references():
    from apps.api.ml.eval.hea_benchmark import HEA_REFERENCES
    return HEA_REFERENCES


@pytest.fixture(scope="module")
def stub_hea_result(hea_references):
    from apps.api.ml.eval.mp_formation_benchmark import evaluate

    def _stub(composition: dict) -> dict:
        return {"value": -0.15, "source": "stub_m3gnet", "uncertainty": 0.20}

    return evaluate(hea_references, _stub)


# ─────────────────────────────────────────────────────────────────────────
# 1. HEA reference catalogue sanity
# ─────────────────────────────────────────────────────────────────────────

def test_hea_reference_count(hea_references):
    assert len(hea_references) >= 8, (
        f"Expected ≥8 HEA references, got {len(hea_references)}"
    )


def test_hea_references_have_required_keys(hea_references):
    required = {"name", "nelements", "composition", "ref_eV_per_atom", "source"}
    for entry in hea_references:
        missing = required - entry.keys()
        assert not missing, f"Entry '{entry.get('name')}' missing keys: {missing}"


def test_hea_compositions_sum_to_one(hea_references):
    for entry in hea_references:
        total = sum(entry["composition"].values())
        assert abs(total - 1.0) < 0.01, (
            f"'{entry['name']}' composition sums to {total:.4f}, expected ~1.0"
        )


def test_hea_are_multicomponent(hea_references):
    """All HEA references must have ≥4 elements."""
    for entry in hea_references:
        n = len(entry["composition"])
        assert n >= 4, f"'{entry['name']}' has only {n} elements — not an HEA"


def test_hea_ref_values_are_negative(hea_references):
    """All reference ΔHf should be negative (HEAs are stable)."""
    for entry in hea_references:
        assert entry["ref_eV_per_atom"] < 0, (
            f"'{entry['name']}' has ref_eV_per_atom={entry['ref_eV_per_atom']} (expected < 0)"
        )


# ─────────────────────────────────────────────────────────────────────────
# 2. G1 harness output (stub predictor)
# ─────────────────────────────────────────────────────────────────────────

def test_stub_hea_result_schema(stub_hea_result):
    expected = {
        "n_evaluated", "n_skipped", "mae_meV_per_atom",
        "by_nelements", "worst",
    }
    missing = expected - stub_hea_result.keys()
    assert not missing, f"HEA result missing keys: {missing}"


def test_all_hea_evaluated(stub_hea_result, hea_references):
    assert stub_hea_result["n_evaluated"] == len(hea_references), (
        f"Only {stub_hea_result['n_evaluated']}/{len(hea_references)} HEA refs evaluated."
    )


# ─────────────────────────────────────────────────────────────────────────
# 3. G2 consistency check (stub predictor via monkeypatch)
# ─────────────────────────────────────────────────────────────────────────

def test_consistency_check_schema(monkeypatch):
    monkeypatch.setattr(
        "apps.api.ml.featurizers.formation_energy_eV_per_atom",
        lambda comp: {"value": -0.30, "source": "stub", "uncertainty": 0.10},
    )
    from apps.api.ml.eval.hea_benchmark import run_consistency_check
    result = run_consistency_check()

    required = {"n_total", "n_consistent", "consistency_pct", "inconsistent", "all_results"}
    missing = required - result.keys()
    assert not missing, f"Consistency result missing keys: {missing}"


def test_consistency_check_all_phases_evaluated(monkeypatch):
    monkeypatch.setattr(
        "apps.api.ml.featurizers.formation_energy_eV_per_atom",
        lambda comp: {"value": -0.20, "source": "stub", "uncertainty": 0.10},
    )
    from apps.api.ml.eval.hea_benchmark import run_consistency_check
    from apps.api.ml.eval.canonical_phases import CANONICAL_INTERMETALLICS
    result = run_consistency_check()
    assert result["n_total"] == len(CANONICAL_INTERMETALLICS)


def test_consistency_check_perfect_with_negative_stub(monkeypatch):
    """With a stub that always returns ΔHf = -0.3, all phases should be consistent."""
    monkeypatch.setattr(
        "apps.api.ml.featurizers.formation_energy_eV_per_atom",
        lambda comp: {"value": -0.30, "source": "stub", "uncertainty": 0.10},
    )
    from apps.api.ml.eval.hea_benchmark import run_consistency_check
    result = run_consistency_check()
    assert result["n_consistent"] == result["n_total"]
    assert result["consistency_pct"] == 100.0
    assert result["inconsistent"] == []


def test_consistency_check_fails_with_positive_stub(monkeypatch):
    """A stub predicting ΔHf > 0 should mark every canonical phase as inconsistent."""
    monkeypatch.setattr(
        "apps.api.ml.featurizers.formation_energy_eV_per_atom",
        lambda comp: {"value": +0.10, "source": "stub_broken", "uncertainty": 0.05},
    )
    from apps.api.ml.eval.hea_benchmark import run_consistency_check
    result = run_consistency_check()
    assert result["n_consistent"] == 0
    assert result["consistency_pct"] == 0.0
    assert len(result["inconsistent"]) == result["n_total"]


# ─────────────────────────────────────────────────────────────────────────
# 4. run_hea_benchmark wrapper (monkeypatched)
# ─────────────────────────────────────────────────────────────────────────

def test_run_hea_benchmark_with_stub(monkeypatch):
    monkeypatch.setattr(
        "apps.api.ml.featurizers.formation_energy_eV_per_atom",
        lambda comp: {"value": -0.18, "source": "stub", "uncertainty": 0.15},
    )
    from apps.api.ml.eval.hea_benchmark import run_hea_benchmark
    result = run_hea_benchmark()
    assert result.get("n_evaluated", 0) > 0
    assert "n_hea_references" in result
    assert "reference_source" in result
