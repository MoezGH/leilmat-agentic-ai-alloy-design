"""
Manufacturability scoring: castability, weldability, cost.

Each score is on a 0-100 scale (higher = more manufacturable) with a
factors dict explaining how the value was computed — so the UI can render
"why" and the Local AI can suggest specific composition changes.

References:
- Carbon Equivalent (IIW): Yurioka, "Welding Carbon Equivalent for Steels,"
  ISIJ International (2001).
- Al-Si castability eutectic at ~12.6% Si: ASM Handbook v.15 (Casting), 2008.
- Element spot prices: LME / USGS Mineral Commodity Summaries 2025 (approximate).
"""
from __future__ import annotations

import math
from typing import Any

# Spot prices in USD per kg (engineering-grade, approximate mid-2025).
# Premium / rare elements use representative values for materials selection.
ELEMENT_PRICE_USD_PER_KG: dict[str, float] = {
    # Base metals
    "Fe": 0.50,  "C": 1.0,   "Si": 2.5,   "Mn": 2.0,
    "Cr": 10.0,  "Ni": 20.0, "Cu": 10.0,  "Al": 2.7,
    "Mg": 3.5,   "Zn": 2.7,  "Pb": 2.0,   "Sn": 35.0,
    "Ti": 10.0,  "V": 35.0,  "Mo": 30.0,  "W": 35.0,
    "Co": 40.0,  "Nb": 50.0, "Ta": 300.0, "Zr": 25.0,
    "Be": 1000.0, "Li": 80.0,
    # Rare earths (representative)
    "Y": 30.0,  "La": 5.0,  "Ce": 5.0,   "Nd": 100.0, "Sm": 30.0,
    "Gd": 50.0, "Tb": 800.0,"Dy": 400.0, "Ho": 200.0, "Er": 100.0,
    "Tm": 5000.0,"Yb": 30.0, "Lu": 800.0,"Sc": 8000.0,
    # Precious metals
    "Au": 75000.0, "Ag": 900.0, "Pt": 35000.0, "Pd": 30000.0,
    "Rh": 200000.0,"Ru": 15000.0,"Ir": 150000.0,
    # Misc
    "B": 5.0, "P": 5.0, "S": 0.2,
}

DEFAULT_PRICE = 50.0  # fallback for elements not in the table


def _normalise(composition: dict[str, float]) -> dict[str, float]:
    s = sum(composition.values())
    if s <= 0:
        return composition
    return {el: v / s for el, v in composition.items()}


def _mass_fractions(composition: dict[str, float]) -> dict[str, float]:
    """Convert atomic% to mass fractions using pymatgen atomic masses."""
    from pymatgen.core import Element
    masses = {}
    for el, at_pct in composition.items():
        try:
            masses[el] = at_pct * Element(el).atomic_mass
        except Exception:
            continue
    tot = sum(masses.values())
    if tot <= 0:
        return {}
    return {el: m / tot for el, m in masses.items()}


def _primary(norm: dict[str, float]) -> str | None:
    if not norm:
        return None
    return max(norm, key=norm.get)


# ─────────────────────────────────────────────────────────────────────────
# Castability — fluidity, freezing range, eutectic proximity
# ─────────────────────────────────────────────────────────────────────────

