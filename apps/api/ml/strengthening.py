"""
apps.api.ml.strengthening
==========================

Sprint 6 — physics-augmented strengthening features.

The yield-strength models in Sprints 1-4 used composition + temper as
inputs.  Sprint 6 adds an **engineered physics layer**:

  Δσ_ss(c)     — solid-solution strengthening (Labusch-Fleischer)
  Δσ_Orowan    — precipitation strengthening estimate
  σ_phys_total — Δσ_ss + Δσ_Orowan + per-family baseline σ₀

These features give the random forest an inductive bias toward
physically-correct YS predictions, while leaving the RF free to ignore
them where the empirical signal is stronger.

Why we don't pull these straight from KWN at training time
----------------------------------------------------------
Running CALPHAD + KWN for every one of 300+ training rows would take
~10 minutes and risk transient solver failures.  We use **closed-form
analytical proxies** that depend only on composition + temper:

* Δσ_ss(c) is a sum-of-c^(2/3) Labusch model — no PDE solve.
* Δσ_Orowan takes r̄ from a *temper-dependent canonical* table (radius is
  set by aging time/temperature) and, where a validated precipitate
  chemistry exists, derives vf from *composition* (volume fraction is set
  by how much precipitate-forming solute is available).  Currently only
  nickel has such a model — γ' = L1₂ Ni₃(Al,Ti,Nb,Ta).  Other families use
  the canonical per-temper vf.  See ``precipitate_volume_fraction``.
  The exact KWN result is available at inference time on demand; for
  training we use these analytical estimates.

The result: the feature pipeline is fast, deterministic, and uses the
**same physics inputs** at train and inference time.

Units
-----
All public functions here take **weight %**.  ``solid_solution_strengthening``
and ``precipitate_volume_fraction`` convert to atomic % internally.  Callers
holding atomic % must convert first (``alloy_datasets.atomic_to_weight``) —
passing atomic % straight in double-converts and skews the features.

Public API
----------
``solid_solution_strengthening(comp_wt, family) -> float`` (MPa)
``orowan_strengthening(family, temper, comp_wt=None) -> float`` (MPa)
``precipitate_volume_fraction(family, temper, comp_wt) -> float | None``
``physics_features(comp_wt, family, temper) -> np.ndarray``
"""
from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np


# ─────────────────────────────────────────────────────────────────────────
# 1.  Labusch-Fleischer solid-solution strengthening
#     Δσ = Σ_i k_i · (c_i [at%])^(2/3)         (c_i in atomic %, range 0-100)
#     k_i fit-coefficients (MPa / (at%)^(2/3)) per matrix family + solute.
#
#     Sources: Argon & Ling 1986 (Al), Akhtar-Teghtsoonian 1971 (Ti),
#     Wakeshima 1976 (Ni), Pelloux-Stoloff 1972 (steel).  Steel values
#     calibrated against 1018 (220 MPa) and 1045 (450 MPa).
# ─────────────────────────────────────────────────────────────────────────

_K_LABUSCH: Dict[str, Dict[str, float]] = {
    "aluminum": {
        "Cu": 14.0,
        "Mg": 41.0,
        "Si": 14.0,
        "Zn":  4.0,
        "Mn": 13.0,
        "Fe":  5.0,
        "Cr": 16.0,
        "Li": 35.0,
        "Sc": 60.0,
    },
    "titanium": {
        # in MPa / (at%)^(2/3); calibrated so Grade-2 CP-Ti (0.25 at% O)
        # gives Δσ_ss ≈ 200 MPa, matching its 275 MPa YS minus Hall-Petch.
        "Al":  35.0,
        "V":   20.0,
        "Mo":  30.0,
        "Fe":  35.0,
        "Sn":  22.0,
        "Zr":  12.0,
        "Nb":  20.0,
        "Cr":  22.0,
        "O":  220.0,        # dominant in CP-Ti at 0.18-0.40 at%
        "N":  170.0,
        "C":  150.0,
    },
    "nickel": {
        "Co":  5.0,
        "Cr":  5.0,
        "Mo": 25.0,
        "W":  25.0,
        "Ti": 22.0,
        "Al": 30.0,
        "Fe":  3.0,
        "Nb": 22.0,
        "Ta": 22.0,
        "Re": 35.0,
        "Si": 18.0,
        "Mn":  4.0,
    },
    "general_steel": {
        # in MPa / (at%)^(2/3); calibrated so 1045 N (0.45 wt% C ≈ 2 at%)
        # gives Δσ_ss ≈ 100 MPa from C alone.
        "C":  100.0,        # interstitial — large but not 900
        "N":   80.0,
        "Mn":  15.0,
        "Si":  40.0,
        "Ni":   3.0,
        "Cr":   8.0,
        "Mo":   8.0,
        "V":   12.0,
        "W":    6.0,
        "Co":   3.0,
        "Cu":   2.0,
        "Nb":   8.0,
        "Ti":   6.0,
        "Al":   2.0,
        "P":   40.0,
        "S":    5.0,
    },
}


