"""
Secondary mechanical & environmental properties:

  • Hardness (HV) — Tabor's rule HV ≈ 3 σ_y with per-family correction factors
    calibrated against canonical alloys (6061-T6, Ti-6-4, Inconel 718, 304SS).

  • Fatigue endurance limit (σ_e, MPa) — empirical σ_e/σ_UTS ratio per family
    (Basquin / S-N curve asymptote, where defined; otherwise the 10⁷-cycle
    fatigue strength). Returns null for high-cycle-fatigue-undefined families
    (Al has no true endurance limit — we report the 10⁷-cycle value with a note).

  • Corrosion resistance — for Fe-base alloys uses the industry-standard Pitting
    Resistance Equivalent Number (PREN = Cr + 3.3 Mo + 16 N, wt%).  For Ti-base
    alloys uses a passive-film quality rule; all other families use the original
    element-contribution scoring.

  • Phase stability warnings — deterministic composition-rule checks for known
    embrittlement and phase-instability risks (Ti₃Al, sensitization, σ-phase,
    γ′ over-saturation, Mg galvanic contamination).

References:
- Tabor, "The Hardness of Metals," Oxford (1951)
- Bannantine, Comer, Handrock, "Fundamentals of Metal Fatigue Analysis," Prentice Hall (1990)
- Sedriks, "Corrosion of Stainless Steels," Wiley (1996) — PREN formula
- Davis (ed.), "Corrosion: Understanding the Basics," ASM International (2000)
- ASM Handbook vol. 2: Properties and Selection of Nonferrous Alloys
"""
from __future__ import annotations

from typing import Any

from pymatgen.core import Element


# ─────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────

def _primary_element(composition: dict[str, float]) -> str | None:
    return max(composition, key=composition.get) if composition else None


def _family_key(composition: dict[str, float]) -> str | None:
    """Match composition to a family key by majority-element threshold."""
    total = sum(composition.values())
    if total <= 0:
        return None
    fracs = {el: v / total for el, v in composition.items()}
    for el, threshold in [("Fe", 0.50), ("Al", 0.80), ("Ti", 0.50), ("Ni", 0.40), ("Cu", 0.50), ("Mg", 0.50)]:
        if fracs.get(el, 0) >= threshold:
            return el
    return _primary_element(composition)


def _at_frac_to_wt_pct(fracs: dict[str, float]) -> dict[str, float]:
    """Convert atomic fractions (sum = 1) → weight percent (sum = 100)."""
    masses: dict[str, float] = {}
    for el_sym, x in fracs.items():
        try:
            masses[el_sym] = x * float(Element(el_sym).atomic_mass)
        except Exception:
            masses[el_sym] = 0.0
    total = sum(masses.values())
    if total <= 0:
        return {}
    return {el: m / total * 100.0 for el, m in masses.items()}


# ─────────────────────────────────────────────────────────────────────────
# Hardness (Vickers, HV)
# ─────────────────────────────────────────────────────────────────────────

HV_FAMILY_RATIOS = {
    "Fe": {"k": 1.00, "label": "steels"},
    "Al": {"k": 1.10, "label": "Al alloys"},
    "Ti": {"k": 1.35, "label": "Ti alloys"},
    "Ni": {"k": 1.10, "label": "Ni superalloys"},
    "Cu": {"k": 1.00, "label": "Cu alloys"},
    "Mg": {"k": 1.00, "label": "Mg alloys"},
}


def hardness_HV(composition: dict[str, float], yield_strength_MPa_value: float | None) -> dict[str, Any]:
    """
    Vickers hardness via Tabor's rule with per-family calibration.
    HV ≈ k · 3 · σ_y / 9.81   (σ_y in MPa, HV in kgf/mm²)
    """
    if yield_strength_MPa_value is None:
        return {
            "value": None,
            "source": "tabor_rule",
            "error": "Requires yield strength — no family model for this composition",
        }

    family = _family_key(composition)
    bundle = HV_FAMILY_RATIOS.get(family, {"k": 1.0, "label": "generic"})
    k = bundle["k"]
    hv = k * 3.0 * yield_strength_MPa_value / 9.81
    uncertainty = max(15.0, hv * 0.20)
    return {
        "value": round(hv, 0),
        "uncertainty": round(uncertainty, 0),
        "source": "tabor_rule",
        "family": bundle["label"],
        "yield_strength_used_MPa": round(yield_strength_MPa_value, 0),
    }