def castability_score(composition: dict[str, float]) -> dict[str, Any]:
    """
    Composition-based castability index (0–100).

    Approach:
      • Base score from average melting point (lower Tm → easier to melt/pour)
      • Boost for known eutectic vicinities (Al-Si, Fe-C cast iron, Zn-Al, etc.)
      • Penalty for reactive elements (Ti, Zr at >5%) and wide-freezing-range alloys
    """
    from apps.api.ml.featurizers import magpie_mean_property

    norm = _normalise(composition)
    if not norm:
        return {"value": None, "source": "heuristic"}

    tm = magpie_mean_property(composition, "MagpieData mean MeltingT") or 1500.0
    primary = _primary(norm)

    # Base from Tm — piecewise linear
    if tm <= 800:
        base = 95.0                                  # Zn-like (Tm < 800K)
    elif tm <= 1200:
        base = 95.0 - (tm - 800) * 0.0375            # → 80 at Tm=1200
    elif tm <= 1500:
        base = 80.0 - (tm - 1200) * 0.05             # → 65 at Tm=1500
    elif tm <= 1800:
        base = 65.0 - (tm - 1500) * 0.0667           # → 45 at Tm=1800
    else:
        base = max(15.0, 45.0 - (tm - 1800) * 0.05)  # → 20 at Tm=2300

    # Element percentages
    pct = lambda el: 100 * norm.get(el, 0)
    al, si, fe, c = pct("Al"), pct("Si"), pct("Fe"), pct("C")
    ti, zr, mg, cu, zn = pct("Ti"), pct("Zr"), pct("Mg"), pct("Cu"), pct("Zn")

    # Eutectic boosts
    boosts = {}
    if primary == "Al" and 5.0 <= si <= 13.0:
        # Al-Si eutectic 12.6 at% Si — peak fluidity, narrow freezing range
        boosts["Al-Si eutectic vicinity"] = 18 - abs(si - 11.0) * 1.5
    if primary == "Fe" and 2.5 <= c <= 4.3:
        # Cast-iron range — graphite shrinkage compensation
        boosts["Fe-C cast iron"] = 15.0
    if primary == "Zn" and 3.0 <= al <= 5.0:
        # Zamak (ZA-3 / ZA-4) zinc die-casting alloys
        boosts["Zn-Al die cast"] = 12.0

    # Penalties
    penalties = {}
    if ti > 2.0:
        penalties["Ti reactive at melt"] = min(30.0, ti * 4)
    if zr > 1.0:
        penalties["Zr reactivity"] = min(20.0, zr * 6)
    if primary == "Al" and mg > 7.0:
        # High-Mg Al → oxidation, dross, hot-tearing
        penalties["high Mg dross + hot tear"] = (mg - 7) * 2
    if primary == "Al" and cu > 4.0 and si < 2.0:
        # Wide freezing range 2xxx-style → hot tearing
        penalties["Al-Cu wide freezing range"] = min(15.0, (cu - 4) * 2.5)
    if primary == "Cu" and zn > 35.0:
        # Brasses with >35% Zn lose fluidity
        penalties["high-Zn brass"] = (zn - 35) * 0.5

    boost = sum(boosts.values())
    penalty = sum(penalties.values())
    score = max(0.0, min(100.0, base + boost - penalty))

    return {
        "value": round(score, 1),
        "factors": {
            "Tm_K": round(tm, 0),
            "base": round(base, 1),
            "boosts": {k: round(v, 1) for k, v in boosts.items()},
            "penalties": {k: round(v, 1) for k, v in penalties.items()},
        },
        "source": "heuristic_eutectic_rules",
    }


# ─────────────────────────────────────────────────────────────────────────
# Weldability — Carbon Equivalent for steels, comp rules for Al / Ti
# ─────────────────────────────────────────────────────────────────────────

def weldability_score(composition: dict[str, float]) -> dict[str, Any]:
    """
    Composition-based weldability index (0–100).

    • Iron-based (Fe ≥ 50 at%): IIW Carbon Equivalent
        CE = C + Mn/6 + (Cr + Mo + V)/5 + (Ni + Cu)/15
      where percentages are *weight* fractions × 100.
        CE < 0.35 → score 100;   CE > 0.85 → score 20
    • Al-based: penalty rules for Cu (hot tear), high Mg, Zn
    • Ti-based: requires inert atmosphere → flat 35
    • Cu-based: generally good → 80, minus Zn>30 penalty
    • Other: estimated default 70
    """
    norm = _normalise(composition)
    if not norm:
        return {"value": None, "source": "heuristic"}

    primary = _primary(norm)
    mass = _mass_fractions(composition)
    mw_pct = lambda el: 100 * mass.get(el, 0)

    if mass.get("Fe", 0) >= 0.50:
        C  = mw_pct("C")
        Mn = mw_pct("Mn")
        Cr = mw_pct("Cr")
        Mo = mw_pct("Mo")
        V  = mw_pct("V")
        Ni = mw_pct("Ni")
        Cu = mw_pct("Cu")
        CE = C + Mn / 6.0 + (Cr + Mo + V) / 5.0 + (Ni + Cu) / 15.0

        if CE < 0.35:
            score = 100.0
        elif CE > 0.85:
            score = 20.0
        else:
            score = 100.0 - (CE - 0.35) * 160.0

        return {
            "value": round(score, 1),
            "factors": {
                "method": "IIW Carbon Equivalent",
                "CE": round(CE, 3),
                "C_wt": round(C, 2), "Mn_wt": round(Mn, 2),
                "Cr_wt": round(Cr, 2), "Mo_wt": round(Mo, 2),
                "Ni_wt": round(Ni, 2),
            },
            "source": "iiw_carbon_equivalent",
        }

    if mass.get("Al", 0) >= 0.50:
        cu, mg, zn = mw_pct("Cu"), mw_pct("Mg"), mw_pct("Zn")
        base = 90.0
        pens = {}
        if cu > 1.0:
            pens["Cu hot tearing"] = (cu - 1) * 6
        if mg > 5.0:
            pens["high Mg cracking"] = (mg - 5) * 4
        if zn > 3.0:
            pens["Zn liquation"] = (zn - 3) * 5
        score = max(15.0, base - sum(pens.values()))
        return {
            "value": round(score, 1),
            "factors": {"method": "Al-alloy rules", "Cu_wt": round(cu, 2), "Mg_wt": round(mg, 2), "Zn_wt": round(zn, 2), "penalties": {k: round(v, 1) for k, v in pens.items()}},
            "source": "al_alloy_rules",
        }

    if mass.get("Ti", 0) >= 0.40:
        return {
            "value": 35.0,
            "factors": {"method": "Ti needs inert atmosphere (GTAW or laser in Ar)"},
            "source": "ti_specialty",
        }

    if mass.get("Cu", 0) >= 0.50:
        zn = mw_pct("Zn")
        score = max(35.0, 80.0 - max(0, zn - 30) * 1.5)
        return {
            "value": round(score, 1),
            "factors": {"method": "Cu/brass rules", "Zn_wt": round(zn, 2)},
            "source": "cu_alloy_rules",
        }

    return {"value": 65.0, "factors": {"method": "default estimate"}, "source": "default"}