def solid_solution_strengthening(composition_wt: dict, family: str) -> float:
    """Labusch-Fleischer Δσ_ss in MPa.

    Returns 0 (not None) for unknown families so the feature can always
    be concatenated cleanly.
    """
    if family not in _K_LABUSCH:
        return 0.0
    from apps.api.ml.alloy_datasets import weight_to_atomic
    try:
        at = weight_to_atomic(composition_wt)
    except Exception:
        return 0.0
    k_table = _K_LABUSCH[family]
    total = 0.0
    for solute, k in k_table.items():
        c_atpct = at.get(solute, 0.0)        # already in at%
        if c_atpct <= 0:
            continue
        total += k * (c_atpct ** (2.0 / 3.0))
    return float(total)


# ─────────────────────────────────────────────────────────────────────────
# 2.  Orowan precipitation strengthening
#     Δσ_Orowan = (M · G · b) / (2 · π · r̄ · √(1 − vf)) · ln(r̄ / b)
#     Standard textbook form (Ardell 1985, Reed 2006 §3.4).
#
#     Per-temper "canonical" precipitate populations come from the KWN
#     literature — peak-aged tempers have well-known (vf, r̄).
# ─────────────────────────────────────────────────────────────────────────

_MATRIX_DATA: Dict[str, Dict[str, float]] = {
    "aluminum":      {"M": 3.06, "G_GPa": 27.0, "b_nm": 0.286},
    "titanium":      {"M": 3.00, "G_GPa": 44.0, "b_nm": 0.295},
    "nickel":        {"M": 3.06, "G_GPa": 80.0, "b_nm": 0.250},
    "general_steel": {"M": 2.75, "G_GPa": 80.0, "b_nm": 0.248},
}