# ─────────────────────────────────────────────────────────────────────────
# Fatigue endurance / 10⁷-cycle fatigue strength
# ─────────────────────────────────────────────────────────────────────────

FATIGUE_FAMILY_RATIOS = {
    "Fe": {"ratio": 0.50, "label": "steels — true endurance limit"},
    "Al": {"ratio": 0.40, "label": "Al alloys — 10⁷-cycle (no true limit)"},
    "Ti": {"ratio": 0.55, "label": "Ti alloys — strong endurance limit"},
    "Ni": {"ratio": 0.40, "label": "Ni superalloys — at room temp"},
    "Cu": {"ratio": 0.35, "label": "Cu alloys"},
    "Mg": {"ratio": 0.35, "label": "Mg alloys"},
}


def fatigue_endurance_MPa(composition: dict[str, float], yield_strength_MPa_value: float | None) -> dict[str, Any]:
    """
    Estimate endurance limit (or 10⁷-cycle fatigue strength) via empirical
    σ_e / σ_UTS family ratio. σ_UTS ≈ 1.15 σ_y.

    Note: Fatigue is highly sensitive to surface finish and residual stress
    (±30% typical). Use the uncertainty band accordingly.
    """
    if yield_strength_MPa_value is None:
        return {
            "value": None,
            "source": "empirical_ratio_UTS",
            "error": "Requires yield strength — no family model for this composition",
        }

    family = _family_key(composition)
    bundle = FATIGUE_FAMILY_RATIOS.get(family, {"ratio": 0.40, "label": "generic estimate"})
    ratio = bundle["ratio"]
    uts = 1.15 * yield_strength_MPa_value
    se = ratio * uts
    return {
        "value": round(se, 0),
        "uncertainty": round(se * 0.30, 0),
        "source": "empirical_ratio_UTS",
        "ratio_used": ratio,
        "family": bundle["label"],
        "estimated_UTS_MPa": round(uts, 0),
    }


# ─────────────────────────────────────────────────────────────────────────
# Corrosion resistance
# ─────────────────────────────────────────────────────────────────────────

# Element contributions for non-Fe / non-Ti families (neutral aerated water, 25°C).
CORROSION_CONTRIBUTIONS_PER_AT_PCT = {
    "Cr": 4.5,
    "Mo": 5.0,
    "Ni": 1.5,
    "Ti": 4.0,
    "Al": 3.5,
    "Mg": -2.0,
    "Zn": -0.5,
    "Cu": -1.5,
    "Fe":  0.0,
    "Mn": -0.5,
    "Si":  0.3,
    "Pb": -1.0,
    "C":  -1.0,
    "W":   2.0,
    "Nb":  0.5,
    "Ta":  3.0,
}


def _corrosion_score_raw(composition: dict[str, float]) -> tuple[float, dict[str, float]]:
    total = sum(composition.values())
    if total <= 0:
        return 0.0, {}
    contributions: dict[str, float] = {}
    score = 0.0
    for el, v in composition.items():
        coeff = CORROSION_CONTRIBUTIONS_PER_AT_PCT.get(el, 0.0)
        at_pct = (v / total) * 100
        contribution = coeff * at_pct
        if abs(contribution) > 0.1:
            contributions[el] = round(contribution, 1)
        score += contribution
    return score, contributions