# ─────────────────────────────────────────────────────────────────────────
# Cost — mass-weighted spot prices on log scale
# ─────────────────────────────────────────────────────────────────────────

def cost_score(composition: dict[str, float],
               form: str = "plate",
               cert: str = "commercial",
               ht:   str | None = None,
               lot_kg: float    = 100.0) -> dict[str, Any]:
    """Cost score (0–100, higher = cheaper) via the Sprint-8 hierarchical
    cost model.

    Wraps :func:`apps.api.ml.cost.compute_cost` and converts the
    USD/kg value into the legacy 0–100 score used by the dashboard's
    radar plot:

        score = clamp(100 − 22·log₁₀(max(0.5, USD/kg)), 0, 100)
        ~$1/kg  → 100   (commercial structural steel)
        ~$10/kg → 78    (Al / mild Cu alloys)
        ~$100/kg→ 56    (Ti / Ni / aerospace alloys)
        ~$1000/kg→ 34   (Ta / Re / superalloys with refractory additions)

    The full hierarchical breakdown (form factor, certification, HT
    multiplier, supplier overhead) is exposed under ``factors``.
    """
    from apps.api.ml.cost import compute_cost
    out = compute_cost(composition, form=form, cert=cert, ht=ht, lot_kg=lot_kg)
    if out.get("USD_per_kg") is None:
        return {"value": None, "source": "cost_v2", "error": out.get("error")}

    cost_per_kg = out["USD_per_kg"]
    score = 100.0 - 22.0 * math.log10(max(0.5, cost_per_kg))
    score = max(0.0, min(100.0, score))

    # Surface the top 3 cost drivers for the radar tooltip
    contributions = out.get("contributions") or []
    drivers = [
        {"element": c["element"], "USD_per_kg_of_alloy": c["USD_per_kg_alloy"]}
        for c in contributions[:3]
    ]

    return {
        "value":            round(score, 1),
        "cost_per_kg_USD":  round(cost_per_kg, 2),
        "factors": {
            "form":          out["form"],
            "certification": out["certification"],
            "family":        out["family"],
            "breakdown":     out["breakdown"],
            "top_drivers":   drivers,
        },
        "source": "cost_v2_hierarchical",
    }


# ─────────────────────────────────────────────────────────────────────────
# Overall manufacturability — average of the three
# ─────────────────────────────────────────────────────────────────────────

def manufacturability(composition: dict[str, float]) -> dict[str, Any]:
    cast = castability_score(composition)
    weld = weldability_score(composition)
    cost = cost_score(composition)

    sub = [s.get("value") for s in (cast, weld, cost) if s.get("value") is not None]
    overall = round(sum(sub) / len(sub), 1) if sub else None

    return {
        "overall": overall,
        "castability": cast,
        "weldability": weld,
        "cost": cost,
    }