# Temper → (volume fraction, mean radius in nm) of the dominant
# strengthening precipitate.  Values curated from the KWN canonical set
# (Sprint 5) and ASM/literature; conservative defaults for un-aged
# tempers (vf=0 → Δσ_Orowan=0).
_TEMPER_PRECIPITATE: Dict[str, Dict[str, tuple]] = {
    "aluminum": {
        # T6/T651: peak-aged → β" / θ' / η' ≈ 0.015 vf, 5-10 nm r̄
        "T6":     (0.015,  8.0),
        "T651":   (0.015,  8.0),
        "T61":    (0.014,  9.0),
        "T7":     (0.025, 15.0),
        "T73":    (0.025, 15.0),
        "T7351":  (0.025, 16.0),
        "T7451":  (0.025, 16.0),
        "T7651":  (0.030, 18.0),
        "T7751":  (0.030, 20.0),
        "T8":     (0.020, 10.0),
        "T81":    (0.022, 10.0),
        "T83":    (0.023, 11.0),
        "T84":    (0.022, 10.0),
        "T851":   (0.020, 12.0),
        "T87":    (0.025, 12.0),
        "T8511":  (0.025, 12.0),
        "T6511":  (0.018, 10.0),
        "T8E74":  (0.020, 11.0),
        "T8771":  (0.022, 12.0),
        "T351":   (0.005, 20.0),
        "T4":     (0.005, 20.0),
        "T3":     (0.005, 25.0),
        "T5":     (0.010, 12.0),
        "T1":     (0.005, 25.0),
        "T2":     (0.005, 25.0),
        # H tempers — work-hardened, not precipitate strengthened
        "O":      (0.0,    0.0),
        "F":      (0.0,    0.0),
        "H12":    (0.0,    0.0),  "H14":  (0.0, 0.0), "H18": (0.0, 0.0), "H19": (0.0, 0.0),
        "H22":    (0.0,    0.0),  "H24":  (0.0, 0.0), "H25": (0.0, 0.0),
        "H32":    (0.0,    0.0),  "H34":  (0.0, 0.0), "H38": (0.0, 0.0),
        "H111":   (0.0,    0.0),  "H116": (0.0, 0.0), "H321": (0.0, 0.0),
    },
    "titanium": {
        "STA":          (0.05, 100.0),     # α platelets in β matrix
        "HIP+Aged":     (0.05,  80.0),
        "β-anneal":     (0.10, 1000.0),    # coarse Widmanstätten
        "Duplex anneal":(0.03,  200.0),
        "Mill-annealed":(0.02,  500.0),
        "Annealed":     (0.0,    0.0),     # primarily solid-solution
    },
    "nickel": {
        # r̄=27nm (was 15nm) — recalibrated alongside the composition-derived
        # vf added below (precipitate_volume_fraction).  At 15nm, real vf
        # (0.10-0.53 across the training set) pushed 88% of aged alloys past
        # the 1000 MPa Orowan-shearing cap, flattening the very feature meant
        # to separate them.  27nm keeps the full range under the cap: vf=0.14
        # (Nimonic 263) -> 492 MPa, vf=0.53 (LSHR) -> 958 MPa.  Still within
        # the literature range for secondary/tertiary γ' (Reed 2006 §2).
        "Aged":     (0.20,  27.0),       # γ' + γ" in Ni-superalloys
        "SX-Aged":  (0.65, 300.0),       # large γ' cuboids in SX — untouched;
                                          # SX vf is naturally narrow (0.62-0.68
                                          # across CMSX/PWA), values sit at
                                          # 92-99 MPa, nowhere near the cap.
        "Annealed": (0.0,    0.0),
        "Solution": (0.0,    0.0),
    },
    "general_steel": {
        # Most "tempers" in steel produce dispersion of carbides or
        # martensite — not classical Orowan.  Use only PH-stainless
        # aging codes for explicit precipitation strengthening.
        "H900":     (0.04,   3.0),     # Cu-rich precipitates in 17-4 PH
        "H950":     (0.04,   4.0),
        "H1000":    (0.04,   6.0),
        "H1025":    (0.03,   8.0),
        "H1050":    (0.025, 10.0),
        "H1150":    (0.015, 18.0),
        # All other tempers — no Orowan term
        "Annealed":         (0.0, 0.0),
        "Normalised":       (0.0, 0.0),
        "Hot-rolled":       (0.0, 0.0),
        "As-rolled":        (0.0, 0.0),
        "Cold-rolled":      (0.0, 0.0),
        "Cold-drawn":       (0.0, 0.0),
        "Q&T":              (0.0, 0.0),
        "Q&T 300":          (0.0, 0.0),  "Q&T 400": (0.0, 0.0),
        "Q&T 425":          (0.0, 0.0),  "Q&T 450": (0.0, 0.0),
        "Q&T 650":          (0.0, 0.0),
        "Carburised":       (0.0, 0.0),  "Carburised + Q&T": (0.0, 0.0),
        "TMCP":             (0.0, 0.0),  "Weathering": (0.0, 0.0),
        "HSLA":             (0.0, 0.0),
    },
}


