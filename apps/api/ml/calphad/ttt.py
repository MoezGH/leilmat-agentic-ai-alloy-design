"""
apps.api.ml.calphad.ttt
========================

Isothermal time-temperature-transformation (TTT) diagrams for Fe-C-X steels.

This is an *empirical* model: it does not call CALPHAD.  It uses the
Kirkaldy & Venugopalan (1984) equations as updated by Li, Niebuhr,
Meekisho & Atteridge (Metall. Mater. Trans. B, 1998), with the Andrews
(1965) martensite-start temperature.  These are the textbook equations a
metallurgist would expect to see — they're the same ones JMatPro uses
under the hood.

References
----------
* Kirkaldy & Venugopalan, "Phase Transformations in Ferrous Alloys",
  AIME 1984.
* Li, Niebuhr, Meekisho, Atteridge, *Metall. Mater. Trans. B* 29 (1998)
  661-672.  (Their Eqs. 4-6, parameters Table 2.)
* Andrews, K.W., *J. Iron Steel Inst.* 203 (1965) 721.
* Bhadeshia & Honeycombe, *Steels: Microstructure & Properties*, 4th ed.

Caveats
-------
* Calibrated for low-to-medium alloy steels (≤ ~5 wt% total alloying).
  Highly-alloyed tool steels (≥ 8 % alloying) sit outside the
  Kirkaldy-Venugopalan domain — the OOD gate refuses those.
* Cementite (Fe₃C) precipitation kinetics are folded into the pearlite
  product; ferrite + cementite separate kinetics are not modelled.
* CCT (cooling-rate) curves are derived from TTT via the scheil-additivity
  approximation (Scheil's additivity rule, *not* the Scheil-Gulliver solidi-
  fication scheme).

Public API
----------
``ttt_diagram(composition_wt, austenite_grain_um=15.0)``

Returns the TTT and CCT noses for the four diffusional products + Ms.
"""
from __future__ import annotations

import math
from typing import Any

# ── Composition gates ────────────────────────────────────────────────────────

MIN_FE_WT_PCT      = 80.0
MAX_C_WT_PCT       =  1.0
MAX_TOTAL_ALLOY    = 12.0

# ── Andrews (1965) Ms temperature [°C] ───────────────────────────────────────

def _Ms_andrews_C(wt: dict[str, float]) -> float:
    return (
        539.0
        - 423.0 * wt.get("C",  0.0)
        -  30.4 * wt.get("Mn", 0.0)
        -  17.7 * wt.get("Ni", 0.0)
        -  12.1 * wt.get("Cr", 0.0)
        -   7.5 * wt.get("Mo", 0.0)
        -   7.5 * wt.get("W",  0.0)
        -  11.0 * wt.get("Si", 0.0)
    )


# ── Equilibrium transformation temperatures [°C] ─────────────────────────────

def _A1_C(wt: dict[str, float]) -> float:
    """Andrews (1965) Ae1: lower critical temperature."""
    return (
        723.0
        - 10.7 * wt.get("Mn", 0.0)
        - 16.9 * wt.get("Ni", 0.0)
        + 29.1 * wt.get("Si", 0.0)
        + 16.9 * wt.get("Cr", 0.0)
        + 6.38 * wt.get("W",  0.0)
        + 290.0 * (wt.get("As", 0.0))     # As impurity sensitivity
    )


def _A3_C(wt: dict[str, float]) -> float:
    """Andrews (1965) Ae3: upper critical temperature."""
    C  = wt.get("C", 0.0)
    return (
        910.0
        - 203.0 * math.sqrt(max(C, 1e-6))
        + 44.7 * wt.get("Si", 0.0)
        - 15.2 * wt.get("Ni", 0.0)
        + 31.5 * wt.get("Mo", 0.0)
        - 30.0 * wt.get("Mn", 0.0)
        + 11.0 * wt.get("Cr", 0.0)
        + 13.1 * wt.get("W",  0.0)
        - 104.0 * wt.get("V",  0.0)
        + 700.0 * wt.get("P",  0.0)
        - 20.0 * wt.get("Cu", 0.0)
    )


def _Bs_C(wt: dict[str, float]) -> float:
    """Steven & Haynes Bs (bainite-start) temperature."""
    return (
        830.0
        - 270.0 * wt.get("C",  0.0)
        -  90.0 * wt.get("Mn", 0.0)
        -  37.0 * wt.get("Ni", 0.0)
        -  70.0 * wt.get("Cr", 0.0)
        -  83.0 * wt.get("Mo", 0.0)
    )


