"""
Held-out canonical alloys for validating the trained yield-strength models.

These alloys are deliberately NOT in `apps/api/ml/alloy_datasets.py`. They serve
as an *out-of-training* test set: predictions on them tell us whether the
production model (fit on the full training set) actually generalises, not just
memorises.

Compositions are in **weight percent** (engineering convention). Yield strengths
are for the peak-aged or commercially-supplied temper.

Sources: ASM Handbook v.2 (Al), v.3 (Ni superalloys), ASTM B265 (Ti), Boyer
"Materials Properties Handbook: Titanium Alloys" (1994), Donachie "Titanium:
A Technical Guide" (2000), MIL-HDBK-5J.
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────
# Aluminum holdout — alloys not in ALUMINUM_ALLOYS
# ─────────────────────────────────────────────────────────────────────────

ALUMINUM_HOLDOUT = [
    {
        "name": "2618-T651",
        "composition_wt": {"Al": 93.7, "Cu": 2.3, "Mg": 1.6, "Fe": 1.1, "Ni": 1.0, "Si": 0.18, "Ti": 0.07},
        "ys_MPa": 372,
        "temper": "T651",
        "expected_in_domain": True,
        "note": "Piston alloy (high-T Al-Cu-Mg-Fe-Ni); long-life rotating components.",
    },
    {
        "name": "6005A-T6",
        "composition_wt": {"Al": 98.0, "Mg": 0.55, "Si": 0.75, "Mn": 0.2, "Cr": 0.15, "Cu": 0.1, "Fe": 0.25},
        "ys_MPa": 240,
        "temper": "T6",
        "expected_in_domain": True,
        "note": "Medium-strength extrusion alloy (different chemistry from 6061/6082).",
    },
    {
        "name": "5456-H321",
        "composition_wt": {"Al": 93.9, "Mg": 5.1, "Mn": 0.8, "Cr": 0.12, "Cu": 0.08},
        "ys_MPa": 230,
        "temper": "H321",
        "expected_in_domain": True,
        "note": "Marine structural plate; higher Mg than 5083/5086.",
    },
    {
        "name": "7150-T7751",
        "composition_wt": {"Al": 88.0, "Zn": 6.4, "Mg": 2.4, "Cu": 2.3, "Zr": 0.12, "Mn": 0.1},
        "ys_MPa": 490,
        "temper": "T7751",
        "expected_in_domain": True,
        "note": "Wing-skin alloy; T7751 is an overaged variant for stress-corrosion resistance.",
    },
    {
        "name": "8090-T8771",
        "composition_wt": {"Al": 94.0, "Li": 2.5, "Cu": 1.3, "Mg": 0.9, "Zr": 0.1},
        "ys_MPa": 415,
        "temper": "T8771",
        "expected_in_domain": False,
        "note": "Second-gen Al-Li for aerospace — OOD-borderline (Li/Cu ratio differs from Cu-rich 2xxx Li alloys).",
    },
]


# ─────────────────────────────────────────────────────────────────────────
# Titanium holdout — alloys not in TITANIUM_ALLOYS
# ─────────────────────────────────────────────────────────────────────────

TITANIUM_HOLDOUT = [
    {
        "name": "Grade 3 CP-Ti",
        "composition_wt": {"Ti": 99.1, "Fe": 0.3, "O": 0.35},
        "ys_MPa": 380,
        "temper": "Annealed",
        "expected_in_domain": True,
        "note": "Commercially pure Ti, between Gr 2 and Gr 4 (oxygen content ~0.35%).",
    },
    {
        "name": "Ti-6Al-7Nb",
        "composition_wt": {"Ti": 87.0, "Al": 6.0, "Nb": 7.0},
        "ys_MPa": 800,
        "temper": "Annealed",
        "expected_in_domain": True,
        "note": "Biomedical α-β alloy; Nb-substituted analogue of Ti-6Al-4V (V is cytotoxic).",
    },
    {
        "name": "Ti-5553",
        "composition_wt": {"Ti": 82.0, "Al": 5.0, "V": 5.0, "Mo": 5.0, "Cr": 3.0},
        "ys_MPa": 1140,
        "temper": "STA",
        "expected_in_domain": True,
        "note": "Near-β airframe alloy; Boeing 787 landing-gear forgings.",
    },
    {
        "name": "Ti-13Nb-13Zr",
        "composition_wt": {"Ti": 74.0, "Nb": 13.0, "Zr": 13.0},
        "ys_MPa": 900,
        "temper": "STA",
        "expected_in_domain": False,
        "note": "Biomedical β-alloy with unusual Nb+Zr chemistry — expected OOD vs training-set α-β alloys.",
    },
    {
        "name": "Ti-LCB",
        "composition_wt": {"Ti": 87.2, "Mo": 6.8, "Fe": 4.5, "Al": 1.5},
        "ys_MPa": 1280,
        "temper": "STA",
        "expected_in_domain": True,
        "note": "Timetal LCB; low-cost β alloy (springs, fasteners).",
    },
]


# ─────────────────────────────────────────────────────────────────────────
# Nickel holdout — alloys not in NICKEL_ALLOYS
# ─────────────────────────────────────────────────────────────────────────

NICKEL_HOLDOUT = [
    {
        "name": "Inconel 706",
        "composition_wt": {"Ni": 41.5, "Fe": 37.0, "Cr": 16.0, "Nb": 2.9, "Ti": 1.75, "Al": 0.2},
        "ys_MPa": 1000,
        "temper": "Aged",
        "expected_in_domain": True,
        "note": "γ' + γ'' precipitation; gas-turbine disks (Ni < 50% — tests sub-threshold routing).",
    },
    {
        "name": "Inconel 690",
        "composition_wt": {"Ni": 58.0, "Cr": 30.0, "Fe": 10.0, "C": 0.04},
        "ys_MPa": 285,
        "temper": "Annealed",
        "expected_in_domain": False,
        "note": "High-Cr (30%) solid solution — expected OOD vs typical Inconel chemistry (Cr 15-22%).",
    },
    {
        "name": "Inconel 825",
        "composition_wt": {"Ni": 42.0, "Fe": 28.0, "Cr": 21.5, "Mo": 3.0, "Cu": 2.2, "Ti": 0.9},
        "ys_MPa": 240,
        "temper": "Annealed",
        "expected_in_domain": True,
        "note": "Ni < 50% — also tests routing threshold and Fe-rich Ni alloys.",
    },
    {
        "name": "Rene 41",
        "composition_wt": {"Ni": 55.0, "Cr": 19.0, "Co": 11.0, "Mo": 10.0, "Ti": 3.1, "Al": 1.5},
        "ys_MPa": 1050,
        "temper": "Aged",
        "expected_in_domain": True,
        "note": "Co-rich precipitation-hardened; jet-engine afterburner.",
    },
    {
        "name": "Hastelloy G-30",
        "composition_wt": {"Ni": 43.0, "Cr": 30.0, "Fe": 15.0, "Mo": 5.5, "Cu": 1.8, "W": 2.5, "Nb": 1.0},
        "ys_MPa": 340,
        "temper": "Annealed",
        "expected_in_domain": True,
        "note": "Corrosion-resistant Ni-Cr-Mo-Cu (Ni < 50% — tests sub-threshold routing).",
    },
]


# ─────────────────────────────────────────────────────────────────────────
# Steel canonical references (matbench_steels is a black-box dataset of 312
# alloys — some of these may overlap, but the literature YS is the source of
# truth and the production model should be near them either way).
# ─────────────────────────────────────────────────────────────────────────

STEEL_REFERENCES = [
    # Originally OOD for matbench_steels (ultra-high-strength only). Now
    # in-domain via the fall-through general_steel model (mild + low-alloy
    # + stainless + PH). These alloys are NOT in the GENERAL_STEEL_ALLOYS
    # training set — they're genuine out-of-training tests for the new model.
    {
        "name": "AISI 1045 N",
        "composition_wt": {"Fe": 98.5, "C": 0.45, "Mn": 0.75, "Si": 0.20},
        "ys_MPa": 450,
        "temper": "Normalised",
        "expected_in_domain": True,
        "note": "Medium-carbon — tests general_steel mild-to-low-alloy boundary.",
    },
    {
        "name": "AISI 316Ti stainless",
        "composition_wt": {"Fe": 67.0, "C": 0.05, "Cr": 17.0, "Ni": 12.0, "Mo": 2.5, "Ti": 0.5, "Mn": 1.5, "Si": 0.5},
        "ys_MPa": 240,
        "temper": "Annealed",
        "expected_in_domain": True,
        "note": "Ti-stabilised austenitic — close to AISI 316 + Ti.",
    },
    {
        "name": "AISI 431 martensitic",
        "composition_wt": {"Fe": 81.0, "C": 0.18, "Cr": 16.0, "Ni": 2.0, "Mn": 1.0, "Si": 0.5},
        "ys_MPa": 655,
        "temper": "Q&T",
        "expected_in_domain": True,
        "note": "Martensitic Cr-Ni stainless — between 410 and 420.",
    },
    {
        "name": "Custom 465",
        "composition_wt": {"Fe": 76.3, "C": 0.02, "Cr": 11.5, "Ni": 11.0, "Mo": 1.0, "Ti": 1.6, "Al": 0.05},
        "ys_MPa": 1620,
        "temper": "H950",
        "expected_in_domain": True,
        "note": "PH stainless — high end of general_steel domain (tests upper boundary).",
    },
    # Truly OOD even for the broader general_steel model: ultra-high-strength
    # maraging at the very edge of the training distribution. Both
    # matbench_steels and general_steel refuse — that's correct.
    {
        "name": "Maraging 250 (edge)",
        "composition_wt": {"Fe": 67.0, "Ni": 18.5, "Co": 7.5, "Mo": 4.8, "Ti": 0.4, "Al": 0.1},
        "ys_MPa": 1700,
        "temper": "Aged",
        "expected_in_domain": False,
        "note": "Edge of both models' domains — co-rich maraging not represented in either training set.",
    },
    {
        "name": "AerMet 100 (edge)",
        "composition_wt": {"Fe": 75.0, "Co": 13.4, "Ni": 11.1, "Cr": 3.0, "Mo": 1.2, "C": 0.23},
        "ys_MPa": 1720,
        "temper": "Aged",
        "expected_in_domain": False,
        "note": "Edge of both models' domains — high-Co secondary-hardening steel.",
    },
]


# ─────────────────────────────────────────────────────────────────────────
# Public accessor
# ─────────────────────────────────────────────────────────────────────────

ALL_HOLDOUT = {
    "aluminum": ALUMINUM_HOLDOUT,
    "titanium": TITANIUM_HOLDOUT,
    "nickel":   NICKEL_HOLDOUT,
    "steel":    STEEL_REFERENCES,
}