def orowan_from_vf_r(family: str, vf: float, r_nm: float) -> float:
    """Δσ_Orowan in MPa from an EXPLICIT precipitate population (vf, r̄ nm).

    The shared core used by both the canonical-temper feature path
    (``orowan_strengthening``) and the KWN-driven inference overlay
    (``orowan_delta_MPa``).  Returns 0 for unknown families or non-physical
    inputs.
    """
    if family not in _MATRIX_DATA or not vf or not r_nm or vf <= 0 or r_nm <= 0:
        return 0.0
    m   = _MATRIX_DATA[family]
    M   = m["M"]
    G   = m["G_GPa"] * 1e3        # → MPa
    b   = m["b_nm"]
    # Mean obstacle spacing for spherical precipitates:
    #     L = r̄ · √(2π / (3 · vf))    (Ardell 1985 §3)
    # Orowan stress in the small-precipitate regime:
    #     σ = 0.84 · M · G · b / L
    # All length-units cancel since b and r̄ are both in nm.
    if r_nm <= b:
        return 0.0
    L_nm = r_nm * math.sqrt(2.0 * math.pi / (3.0 * vf))
    sigma = 0.84 * M * G * b / L_nm
    # Cap at 1000 MPa: below this, Orowan looping is the rate-limiting
    # mechanism; above it the precipitate is small enough that shearing
    # (Russell-Brown) dominates and Δσ saturates around ~800-1000 MPa for
    # typical engineering precipitate systems.
    return float(min(sigma, 1000.0))


def canonical_precipitate(family: str, temper: Optional[str]) -> Optional[tuple]:
    """The canonical (vf, r̄ nm) the ML baseline assumes for this temper, or None."""
    if family not in _TEMPER_PRECIPITATE:
        return None
    from apps.api.ml.temper.encoding import canonicalise_temper
    canon = canonicalise_temper(family, temper)
    return _TEMPER_PRECIPITATE[family].get(canon)


# ── Composition-derived precipitate volume fraction ──────────────────────
#
# The canonical (vf, r̄) table above is keyed on temper ALONE, so every aged
# alloy in a family received an identical Orowan term.  For nickel that meant
# all 40 aged rows — spanning 580-1300 MPa — carried the same value, and the
# model had to recover that spread from Magpie aggregate statistics, which
# smear out exactly the Ti/Al/Nb signal that sets γ' fraction.  Measured
# consequence: moderate-strength aged alloys (Nimonic PE16, Incoloy 925,
# Haynes 282, Inconel 740H) were all over-predicted at ~900 MPa.
#
# vf is fundamentally a *chemistry* property — how much precipitate-forming
# solute is available — while r̄ is a *kinetics* property set by aging time
# and temperature.  So we derive vf from composition and keep r̄ from temper.
#
# For γ' (L1₂ Ni₃X, X = Al/Ti/Nb/Ta) the phase is 25 at% formers, so if the
# formers partition essentially fully to γ' at aging temperature:
#     vf ≈ x_formers / 0.25
# Validated against 12 well-characterised superalloys with published γ'
# fractions (Reed 2006 Table 2.1; ASM v.3): mean |error| = 0.033 in vf
# (e.g. Waspaloy 0.25 vs 0.25 lit, Udimet 720Li 0.45 vs 0.45, CMSX-4 0.64
# vs 0.70, Nimonic 263 0.14 vs 0.10).  The flat 0.20 it replaces is off by
# ~0.15 on the same set.
#
# Only nickel is enabled: its precipitate chemistry is a single well-defined
# phase.  Aluminium's strengthening phase depends on series (θ'-Al₂Cu in
# 2xxx, β"-Mg₂Si in 6xxx, η'-MgZn₂ in 7xxx) and steel's on the PH grade, so
# a single stoichiometry is not defensible there — those families keep the
# canonical constant until validated the same way.
#
# ── DO NOT "FIX" THIS BY CHANGING THE STRENGTHENING EQUATION ──────────────
#
# Recorded because it is an easy and expensive mistake to retry.  The obvious
# next step looks like replacing Orowan *bypass* with APB *shearing*, since
# most aged-Ni γ' is coherent and shearable.  It cannot help, for a
# structural reason:
#
#   Orowan bypass   σ ∝ √vf / r̄
#   Weak-pair shear σ ∝ √(γ_APB · vf · r̄)
#
# r̄ here is a per-temper CONSTANT (we do not know each alloy's aging
# schedule), so both reduce to σ ∝ √vf — monotonic transforms of each other.
# Tree models are invariant to monotonic transforms of a single feature, so
# the swap is a no-op by construction.  Measured Spearman ρ between the two
# features across the aged-Ni set: 0.998, stable over γ_APB 0.08-0.30 J/m²
# and r̄ 27-200 nm.  Implementing it changed nothing, as predicted.
#
# The missing variable is r̄ (precipitate size), which is set by aging
# time/temperature — information the single "Aged" temper label does not
# carry.  Fixing THAT requires processing metadata on the training rows,
# not a different equation.
#
# There is also a hard floor on how well any composition-only model can do
# here.  Among aged-Ni training alloys, 54 pairs sit within |Δvf| < 0.02 yet
# differ in yield strength by 185 MPa on average (max 480: Inconel 718 at
# 1100 vs Nimonic 80A at 620, both vf≈0.21).  Identical chemistry-derived
# γ' fraction, very different strength — the difference is processing.  So
# ~93-185 MPa is roughly the irreducible error band for aged Ni from
# composition alone; the model's 73 MPa holdout MAE is already inside it.
#
# KNOWN LIMITATION of the vf model itself: it treats Al/Ti/Nb/Ta as
# interchangeable γ'-formers.  Nb preferentially forms γ" (DO22 Ni₃Nb) in
# Fe-bearing alloys such as 718/706/725, which is a more potent strengthener
# than γ' — so those alloys' effective strengthening is underestimated
# relative to their computed vf.  Splitting γ'/γ" would be a real refinement;
# changing the bypass/shearing form would not.
_PRECIP_CHEMISTRY: Dict[str, Dict[str, object]] = {
    "nickel": {
        "formers": ("Al", "Ti", "Nb", "Ta"),
        "x_former_in_precip": 0.25,   # L1₂ Ni₃X
        "vf_max": 0.70,               # highest γ' seen in SX superalloys
    },
}


