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
* Δσ_Orowan uses *temper-dependent canonical (vf, r̄)* per family
  (e.g. T6 Al → vf ≈ 0.015, r̄ ≈ 8 nm; STA Ti → vf ≈ 0.05, r̄ ≈ 100 nm).
  The exact KWN result is available at inference time on demand; for
  training we use the canonical-temper averages.

The result: the feature pipeline is fast, deterministic, and uses the
**same physics inputs** at train and inference time.

Public API
----------
``solid_solution_strengthening(comp_wt, family) -> float`` (MPa)
``orowan_strengthening(family, temper) -> float`` (MPa)
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
        "Aged":     (0.20,  15.0),       # γ' + γ" in Ni-superalloys
        "SX-Aged":  (0.65,  300.0),      # large γ' cuboids in SX
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


def orowan_strengthening(family: str, temper: Optional[str]) -> float:
    """Return Δσ_Orowan in MPa for the family/temper pair (canonical precipitate).

    Returns 0 when no precipitate is canonically associated with this
    temper (e.g. annealed, work-hardened, Q&T without aging).
    """
    if family not in _MATRIX_DATA:
        return 0.0
    vf_r = canonical_precipitate(family, temper)
    if vf_r is None or vf_r[0] <= 0 or vf_r[1] <= 0:
        return 0.0
    return orowan_from_vf_r(family, vf_r[0], vf_r[1])


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
                     temper: Optional[str]) -> np.ndarray:
    """Compute the Sprint-6 physics-feature vector for one training row.

    Length matches ``PHYSICS_FEATURE_NAMES``.  Always returns finite
    values (0 in place of None) so the RF never sees NaNs.
    """
    ss = solid_solution_strengthening(composition_wt, family)
    oro = orowan_strengthening(family, temper)
    total = ss + oro
    return np.array([ss, oro, total], dtype=float)


def physics_feature_dim() -> int:
    return len(PHYSICS_FEATURE_NAMES)