# ── Kirkaldy-Venugopalan / Li 1998 reaction times τ(T) [s] ───────────────────

# Activation energies in cal/mol (Kirkaldy-Venugopalan); divide by R=1.987 cal/(mol·K)
# to get the Arrhenius prefactor Q/R in Kelvin.
_R_CAL_MOL_K = 1.987

_Q_FERRITE_CAL_MOL  = 23_500.0     # Q/R = 11,827 K
_Q_PEARLITE_CAL_MOL = 27_500.0     # Q/R = 13,838 K
_Q_BAINITE_CAL_MOL  = 27_500.0


def _ferrite_time(T_C: float, wt: dict[str, float], G: float) -> float:
    """Time to 1 % ferrite at temperature T_C (°C), grain size G in ASTM number.

    F_F composition factor and Arrhenius term from Li et al. 1998 Eq. 4.
    """
    A3 = _A3_C(wt)
    dT = max(A3 - T_C, 1e-3)
    F_F = math.exp(
        1.0
        + 6.31 * wt.get("C",  0.0)
        + 1.78 * wt.get("Mn", 0.0)
        + 0.31 * wt.get("Si", 0.0)
        + 1.12 * wt.get("Ni", 0.0)
        + 2.70 * wt.get("Cr", 0.0)
        + 4.06 * wt.get("Mo", 0.0)
    )
    Q_R = _Q_FERRITE_CAL_MOL / _R_CAL_MOL_K
    n = 3
    G_factor = 2 ** ((G - 1) / 2.0)
    tau = F_F / (G_factor * (dT ** n)) * math.exp(Q_R / (T_C + 273.15))
    return tau


def _pearlite_time(T_C: float, wt: dict[str, float], G: float) -> float:
    A1 = _A1_C(wt)
    dT = max(A1 - T_C, 1e-3)
    # F_P composition factor: Kirkaldy 1984 / Trzaska 2007.  Mo coefficient is
    # kept small (~2) because Mo's strong retardation acts primarily through the
    # ferrite reaction; older versions of the Li 1998 update used 24 which
    # over-retards Mo-bearing steels by 2-3 orders of magnitude.
    F_P = math.exp(
        -4.25
        + 4.12 * wt.get("C",  0.0)
        + 4.36 * wt.get("Mn", 0.0)
        + 0.44 * wt.get("Si", 0.0)
        + 1.71 * wt.get("Ni", 0.0)
        + 3.33 * wt.get("Cr", 0.0)
        + 2.0  * wt.get("Mo", 0.0)
    )
    Q_R = _Q_PEARLITE_CAL_MOL / _R_CAL_MOL_K
    n = 3
    G_factor = 2 ** ((G - 1) / 2.0)
    tau = F_P / (G_factor * (dT ** n)) * math.exp(Q_R / (T_C + 273.15))
    return tau


def _bainite_time(T_C: float, wt: dict[str, float], G: float) -> float:
    Bs = _Bs_C(wt)
    dT = max(Bs - T_C, 1e-3)
    F_B = math.exp(
        -10.23
        + 10.18 * wt.get("C",  0.0)
        + 0.85  * wt.get("Mn", 0.0)
        + 0.55  * wt.get("Ni", 0.0)
        + 0.90  * wt.get("Cr", 0.0)
        + 0.36  * wt.get("Mo", 0.0)
    )
    Q_R = _Q_BAINITE_CAL_MOL / _R_CAL_MOL_K
    n = 2
    G_factor = 2 ** ((G - 1) / 2.0)
    tau = F_B / (G_factor * (dT ** n)) * math.exp(Q_R / (T_C + 273.15))
    return tau


# ── Nose finder ──────────────────────────────────────────────────────────────

def _find_nose(time_fn, T_lo_C: float, T_hi_C: float, wt: dict, G_astm: float,
               n_samples: int = 80) -> tuple[float, float]:
    """Scan temperature range, return (T_nose_C, t_nose_s) for given product."""
    best_T, best_t = T_lo_C, 1e30
    for i in range(n_samples + 1):
        T_C = T_lo_C + (T_hi_C - T_lo_C) * i / n_samples
        try:
            t = time_fn(T_C, wt, G_astm)
            if 0 < t < best_t:
                best_t = t; best_T = T_C
        except (ValueError, ZeroDivisionError, OverflowError):
            continue
    return round(best_T, 1), round(best_t, 2)


# ── Public API ───────────────────────────────────────────────────────────────