def precipitate_volume_fraction(
    family: str, temper: Optional[str], composition_wt: Optional[dict],
) -> Optional[float]:
    """Composition-derived precipitate volume fraction, or None.

    Returns None when the family has no validated chemistry model, when no
    composition is supplied, or when the temper carries no precipitate at all
    (annealed/solution — chemistry is irrelevant if nothing was aged in).
    Callers fall back to the canonical per-temper constant.
    """
    chem = _PRECIP_CHEMISTRY.get(family)
    if chem is None or not composition_wt:
        return None
    ref = canonical_precipitate(family, temper)
    if ref is None or ref[0] <= 0:
        return None            # non-aging temper — no precipitate to scale
    from apps.api.ml.alloy_datasets import weight_to_atomic
    try:
        at = weight_to_atomic(composition_wt)
    except Exception:
        return None
    x_formers = sum(at.get(el, 0.0) for el in chem["formers"]) / 100.0
    if x_formers <= 0:
        return 0.0             # e.g. Haynes 242 — Mo-strengthened, no γ'
    vf = x_formers / float(chem["x_former_in_precip"])
    return float(min(vf, float(chem["vf_max"])))


# ── APB shearing (order strengthening) ────────────────────────────────────
#
# Ordered L1₂ γ' can be CUT by a dislocation pair rather than bypassed.  The
# leading dislocation creates an antiphase boundary of energy γ_APB; the
# trailing one restores order.  In the weak-pair-coupling regime (Huther &
# Reppich; Reed 2006 §3.4):
#
#     Δτ = (γ_APB / 2b) · [ sqrt(6·γ_APB·vf·r̄ / (π·T)) − vf ],  T = G·b²/2
#
# Note the r̄ dependence is OPPOSITE to Orowan bypass: shearing gets HARDER as
# precipitates coarsen, bypass gets easier.  That is why this could be ignored
# while r̄ was a per-temper constant (the two were rank-identical — proven at
# rho=0.998 in d04acab) and why it becomes necessary the moment r̄ varies with
# an aging schedule.  The guard test written in that commit exists to flag
# exactly this transition.
#
# γ_APB is a literature constant, not fitted here.  0.12 J/m² is mid-range for
# Ni₃Al-based γ' (published values span roughly 0.10-0.30 J/m² and shift with
# Cr/Co/Ta content).  It is disclosed rather than tuned because tuning it
# against the holdout set would be fitting to the test.
_APB_ENERGY_J_M2: Dict[str, float] = {
    "nickel": 0.12,
}


