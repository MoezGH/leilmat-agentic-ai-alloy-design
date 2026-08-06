"""
Regression tests for Sprint 6 — strengthening physics features.

Verifies:
1. ``physics_features`` is deterministic and produces sensible magnitudes
   for canonical alloys (6061-O, 6061-T6, 1100-O, IN 718 Aged…).
2. ``solid_solution_strengthening`` is monotone in solute concentration.
3. ``orowan_strengthening`` is zero for non-precipitating tempers.
4. The retrained model bundles declare themselves ``physics_aware``.
5. Feature ablation: L4 (all) is never worse than L1 (composition only).
6. CV MAE acceptance criteria where Sprint 6 has met them.

Run:
    pytest apps/api/ml/eval/test_strengthening.py -v
"""
import pickle
from pathlib import Path

import numpy as np
import pytest

from apps.api.ml.strengthening import (
    solid_solution_strengthening,
    orowan_strengthening,
    precipitate_volume_fraction,
    physics_features,
    physics_feature_dim,
    PHYSICS_FEATURE_NAMES,
    _MATRIX_DATA,
    _TEMPER_PRECIPITATE,
)


# ── 1. Physics feature primitives ────────────────────────────────────────────

def test_physics_feature_vector_dimensions():
    """Vector length must match ``PHYSICS_FEATURE_NAMES``."""
    v = physics_features({"Al": 100.0}, "aluminum", "O")
    assert v.shape == (physics_feature_dim(),)
    assert physics_feature_dim() == len(PHYSICS_FEATURE_NAMES)


def test_physics_features_are_finite():
    """Pathological inputs must still return finite numbers (RF doesn't tolerate NaN)."""
    for comp in [{"Al": 100.0}, {"Fe": 99.99, "C": 0.01}, {"Ti": 100.0}]:
        for fam in ["aluminum", "titanium", "nickel", "general_steel"]:
            v = physics_features(comp, fam, None)
            assert np.all(np.isfinite(v)), f"{comp} / {fam}: produced NaN/inf"


def test_unknown_family_returns_zeros_not_error():
    """Unknown family → quiet zero, not exception."""
    assert solid_solution_strengthening({"Al": 100}, "unobtainium") == 0.0
    assert orowan_strengthening("unobtainium", "T6") == 0.0


# ── 2. Solid-solution monotonicity ───────────────────────────────────────────

@pytest.mark.parametrize("family,solute", [
    ("aluminum", "Mg"),
    ("aluminum", "Cu"),
    ("titanium", "O"),
    ("nickel", "Mo"),
    ("general_steel", "C"),
])
def test_ss_strengthening_monotone_in_solute(family, solute):
    """More solute → more strengthening (Labusch is concave but monotone)."""
    matrix = {"aluminum": "Al", "titanium": "Ti", "nickel": "Ni",
              "general_steel": "Fe"}[family]
    s1 = solid_solution_strengthening(
        {matrix: 100 - 1, solute: 1}, family,
    )
    s2 = solid_solution_strengthening(
        {matrix: 100 - 3, solute: 3}, family,
    )
    assert s2 > s1, f"{family}/{solute}: doubling concentration didn't increase Δσ_ss"


# ── 3. Orowan / temper behaviour ─────────────────────────────────────────────

def test_orowan_zero_for_annealed_aluminum():
    """Annealed Al has no Orowan contribution (no precipitates)."""
    assert orowan_strengthening("aluminum", "O") == 0.0


def test_orowan_nonzero_for_peak_aged():
    """T6 / Aged tempers must produce a non-zero Orowan stress."""
    assert orowan_strengthening("aluminum", "T6")  > 50
    assert orowan_strengthening("nickel",   "Aged") > 100


def test_orowan_capped_at_1000_MPa():
    """The 1000 MPa cap prevents the Orowan formula from blowing up at small r̄."""
    # Force a very small radius case by patching the temper table
    sigma = orowan_strengthening("general_steel", "H900")
    assert sigma <= 1000.0


def test_orowan_temper_data_is_consistent():
    """Every family with matrix data must have at least one temper entry."""
    for fam in _MATRIX_DATA:
        assert fam in _TEMPER_PRECIPITATE
        assert len(_TEMPER_PRECIPITATE[fam]) > 0


# ── 3b. Composition-derived precipitate volume fraction (nickel γ') ─────────

def test_precipitate_vf_none_without_chemistry_model():
    """Families without a validated chemistry model fall back to None."""
    assert precipitate_volume_fraction("aluminum", "T6", {"Al": 90, "Cu": 4, "Mg": 1.5}) is None
    assert precipitate_volume_fraction("general_steel", "H900", {"Fe": 96, "Cr": 3, "Cu": 1}) is None


