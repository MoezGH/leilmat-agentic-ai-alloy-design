"""
apps.api.ml.cost.elements_2025
================================

Spot prices for the elements LeilMat handles, USD/kg, approximate mid-2025.

Source mix (per element):
* LME (London Metal Exchange): Al, Cu, Pb, Ni, Sn, Zn          — daily spot
* USGS Mineral Commodity Summaries: Cr, Mn, Mo, Co, Ti sponge, Nb, V, W, Re, Zr
* MMTA monthly minor-metals: Ga, In, Sb, Te, Bi, Hf, Ta
* PGM (London Platinum & Palladium Market): Pt, Pd, Rh, Ir, Ru
* LBMA: Au, Ag
* Argus / Roskill: rare earths (Y, La, Ce, Nd, Sm, Gd, Tb, Dy, Ho, Er, Tm, Yb, Lu, Sc)

These are *materials-selection* numbers, not contract prices.  Real
contract prices vary ±15 % on spot for major commodities and ±50 % for
specialty elements.  ``compute_cost`` already accounts for this with
the form-factor and supplier-minimum multipliers downstream.
"""
ELEMENT_PRICE_USD_PER_KG: dict[str, float] = {
    # ─── Base metals (LME-tracked, very liquid markets) ───────────────────
    "Al":   2.70,    # LME Al 2025-Q2
    "Cu":  10.00,    # LME Cu 2025-Q2
    "Ni":  20.00,    # LME Ni 2025-Q2
    "Zn":   4.00,    # LME Zn 2025-Q2 (aerospace-grade Zn for 7xxx is dominated by purity premium)
    "Pb":   2.00,    # LME Pb 2025-Q2
    "Sn":  35.00,    # LME Sn 2025-Q2
    "Fe":   1.00,    # ~hot-rolled coil base (HRC ≈ $700-1000/ton) — the
                     # "billet-level" reference; downstream forms add the
                     # form-factor multiplier on top.

    # ─── Interstitials & metalloids (industrial purchase forms) ────────────
    "C":    1.00,    # graphite addition
    "Si":   2.50,    # ferrosilicon → pure Si reference
    "Mn":   2.00,    # electrolytic Mn
    "B":    5.00,    # ferroboron equiv.
    "P":    5.00,
    "S":    0.20,
    "N":    0.50,    # via Si3N4 / ammonia route
    "O":    0.10,    # incidental

    # ─── Transition metals (USGS) ─────────────────────────────────────────
    "Cr":  10.00,    # ferro-chrome
    "Mo":  30.00,    # ferro-molybdenum
    "W":   35.00,    # ferro-tungsten / W concentrate
    "V":   35.00,    # ferro-vanadium
    "Co":  40.00,    # cobalt cathode
    "Ti":  20.00,    # Ti sponge (Kroll) — aerospace-grade is dominated by sponge + scrap recovery loss
    "Zr":  25.00,
    "Nb":  50.00,
    "Hf": 1000.00,   # high-purity, low-Zr Hf
    "Ta": 300.00,
    "Re":2000.00,    # rhenium ingot — KEY for Ni superalloys

    # ─── Light metals / reactive ──────────────────────────────────────────
    "Mg":   3.50,
    "Li":  80.00,
    "Be":1000.00,
    "Ca":   1.50,
    "K":   10.00,
    "Na":   3.00,

    # ─── Rare earths (LREEs cheap, HREEs expensive) ───────────────────────
    "Y":   30.00,
    "La":   5.00,
    "Ce":   5.00,
    "Pr":  90.00,
    "Nd": 100.00,
    "Sm":  30.00,
    "Eu": 100.00,
    "Gd":  50.00,
    "Tb": 800.00,
    "Dy": 400.00,
    "Ho": 200.00,
    "Er": 100.00,
    "Tm":5000.00,
    "Yb":  30.00,
    "Lu": 800.00,
    "Sc":8000.00,

    # ─── Precious metals (per ounce → /kg conversion baked in) ────────────
    "Au":75000.00,
    "Ag":  900.00,
    "Pt":35000.00,
    "Pd":30000.00,
    "Rh":200000.00,
    "Ru":15000.00,
    "Ir":150000.00,

    # ─── Minor metals (MMTA) ──────────────────────────────────────────────
    "Ga":  500.00,
    "In":  300.00,
    "Sb":   8.00,
    "Bi":  10.00,
    "Te":  90.00,
    "Se":  30.00,
    "Ge":1000.00,
    "Cd":   3.00,
    "Cs":80000.00,   # caesium metal — extreme
    "Rb":50000.00,
}

DEFAULT_PRICE_USD_PER_KG = 50.0   # fallback for any element not in the table

PRICE_PROVENANCE = (
    "USD/kg spot prices, ~mid-2025. Sources: LME, USGS Mineral Commodity "
    "Summaries, MMTA, LBMA, Argus/Roskill rare-earth tables. Reload "
    "elements_2025.py periodically (monthly LME refresh is sufficient for "
    "screening purposes)."
)