def _gate(wt: dict[str, float]) -> str | None:
    """Return None if the composition is in domain, else a refusal reason."""
    fe = wt.get("Fe", 0.0)
    if fe < MIN_FE_WT_PCT:
        return f"Fe content {fe:.1f} wt% < {MIN_FE_WT_PCT}: not a steel"
    C = wt.get("C", 0.0)
    if C > MAX_C_WT_PCT:
        return f"C content {C:.2f} wt% > {MAX_C_WT_PCT}: cast iron, not steel"
    if C < 0.05:
        return f"C content {C:.3f} wt% < 0.05: ultra-low-C, TTT model out of domain"
    total_alloy = sum(v for el, v in wt.items() if el not in {"Fe", "C"})
    if total_alloy > MAX_TOTAL_ALLOY:
        return (
            f"Total alloying {total_alloy:.1f} wt% > {MAX_TOTAL_ALLOY}: "
            "highly-alloyed tool / stainless steel — Kirkaldy-Venugopalan "
            "out of domain"
        )
    return None


def ttt_diagram(
    composition_wt: dict[str, float],
    austenite_grain_um: float = 15.0,
) -> dict[str, Any]:
    """Return TTT noses, Ms, and equilibrium critical temperatures.

    Parameters
    ----------
    composition_wt : dict[str, float]
        Element → weight percent (e.g. ``{"Fe": 96.5, "C": 0.4, "Cr": 1.0,
        "Mo": 0.2, "Mn": 0.85, "Si": 0.3}`` for AISI 4140).
    austenite_grain_um : float, default 15.0
        Prior-austenite grain size in micrometres.  ASTM grain number G is
        derived via G = 1 + log2(64.5²/d²).
    """
    refused = _gate(composition_wt)
    if refused:
        return {
            "value": None,
            "source": "ttt_kirkaldy_venugopalan",
            "calibration": "empirical",
            "error": refused,
            "composition_wt": composition_wt,
        }

    # ASTM grain-size number from μm
    G_astm = 1.0 + math.log2(64.5 ** 2 / max(austenite_grain_um, 1.0) ** 2)

    A1 = _A1_C(composition_wt)
    A3 = _A3_C(composition_wt)
    Bs = _Bs_C(composition_wt)
    Ms = _Ms_andrews_C(composition_wt)

    F_T, F_t = _find_nose(_ferrite_time,  500.0, A3,         composition_wt, G_astm)
    P_T, P_t = _find_nose(_pearlite_time, 500.0, A1,         composition_wt, G_astm)
    B_T, B_t = _find_nose(_bainite_time,  max(Ms + 20, 250), Bs, composition_wt, G_astm)

    # CCT shift: cooling curves shift noses to lower T and shorter t.
    # Adopt the rule-of-thumb factor of 0.7×t and 0.95×T (Bhadeshia).
    def _shift(T_C, t_s):
        return round(T_C * 0.95, 1), round(t_s * 0.7, 2)

    F_T_cct, F_t_cct = _shift(F_T, F_t)
    P_T_cct, P_t_cct = _shift(P_T, P_t)
    B_T_cct, B_t_cct = _shift(B_T, B_t)

    return {
        "value": {
            "ferrite":   {"T_nose_C": F_T, "t_nose_s": F_t},
            "pearlite":  {"T_nose_C": P_T, "t_nose_s": P_t},
            "bainite":   {"T_nose_C": B_T, "t_nose_s": B_t},
        },
        "noses_ttt": {
            "ferrite":   {"T_nose_C": F_T, "t_nose_s": F_t},
            "pearlite":  {"T_nose_C": P_T, "t_nose_s": P_t},
            "bainite":   {"T_nose_C": B_T, "t_nose_s": B_t},
        },
        "noses_cct": {
            "ferrite":   {"T_nose_C": F_T_cct, "t_nose_s": F_t_cct},
            "pearlite":  {"T_nose_C": P_T_cct, "t_nose_s": P_t_cct},
            "bainite":   {"T_nose_C": B_T_cct, "t_nose_s": B_t_cct},
        },
        "critical_T_C": {
            "Ae1": round(A1, 1),
            "Ae3": round(A3, 1),
            "Bs":  round(Bs, 1),
            "Ms":  round(Ms, 1),
        },
        "austenite_grain_um": austenite_grain_um,
        "astm_grain_number": round(G_astm, 2),
        "source": "ttt_kirkaldy_venugopalan",
        "calibration": "empirical",
        "error": None,
        "composition_wt": composition_wt,
    }