def _pren_score(fracs: dict[str, float]) -> dict[str, Any]:
    """
    Pitting Resistance Equivalent Number for Fe-base alloys.

    PREN = Cr_wt + 3.3 · Mo_wt + 16 · N_wt  (Sedriks 1996, wt%)

    Thresholds (pitting in chloride environments):
      PREN ≥ 40 → Excellent  (super duplex / super austenitic)
      PREN ≥ 25 → Good       (316L ≈ 25, duplex 2205 ≈ 35)
      PREN ≥ 13 → Fair       (430 ferritic ≈ 17, 410 martensitic ≈ 12)
      PREN  < 13 → Poor      (plain / low-alloy steels)
    """
    wt = _at_frac_to_wt_pct(fracs)
    cr_wt = wt.get("Cr", 0.0)
    mo_wt = wt.get("Mo", 0.0)
    n_wt  = wt.get("N",  0.0)
    pren  = cr_wt + 3.3 * mo_wt + 16.0 * n_wt

    if pren >= 40:
        rating, rate, rate_value = "Excellent", "< 0.025 mm/yr", 0.01
    elif pren >= 25:
        rating, rate, rate_value = "Good",      "0.025–0.1 mm/yr", 0.05
    elif pren >= 13:
        rating, rate, rate_value = "Fair",      "0.1–0.5 mm/yr", 0.2
    else:
        rating, rate, rate_value = "Poor",      "> 0.5 mm/yr", 1.0

    drivers_pos = [{"element": el, "contribution": round(v, 1)}
                   for el, v in [("Cr", cr_wt), ("Mo", mo_wt * 3.3), ("N", n_wt * 16.0)]
                   if v > 0.1]
    drivers_neg: list[dict] = []

    return {
        "value":               round(pren, 1),
        "rating":              rating,
        "rate_general_mm_per_year": rate_value,
        "rate_range_text":     rate,
        "pren":                round(pren, 1),
        "drivers_positive":    drivers_pos,
        "drivers_negative":    drivers_neg,
        "source":              "pren_steels",
        "note":                f"PREN = Cr + 3.3·Mo + 16·N = {pren:.1f} (Sedriks 1996). "
                               "Chloride pitting resistance; acid / crevice conditions differ.",
    }


def _ti_corrosion(fracs: dict[str, float]) -> dict[str, Any]:
    """
    Ti-base corrosion: TiO₂ passive film gives excellent baseline.
    Penalty only for deliberate Fe, Cu, or Ni additions that disrupt passivity.
    """
    fe_at  = fracs.get("Fe", 0) * 100
    cu_at  = fracs.get("Cu", 0) * 100
    ni_at  = fracs.get("Ni", 0) * 100
    penalty = fe_at * 0.5 + cu_at * 1.0 + ni_at * 1.5

    if penalty < 1.5:
        rating, rate, rate_value = "Excellent", "< 0.025 mm/yr", 0.01
    elif penalty < 4.0:
        rating, rate, rate_value = "Good",      "0.025–0.1 mm/yr", 0.05
    else:
        rating, rate, rate_value = "Fair",      "0.1–0.5 mm/yr", 0.2

    drivers_neg = [{"element": el, "contribution": round(-v * c, 1)}
                   for el, v, c in [("Fe", fe_at, 0.5), ("Cu", cu_at, 1.0), ("Ni", ni_at, 1.5)]
                   if v > 0]
    return {
        "value":               round(100.0 - penalty * 5, 0),   # pseudo-score for inverse design
        "rating":              rating,
        "rate_general_mm_per_year": rate_value,
        "rate_range_text":     rate,
        "drivers_positive":    [{"element": "Ti", "contribution": 100.0}],
        "drivers_negative":    drivers_neg,
        "source":              "passive_film_rules",
        "note":                "TiO₂ passive film; highly resistant in oxidising and neutral media. "
                               "Penalties for Fe/Cu/Ni additions that reduce film stability.",
    }