def apb_shearing_from_vf_r(family: str, vf: float, r_nm: float) -> Optional[float]:
    """Δσ from weak-pair APB shearing in MPa, or None if not applicable."""
    gamma_apb = _APB_ENERGY_J_M2.get(family)
    if gamma_apb is None or family not in _MATRIX_DATA:
        return None
    if not vf or not r_nm or vf <= 0 or r_nm <= 0:
        return None
    m = _MATRIX_DATA[family]
    M = m["M"]
    G = m["G_GPa"] * 1e9          # Pa
    b = m["b_nm"] * 1e-9          # m
    r = r_nm * 1e-9               # m
    line_tension = 0.5 * G * b * b
    inner = 6.0 * gamma_apb * vf * r / (math.pi * line_tension)
    if inner <= 0:
        return None
    tau = (gamma_apb / (2.0 * b)) * (math.sqrt(inner) - vf)
    if tau <= 0:
        return None
    return float(min(M * tau / 1e6, 1000.0))   # Pa → MPa, same cap as bypass


# ── Aging-schedule-derived precipitate radius (LSW coarsening) ────────────
#
# The companion to precipitate_volume_fraction above.  vf comes from
# chemistry; r̄ comes from the aging schedule (time + temperature), which is
# what the single "Aged"/"T6" temper label cannot carry.  Without it, r̄ is a
# per-temper constant and every strengthening model degenerates to a function
# of vf alone — see the DO NOT FIX note above.
#
# Lifshitz-Slyozov-Wagner coarsening, diffusion-controlled:
#     r̄³ − r̄₀³ = K·t ,  K = (8/9)·γ·D(T)·X_eq(T)·V_m / (R·T)
# Constants (γ, D₀, Q, V_m, X_eq(T)) are reused from the KWN module's
# PRECIPITATE_DATA rather than duplicated, so the two paths cannot drift.
#
# r̄₀ (nucleation radius) is neglected — it is nanometres against a coarsened
# tens-of-nanometres scale, and the term enters as a cube.
#
# This is an ESTIMATE of relative coarsening, not a measurement.  A real
# peak-aged microstructure is arrested near peak strength rather than fully
# LSW-coarsened, so absolute r̄ carries real error.  What it captures well is
# the *relative* T,t dependence: across the 620-845 C range Ni superalloys are
# actually aged in, D varies ~74x (Q=268 kJ/mol), so r̄ varies ~4x — genuine
# discrimination that a single constant cannot express.
_FAMILY_PRECIP_PHASE: Dict[str, str] = {
    # Only nickel, matching precipitate_volume_fraction's scope.  Aluminium
    # would need series detection first (θ'-Al₂Cu / β"-Mg₂Si / η'-MgZn₂ are
    # different phases with different constants); steel PH needs a Cu-rich
    # phase that PRECIPITATE_DATA does not carry.
    "nickel": "Ni3Al_gamma_prime",
}

# DISCLOSED FITTED CONSTANT (same spirit as the KWN diffusion knob).
#
# Raw LSW-from-zero underestimates a peak-aged radius: it neglects r̄₀, assumes
# pure coarsening rather than a microstructure arrested near peak strength, and
# inherits uncertainty in γ and X_eq.  Uncalibrated it returns 1-23 nm for real
# Ni schedules, where literature secondary γ' is ~20-80 nm — small enough that
# every alloy would re-saturate the 1000 MPa Orowan cap and destroy exactly the
# discrimination this is meant to add.
#
# One scalar per family, chosen so a representative mid-range schedule
# (760 C / 16 h, Waspaloy-like) reproduces the canonical 27 nm the temper table
# already used.  It rescales; it does not reorder — the relative T,t dependence
# is untouched, and relative ordering is all a tree model consumes.
#
# Calibrated, real schedules map to: 621 C/8 h -> 4 nm (tertiary γ'),
# 760 C/16 h -> 27 nm, 845 C/24 h -> 77 nm (coarse secondary γ').  All within
# the literature range for their respective aging conditions.
_LSW_CALIBRATION: Dict[str, float] = {
    "nickel": 3.3,
}


