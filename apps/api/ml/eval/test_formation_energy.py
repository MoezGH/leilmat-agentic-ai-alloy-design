"""
Regression tests for the M3GNet formation-energy predictor.

These tests guard against silent regressions in the M3GNet path — e.g. the
model file going missing, the supercell builder breaking, the fallback to
Miedema kicking in unexpectedly, or the published benchmark accuracy
collapsing after a dependency upgrade.

Thresholds are deliberately generous (200-300 meV/atom) — they're meant to
catch *catastrophic* drift, not tight accuracy. The actual measured accuracy
is reported by the scorecard CLI.

Run:
    pytest apps/api/ml/eval/test_formation_energy.py -v
"""
from __future__ import annotations

import pytest


# Threshold table (eV/atom). The intermetallic threshold is intentionally
# loose because our random-supercell approach biases predictions; the
# scorecard reports the actual MAE, which is around 80-120 meV/atom.
THRESHOLDS = {
    "pure_element":  0.010,   # zero by definition — should be exact
    "intermetallic": 0.300,   # random supercell error budget
}

# Catastrophic-failure threshold — any single point above this almost
# certainly means the model isn't loaded or a fallback heuristic kicked in.
GROSS_ERROR_THRESHOLD = 0.500


@pytest.fixture(scope="module")
def formation_results():
    """Run the M3GNet predictor against all canonical references once."""
    from apps.api.ml.eval.formation_energy_runner import run_formation_energy
    return run_formation_energy()


# ── 1. The pipeline produces predictions for every reference ──────────

def test_all_references_predicted(formation_results):
    """No reference should be silently skipped (would indicate model unavailable)."""
    assert formation_results.get("n_predicted") == formation_results.get("n_total"), (
        f"Only {formation_results.get('n_predicted')}/{formation_results.get('n_total')} predicted. "
        f"Skipped: {formation_results.get('skipped', [])}"
    )


# ── 2. Pure elements are exactly zero by definition ──────────────────

def test_pure_elements_yield_zero(formation_results):
    """Each pure element should return exactly 0 with the by_definition source."""
    pure = [p for p in formation_results["predictions"] if p["class"] == "pure_element"]
    assert pure, "no pure-element entries"
    for p in pure:
        assert p["y_pred"] == 0.0, f"{p['name']}: predicted {p['y_pred']} (expected 0.0)"
        assert p["source"] == "by_definition", f"{p['name']}: source {p['source']}"


# ── 3. No prediction should fall back to Miedema ──────────────────────

def test_intermetallics_use_m3gnet(formation_results):
    """Every intermetallic should be predicted via M3GNet, not the Miedema fallback.

    A Miedema fallback would indicate the M3GNet model failed to load — the
    answer might still be in the right ballpark but the source provenance
    label is wrong and the UI badge will mislead the user.
    """
    inter = [p for p in formation_results["predictions"] if p["class"] == "intermetallic"]
    fallbacks = [p["name"] for p in inter if p["source"] != "m3gnet_dft"]
    assert not fallbacks, f"Miedema fallback used for: {fallbacks}"


# ── 4. Aggregate MAE thresholds per class ────────────────────────────

def test_class_mae_within_threshold(formation_results):
    """Per-class MAE should not blow past the documented threshold."""
    by_class = formation_results.get("by_class", {})
    for cls, stats in by_class.items():
        thresh = THRESHOLDS.get(cls)
        if thresh is None:
            continue
        mae = stats.get("mae_eV_per_atom", float("inf"))
        assert mae <= thresh, (
            f"{cls}: MAE {mae*1000:.0f} meV/atom exceeds {thresh*1000:.0f} meV/atom"
        )


# ── 5. No single prediction is grossly wrong ─────────────────────────

def test_no_prediction_grossly_wrong(formation_results):
    """No single intermetallic should be off by more than 500 meV/atom.

    A 500-meV/atom error on an alloy with formation energy of order -0.5 eV
    means we're getting the sign right but not much else. This usually
    indicates the supercell builder picked a wildly inappropriate lattice.
    """
    inter = [p for p in formation_results["predictions"] if p["class"] == "intermetallic"]
    if not inter:
        pytest.skip("no intermetallic predictions")
    worst = max(inter, key=lambda p: p["abs_err"])
    assert worst["abs_err"] <= GROSS_ERROR_THRESHOLD, (
        f"{worst['name']}: predicted {worst['y_pred']:+.4f} eV/atom, "
        f"truth {worst['y_true']:+.4f} (err {worst['abs_err']*1000:.0f} meV/atom)"
    )


# ── 6. Signs are correct (negative for stable intermetallics) ────────

def test_intermetallics_predict_negative(formation_results):
    """Stable intermetallics (e_above_hull=0) should predict ΔH_f < 0.

    Getting the sign right is the absolute floor for a useful predictor —
    a positive predicted formation energy for a stable phase would indicate
    the model thinks it should decompose, which is qualitatively wrong.
    """
    inter = [p for p in formation_results["predictions"] if p["class"] == "intermetallic"]
    wrong_sign = [p for p in inter if p["y_pred"] >= 0]
    assert not wrong_sign, (
        f"Stable intermetallics predicted with non-negative ΔH_f: "
        f"{[(p['name'], p['y_pred']) for p in wrong_sign]}"
    )


# ── 7. Specific regression points for well-known phases ──────────────

def test_ni3al_within_150_meV():
    """Ni3Al (γ' precipitate) is the most-studied intermetallic in superalloys.
    The model should reproduce its formation energy within 150 meV/atom."""
    from apps.api.ml.featurizers import formation_energy_eV_per_atom
    out = formation_energy_eV_per_atom({"Ni": 75.0, "Al": 25.0})
    assert out["source"] == "m3gnet_dft"
    assert abs(out["value"] - (-0.4264)) < 0.150, (
        f"Ni3Al: predicted {out['value']:+.4f}, expected -0.4264 (MP)"
    )


def test_b2_nial_within_200_meV():
    """B2-NiAl bond-coat material — known DFT ground state."""
    from apps.api.ml.featurizers import formation_energy_eV_per_atom
    out = formation_energy_eV_per_atom({"Ni": 50.0, "Al": 50.0})
    assert out["source"] == "m3gnet_dft"
    assert abs(out["value"] - (-0.6849)) < 0.200, (
        f"NiAl: predicted {out['value']:+.4f}, expected -0.6849 (MP)"
    )