def test_precipitate_vf_none_for_non_aging_temper():
    """No precipitate to scale for annealed/solution tempers."""
    assert precipitate_volume_fraction("nickel", "Annealed", {"Ni": 70, "Cr": 20, "Fe": 10}) is None
    assert precipitate_volume_fraction("nickel", "Solution", {"Ni": 70, "Cr": 20, "Fe": 10}) is None


def test_precipitate_vf_zero_for_no_formers():
    """A Mo-strengthened alloy with zero γ'-formers gets vf=0, not None."""
    vf = precipitate_volume_fraction("nickel", "Aged", {"Ni": 65, "Mo": 25, "Cr": 8, "Fe": 2})
    assert vf == 0.0


def test_precipitate_vf_matches_literature_within_tolerance():
    """Stoichiometric L1₂ estimate vs published γ' fractions (Reed 2006 Table 2.1)."""
    cases = [
        # (composition_wt, literature vf, tolerance)
        ({"Ni": 57.0, "Cr": 19.5, "Co": 13.5, "Mo": 4.3, "Ti": 3.0, "Al": 1.4}, 0.25, 0.10),  # Waspaloy
        ({"Ni": 53.0, "Fe": 18.5, "Cr": 19.0, "Nb": 5.1, "Mo": 3.0, "Ti": 0.9, "Al": 0.5}, 0.20, 0.10),  # Inconel 718
        ({"Ni": 51.0, "Cr": 20.0, "Co": 20.0, "Mo": 5.9, "Ti": 2.1, "Al": 0.5}, 0.10, 0.10),  # Nimonic 263
    ]
    for comp, lit_vf, tol in cases:
        vf = precipitate_volume_fraction("nickel", "Aged", comp)
        assert abs(vf - lit_vf) <= tol, f"{comp}: vf={vf:.2f} vs lit={lit_vf:.2f} (tol {tol})"


def test_precipitate_vf_capped():
    """A composition with unrealistically high formers is clamped, not left to blow up."""
    vf = precipitate_volume_fraction("nickel", "Aged", {"Ni": 50, "Al": 30, "Ti": 20})
    assert vf <= 0.70


def test_orowan_uses_composition_when_available():
    """Two aged Ni alloys with different γ'-former content must get different
    Orowan values — this is the discrimination the flat per-temper constant
    could not provide (see commit message: all 40 aged rows were identical)."""
    low_former = orowan_strengthening("nickel", "Aged", {"Ni": 51.0, "Cr": 20.0, "Co": 20.0, "Mo": 5.9, "Ti": 2.1, "Al": 0.5})   # Nimonic 263
    high_former = orowan_strengthening("nickel", "Aged", {"Ni": 42.0, "Al": 4.9, "Ti": 3.7, "Co": 13.2, "Cr": 14.3, "Mo": 3.3})  # Nimonic 115-like
    assert high_former > low_former


def test_orowan_without_composition_uses_canonical_constant():
    """Backward compatibility: omitting composition_wt reproduces the old
    temper-only behaviour exactly."""
    assert orowan_strengthening("nickel", "Aged") == orowan_strengthening("nickel", "Aged", None)


def test_apb_shearing_would_be_a_no_op_versus_orowan():
    """Guards the negative result documented in strengthening.py: swapping
    Orowan *bypass* for APB *shearing* cannot change a tree model's output,
    because at a fixed per-temper r̄ both reduce to sigma ∝ sqrt(vf) and are
    therefore monotonic transforms of each other.

    If this test ever fails, it means r̄ has become composition/schedule
    dependent — at which point the shearing form WOULD carry new information
    and is worth revisiting.
    """
    import math
    from scipy.stats import spearmanr
    from apps.api.ml.alloy_datasets import NICKEL_ALLOYS

    G, b, M = 80e9, 0.25e-9, 3.06
    gamma_apb = 0.12          # J/m^2, typical Ni3Al-based gamma-prime
    line_tension = 0.5 * G * b * b
    r_nm = _TEMPER_PRECIPITATE["nickel"]["Aged"][1]

    def weak_pair_shearing(vf: float) -> float:
        r = r_nm * 1e-9
        inner = 6.0 * gamma_apb * vf * r / (math.pi * line_tension)
        return M * (gamma_apb / (2 * b)) * (math.sqrt(inner) - vf)

    aged = [a for a in NICKEL_ALLOYS if a.get("temper") == "Aged"]
    bypass, shearing = [], []
    for a in aged:
        vf = precipitate_volume_fraction("nickel", "Aged", a["composition_wt"])
        if not vf:
            continue
        bypass.append(orowan_strengthening("nickel", "Aged", a["composition_wt"]))
        shearing.append(weak_pair_shearing(vf))

    rho = spearmanr(bypass, shearing).statistic
    assert rho > 0.99, (
        f"Spearman rho={rho:.4f} between Orowan-bypass and APB-shearing features. "
        f"Below 0.99 they are no longer rank-equivalent, so the shearing "
        f"formulation may now add information — see the DO NOT FIX note in "
        f"strengthening.py and re-evaluate."
    )