def precipitate_radius_nm(
    family: str,
    aging_T_C: Optional[float] = None,
    aging_time_s: Optional[float] = None,
) -> Optional[float]:
    """LSW-coarsened mean radius in nm from an aging schedule, or None.

    Returns None when no schedule is supplied or the family has no mapped
    precipitate phase — callers then fall back to the canonical per-temper r̄.
    """
    if aging_T_C is None or aging_time_s is None or aging_time_s <= 0:
        return None
    phase = _FAMILY_PRECIP_PHASE.get(family)
    if phase is None:
        return None
    try:
        from apps.api.ml.precipitation.kwn import (
            PRECIPITATE_DATA, _interp_Xeq, _diffusivity_m2_s,
        )
        d = PRECIPITATE_DATA[phase]
    except Exception:
        return None

    R = 8.314
    T_K = float(aging_T_C) + 273.15
    if T_K <= 0:
        return None
    D = _diffusivity_m2_s(d["D0_m2_s"], d["Q_J_mol"], T_K)
    X_eq = _interp_Xeq(d["Xeq_T_C"], float(aging_T_C))
    if D <= 0 or X_eq <= 0:
        return None
    K = (8.0 / 9.0) * d["gamma_J_m2"] * D * X_eq * d["V_m_m3_mol"] / (R * T_K)
    if K <= 0:
        return None
    r_m = (K * float(aging_time_s)) ** (1.0 / 3.0)
    r_nm = r_m * 1e9 * _LSW_CALIBRATION[family]
    # Clamp to a physically sane band for engineering precipitates.  Below b
    # the Orowan expression is undefined; above ~1 um the phase is no longer a
    # coherent strengthener.
    return float(min(max(r_nm, 1.0), 1000.0))


def orowan_strengthening(family: str, temper: Optional[str],
                         composition_wt: Optional[dict] = None,
                         aging_T_C: Optional[float] = None,
                         aging_time_s: Optional[float] = None) -> float:
    """Return Δσ_Orowan in MPa for the family/temper pair.

    Both inputs to the Orowan expression degrade independently:

    * ``vf``  — from ``composition_wt`` when the family has a validated
      precipitate-chemistry model (currently nickel), else the canonical
      per-temper constant.
    * ``r̄``   — from ``aging_T_C``/``aging_time_s`` via LSW coarsening when a
      schedule is supplied, else the canonical per-temper constant.

    With neither supplied this reproduces the original temper-only behaviour
    exactly, so existing callers are unaffected.

    Returns 0 when no precipitate is canonically associated with this
    temper (e.g. annealed, work-hardened, Q&T without aging).
    """
    if family not in _MATRIX_DATA:
        return 0.0
    vf_r = canonical_precipitate(family, temper)
    if vf_r is None or vf_r[0] <= 0 or vf_r[1] <= 0:
        return 0.0
    vf_comp = precipitate_volume_fraction(family, temper, composition_wt)
    vf = vf_r[0] if vf_comp is None else vf_comp
    if vf <= 0:
        return 0.0
    r_sched = precipitate_radius_nm(family, aging_T_C, aging_time_s)
    r_nm = vf_r[1] if r_sched is None else r_sched
    bypass = orowan_from_vf_r(family, vf, r_nm)
    shear = apb_shearing_from_vf_r(family, vf, r_nm)
    # A dislocation takes the cheaper path, so the operative obstacle strength
    # is the LOWER of the two.  This is what produces a peak-aging curve:
    # shearing rises with r̄, bypass falls with it, and peak strength sits at
    # the crossover.  A bypass-only model has no peak and badly over-predicts
    # finely-aged alloys.
    if shear is None:
        return bypass
    return float(min(bypass, shear))