def corrosion_resistance(composition: dict[str, float]) -> dict[str, Any]:
    """
    Corrosion resistance, routed by alloy family:

    Fe-base (Fe ≥ 50%) → PREN = Cr + 3.3·Mo + 16·N (Sedriks 1996, wt%)
    Ti-base (Ti ≥ 50%) → TiO₂ passive-film quality rule
    Other families      → element-contribution scoring (neutral aerated water)
    """
    total = sum(composition.values())
    if total <= 0:
        return {"value": None, "source": "electrochemistry_rules", "error": "empty composition"}

    fracs = {el: v / total for el, v in composition.items()}

    if fracs.get("Fe", 0) >= 0.50:
        return _pren_score(fracs)

    if fracs.get("Ti", 0) >= 0.50:
        return _ti_corrosion(fracs)

    # Generic element-contribution path (Ni, Al, Cu, Mg, others)
    score, contributions = _corrosion_score_raw(composition)

    if score >= 220:
        rating, rate, rate_value = "Excellent", "< 0.025 mm/yr", 0.01
    elif score >= 80:
        rating, rate, rate_value = "Good",      "0.025–0.1 mm/yr", 0.05
    elif score >= 30:
        rating, rate, rate_value = "Fair",      "0.1–0.5 mm/yr", 0.2
    else:
        rating, rate, rate_value = "Poor",      "> 0.5 mm/yr", 1.0

    sorted_pos = sorted(((k, v) for k, v in contributions.items() if v > 0), key=lambda kv: -kv[1])[:3]
    sorted_neg = sorted(((k, v) for k, v in contributions.items() if v < 0), key=lambda kv: kv[1])[:3]

    return {
        "value":               round(score, 0),
        "rating":              rating,
        "rate_general_mm_per_year": rate_value,
        "rate_range_text":     rate,
        "drivers_positive":    [{"element": el, "contribution": v} for el, v in sorted_pos],
        "drivers_negative":    [{"element": el, "contribution": v} for el, v in sorted_neg],
        "source":              "electrochemistry_rules",
        "note":                "Score for neutral-aerated water at 25°C. Marine / acid / high-T differ.",
    }


# ─────────────────────────────────────────────────────────────────────────
# Phase stability warnings (composition-rule based, no API required)
# ─────────────────────────────────────────────────────────────────────────