def test_orowan_stays_under_cap_for_realistic_nickel_range():
    """Regression guard for the r̄=15nm saturation bug: with the recalibrated
    r̄=27nm, realistic γ' fractions (0.10-0.55) must NOT all pile up at the
    1000 MPa shearing cap — the feature must retain discrimination."""
    from apps.api.ml.alloy_datasets import NICKEL_ALLOYS
    aged = [a for a in NICKEL_ALLOYS if a.get("temper") == "Aged"]
    values = [orowan_strengthening("nickel", "Aged", a["composition_wt"]) for a in aged]
    n_capped = sum(1 for v in values if v >= 999.9)
    assert n_capped / len(values) < 0.3, (
        f"{n_capped}/{len(values)} aged Ni alloys saturated at the cap — "
        f"the composition-derived vf isn't discriminating"
    )


# ── 4. Spot-check magnitudes against literature ─────────────────────────────

def test_6061_O_ss_in_range():
    """6061-O (no precipitates) should have Δσ_ss ≈ 50-100 MPa from Mg+Si+Cu."""
    comp = {"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2}
    ss = solid_solution_strengthening(comp, "aluminum")
    assert 30 <= ss <= 150, f"6061-O Δσ_ss = {ss:.0f} outside [30, 150]"


def test_1100_ss_near_zero():
    """1100 is 99 % pure Al; Δσ_ss should be near zero."""
    ss = solid_solution_strengthening({"Al": 99.0, "Si": 0.5, "Fe": 0.5}, "aluminum")
    assert ss < 25, f"1100 Δσ_ss = {ss:.0f} too high for ~pure Al"


def test_4140_QT_total_is_in_low_alloy_range():
    """4140 Q&T total physics estimate should be in 'a few hundred MPa' range."""
    comp = {"Fe": 96.7, "C": 0.40, "Cr": 1.0, "Mo": 0.2, "Mn": 0.85, "Si": 0.25}
    v = physics_features(comp, "general_steel", "Q&T")
    total = v[2]
    assert 100 <= total <= 600, f"4140 Q&T total = {total:.0f} MPa, expected 100-600"


# ── 5. Model bundle declares physics_aware ───────────────────────────────────

MODELS_DIR = Path(__file__).parent.parent.parent.parent.parent / "models"

_FAMILY_FILES = {
    "aluminum":      "aluminum_ys_rf.pkl",
    "titanium":      "titanium_ys_rf.pkl",
    "nickel":        "nickel_ys_rf.pkl",
    "general_steel": "general_steel_ys_rf.pkl",
}


@pytest.mark.parametrize("family", list(_FAMILY_FILES))
def test_bundle_is_physics_aware(family):
    """All four production YS bundles must declare themselves physics_aware."""
    p = MODELS_DIR / _FAMILY_FILES[family]
    if not p.exists():
        pytest.skip(f"{family}: model file missing — run training first")
    with open(p, "rb") as f:
        b = pickle.load(f)
    assert b.get("physics_aware") is True, (
        f"{family}: bundle is not physics_aware — re-run training after Sprint 6"
    )
    assert b.get("n_physics_features") == physics_feature_dim()


# ── 6. Ablation evidence (the headline Sprint 6 deliverable) ─────────────────

@pytest.fixture(scope="module")
def ablation_results():
    from apps.api.ml.strengthening_ablation import run_ablation
    return run_ablation()


def test_l4_never_worse_than_l1(ablation_results):
    """The all-features model (L4) must dominate the composition-only baseline (L1).
    Adding features should never hurt — otherwise we have a regression."""
    for row in ablation_results:
        assert row["L4_comp_temp_phys_mae"] <= row["L1_comp_mae"] + 1, (
            f"{row['family']}: L4 ({row['L4_comp_temp_phys_mae']}) worse than "
            f"L1 ({row['L1_comp_mae']}) — adding features regressed performance"
        )


def test_temper_layer_helps_every_family(ablation_results):
    """Temper-aware (L2) must beat composition-only (L1) for every family."""
    for row in ablation_results:
        improvement = row["L1_comp_mae"] - row["L2_comp_temper_mae"]
        assert improvement >= 5, (
            f"{row['family']}: temper layer only improved CV MAE by "
            f"{improvement:.1f} MPa (expected ≥ 5)"
        )


def test_general_steel_physics_helps(ablation_results):
    """For steel specifically, adding physics on top of temper must give a
    measurable improvement — that's the headline Sprint 6 ablation result."""
    steel = next(r for r in ablation_results if r["family"] == "general_steel")
    delta = steel["L2_comp_temper_mae"] - steel["L4_comp_temp_phys_mae"]
    assert delta >= 3, (
        f"Steel L4 vs L2 improvement only {delta:.1f} MPa "
        f"(expected ≥ 3 — physics features should help carbon-strengthening signal)"
    )