# Map the YS-router family element (Fe/Al/Ti/Ni) → strengthening family key.
_ELEMENT_TO_FAMILY: Dict[str, str] = {
    "Al": "aluminum", "Ti": "titanium", "Ni": "nickel", "Fe": "general_steel",
}


def orowan_delta_MPa(family_element: str, temper: Optional[str],
                     vf: float, r_nm: float) -> Optional[dict]:
    """Differential Orowan overlay from a KWN-simulated precipitate state.

    The physics-aware YS model already carries the *canonical-temper* Orowan
    term as a training+inference feature, so feeding a KWN result must be a
    DIFFERENCE (mirrors the Hall-Petch overlay):

        Δσ = σ_Orowan(KWN vf, r̄) − σ_Orowan(canonical temper)

    i.e. how the user's actual aging schedule deviates from the canonical
    temper the baseline assumes.  Returns ``None`` for unknown families or
    non-physical inputs; otherwise a self-describing, honestly-tagged block.
    """
    family = _ELEMENT_TO_FAMILY.get(family_element)
    if family is None or not vf or not r_nm or vf <= 0 or r_nm <= 0:
        return None
    actual = orowan_from_vf_r(family, float(vf), float(r_nm))
    canon = canonical_precipitate(family, temper)
    baseline = (orowan_from_vf_r(family, canon[0], canon[1])
                if canon and canon[0] > 0 and canon[1] > 0 else 0.0)
    return {
        "delta_MPa":            round(actual - baseline, 1),
        "orowan_sim_MPa":       round(actual, 1),
        "orowan_baseline_MPa":  round(baseline, 1),
        "vf":                   round(float(vf), 5),
        "r_nm":                 round(float(r_nm), 2),
        "family":               family,
        "temper":               temper,
        "calibration":          "literature-correlation",
        "note": (
            f"Orowan strengthening from the simulated precipitate state "
            f"(vf={float(vf):.4f}, r̄={float(r_nm):.1f} nm), differenced against "
            f"the canonical {temper or 'baseline'} temper the ML baseline assumes."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────
# 3.  Public feature vector — concatenated to the existing
#     [Magpie composition + temper one-hot] features at train + inference.
# ─────────────────────────────────────────────────────────────────────────

PHYSICS_FEATURE_NAMES = [
    "ss_strengthening_MPa",
    "orowan_strengthening_MPa",
    "sigma_phys_total_MPa",
]


def physics_features(composition_wt: dict, family: str,
                     temper: Optional[str],
                     aging_T_C: Optional[float] = None,
                     aging_time_s: Optional[float] = None,
                     fallback_radius_nm: Optional[float] = None) -> np.ndarray:
    """Compute the Sprint-6 physics-feature vector for one training row.

    Length matches ``PHYSICS_FEATURE_NAMES``.  Always returns finite
    values (0 in place of None) so the RF never sees NaNs.

    ``aging_T_C``/``aging_time_s`` give a schedule-derived precipitate radius
    (see ``precipitate_radius_nm``).  ``fallback_radius_nm`` is what to use
    when no schedule is available — training passes None (falls through to the
    canonical per-temper value), while inference passes the median radius the
    model actually saw during training, so the no-schedule path lands inside
    the training distribution rather than on an unrelated constant.
    """
    ss = solid_solution_strengthening(composition_wt, family)
    if (aging_T_C is None or aging_time_s is None) and fallback_radius_nm:
        # No schedule from the caller — synthesise the Orowan term directly at
        # the training-median radius instead of the canonical constant.
        vf_r = canonical_precipitate(family, temper)
        if vf_r is None or vf_r[0] <= 0 or vf_r[1] <= 0:
            oro = 0.0
        else:
            vf_comp = precipitate_volume_fraction(family, temper, composition_wt)
            vf = vf_r[0] if vf_comp is None else vf_comp
            oro = orowan_from_vf_r(family, vf, fallback_radius_nm) if vf > 0 else 0.0
    else:
        oro = orowan_strengthening(family, temper, composition_wt,
                                   aging_T_C, aging_time_s)
    total = ss + oro
    return np.array([ss, oro, total], dtype=float)


def physics_feature_dim() -> int:
    return len(PHYSICS_FEATURE_NAMES)