def phase_stability_warnings(composition: dict[str, float]) -> dict[str, Any]:
    """
    Deterministic composition-rule checks for known embrittlement and
    phase-instability risks.  Returns a list of warning dicts sorted by
    severity (critical > warning > info).

    Rules are drawn from:
    - ASM Handbook vol. 2 & 5 (Ti, Ni, Al metallurgy)
    - Sedriks, "Corrosion of Stainless Steels," Wiley (1996) — sensitization, σ-phase
    - Petch, Phil. Mag. 1953 — Hall-Petch; Embury & Nicholson 1965 — Ti₃Al
    - Mg handbook: Lunder et al. Corrosion 1989 — Fe/Ni tolerance limits
    """
    total = sum(composition.values())
    if total <= 0:
        return {"warnings": [], "source": "composition_rules", "n_warnings": 0}

    fracs = {el: v / total for el, v in composition.items()}
    wt    = _at_frac_to_wt_pct(fracs)
    warnings: list[dict[str, str]] = []

    # ── Ti-base alloys ─────────────────────────────────────────────────
    if fracs.get("Ti", 0) >= 0.50:
        al_at = fracs.get("Al", 0) * 100
        if al_at > 8:
            warnings.append({
                "level":   "critical",
                "code":    "Ti3Al_embrittlement",
                "message": f"Al {al_at:.1f} at% exceeds 8 at% limit — Ti₃Al (α₂) ordered intermetallic risk; causes severe room-temperature embrittlement",
                "element": "Al",
            })

        # Al-equivalent: Al_eq = Al + Sn/3 + Zr/6 accounts for equivalent hardening
        al_eq = al_at + fracs.get("Sn", 0) * 100 / 3 + fracs.get("Zr", 0) * 100 / 6
        if al_eq > 9 and al_at <= 8:
            warnings.append({
                "level":   "warning",
                "code":    "Al_equivalent_high",
                "message": f"Al-equivalent {al_eq:.1f} at% > 9 — α-stabiliser saturation; embrittlement risk even with Al < 8 at%",
                "element": "Al",
            })

        o_at = fracs.get("O", 0) * 100
        if o_at > 0.2:
            warnings.append({
                "level":   "warning",
                "code":    "Ti_oxygen_embrittlement",
                "message": f"O {o_at:.2f} at% — oxygen is a potent α-stabiliser in Ti; > 0.2 at% raises ductile-brittle transition significantly",
                "element": "O",
            })

    # ── Fe-base steels ─────────────────────────────────────────────────
    if fracs.get("Fe", 0) >= 0.50:
        c_wt  = wt.get("C",  0.0)
        cr_at = fracs.get("Cr", 0) * 100
        mo_at = fracs.get("Mo", 0) * 100
        si_at = fracs.get("Si", 0) * 100

        if c_wt > 0.8:
            warnings.append({
                "level":   "warning",
                "code":    "hypereutectoid_carbide",
                "message": f"C {c_wt:.2f} wt% > 0.8% — hypereutectoid steel; pro-eutectoid cementite network at prior austenite grain boundaries reduces toughness",
                "element": "C",
            })

        # Sensitization: Cr₂₃C₆ depletes Cr at grain boundaries (HAZ + aging at 500–850°C)
        if 10 <= cr_at <= 22 and c_wt > 0.03:
            warnings.append({
                "level":   "warning",
                "code":    "sensitization_risk",
                "message": f"Cr {cr_at:.1f} at% + C {c_wt:.2f} wt% — sensitization risk: M₂₃C₆ precipitation depletes Cr at grain boundaries (500–850°C range)",
                "element": "Cr",
            })

        # Sigma phase: tetragonal FeCr intermetallic, forms 600–900°C in high-Cr+Mo alloys
        if cr_at > 17 and (mo_at + si_at) > 4:
            warnings.append({
                "level":   "warning",
                "code":    "sigma_phase",
                "message": f"High Cr ({cr_at:.1f} at%) + Mo+Si {(mo_at + si_at):.1f} at% — σ-phase (FeCr intermetallic) embrittlement risk between 600–900°C",
                "element": "Cr",
            })

    # ── Ni-base superalloys ─────────────────────────────────────────────
    if fracs.get("Ni", 0) >= 0.40:
        al_ti_at = (fracs.get("Al", 0) + fracs.get("Ti", 0)) * 100

        if al_ti_at > 8:
            warnings.append({
                "level":   "info",
                "code":    "high_gamma_prime",
                "message": f"Al+Ti {al_ti_at:.1f} at% > 8% — high γ′ (Ni₃Al/Ni₃Ti) volume fraction; excellent creep strength but reduced ductility and weldability",
                "element": "Al",
            })

        if al_ti_at > 12:
            warnings.append({
                "level":   "warning",
                "code":    "gamma_prime_oversaturation",
                "message": f"Al+Ti {al_ti_at:.1f} at% > 12% — γ′ over-saturation; risk of grain boundary δ/η phase formation and stress-rupture embrittlement",
                "element": "Al",
            })

    # ── Mg-base alloys ──────────────────────────────────────────────────
    if fracs.get("Mg", 0) >= 0.50:
        if fracs.get("Fe", 0) > 0.005:
            fe_at = fracs.get("Fe", 0) * 100
            warnings.append({
                "level":   "critical",
                "code":    "Mg_Fe_galvanic",
                "message": f"Fe {fe_at:.1f} at% in Mg alloy — Fe tolerance limit is ~30 ppm wt; cathodic Fe particles cause severe micro-galvanic corrosion",
                "element": "Fe",
            })

        if fracs.get("Ni", 0) > 0.003:
            ni_at = fracs.get("Ni", 0) * 100
            warnings.append({
                "level":   "critical",
                "code":    "Mg_Ni_galvanic",
                "message": f"Ni {ni_at:.1f} at% in Mg alloy — Ni tolerance limit is ~20 ppm wt; causes severe galvanic corrosion (Lunder et al. 1989)",
                "element": "Ni",
            })

    # Sort: critical first, then warning, then info
    _level_order = {"critical": 0, "warning": 1, "info": 2}
    warnings.sort(key=lambda w: _level_order.get(w["level"], 3))

    return {
        "warnings":    warnings,
        "source":      "composition_rules",
        "n_warnings":  len(warnings),
    }
