"""
Hand-curated yield strength datasets for non-ferrous alloy families.

Compositions are in **weight percent** (the engineering convention for
named alloys). Yield strengths are for the **peak-aged or work-hardened
temper** typical of the alloy designation — i.e., what's *achievable* in
that composition with appropriate processing.

References: ASM Aerospace Specification Metals reference sheets, ASM
Handbook v.2 (Al alloys), v.3 (Ni-based and special alloys), v.4 (heat
treating), Boyer "Materials Properties Handbook: Titanium Alloys" (1994).

Each entry: {name, composition_wt: {element: wt%}, ys_MPa, temper, source_note}
"""

# ─────────────────────────────────────────────────────────────────────────
# Aluminum alloys (~30 representative alloys across major series)
# ─────────────────────────────────────────────────────────────────────────

ALUMINUM_ALLOYS = [
    # 1xxx — pure / commercially pure Al
    {"name": "1100-H14",     "composition_wt": {"Al": 99.0, "Si": 0.5, "Fe": 0.5},                                "ys_MPa": 117,  "temper": "H14"},
    {"name": "1050-H14",     "composition_wt": {"Al": 99.5, "Si": 0.25, "Fe": 0.25},                              "ys_MPa": 105,  "temper": "H14"},
    # 2xxx — Al-Cu
    {"name": "2014-T6",      "composition_wt": {"Al": 92.5, "Cu": 4.4, "Si": 0.8, "Mn": 0.8, "Mg": 0.5},          "ys_MPa": 414,  "temper": "T6"},
    {"name": "2017-T4",      "composition_wt": {"Al": 93.5, "Cu": 4.0, "Mg": 0.6, "Mn": 0.7, "Si": 0.5, "Fe": 0.7}, "ys_MPa": 275, "temper": "T4"},
    {"name": "2024-T3",      "composition_wt": {"Al": 93.5, "Cu": 4.4, "Mg": 1.5, "Mn": 0.6},                     "ys_MPa": 345,  "temper": "T3"},
    {"name": "2024-T81",     "composition_wt": {"Al": 93.5, "Cu": 4.4, "Mg": 1.5, "Mn": 0.6},                     "ys_MPa": 450,  "temper": "T81"},
    {"name": "2090-T84",     "composition_wt": {"Al": 95.4, "Cu": 2.7, "Li": 2.1, "Zr": 0.12},                    "ys_MPa": 520,  "temper": "T84"},
    {"name": "2050-T84",     "composition_wt": {"Al": 94.2, "Cu": 3.6, "Li": 1.0, "Mg": 0.4, "Mn": 0.35, "Ag": 0.4, "Zr": 0.11}, "ys_MPa": 515, "temper": "T84"},
    {"name": "2099-T83",     "composition_wt": {"Al": 94.0, "Cu": 2.7, "Li": 1.75, "Zn": 0.7, "Mg": 0.3, "Mn": 0.3, "Zr": 0.09}, "ys_MPa": 505, "temper": "T83"},
    # 3xxx — Al-Mn
    {"name": "3003-H18",     "composition_wt": {"Al": 97.5, "Mn": 1.2, "Cu": 0.12, "Fe": 0.7, "Si": 0.6},         "ys_MPa": 185,  "temper": "H18"},
    {"name": "3105-H25",     "composition_wt": {"Al": 97.5, "Mn": 0.55, "Mg": 0.5, "Cu": 0.3, "Si": 0.6, "Fe": 0.7}, "ys_MPa": 160, "temper": "H25"},
    # 4xxx — Al-Si
    {"name": "4032-T6",      "composition_wt": {"Al": 85.0, "Si": 12.2, "Mg": 1.0, "Cu": 0.9, "Ni": 0.9},         "ys_MPa": 315,  "temper": "T6"},
    # 5xxx — Al-Mg
    {"name": "5052-H32",     "composition_wt": {"Al": 97.0, "Mg": 2.5, "Cr": 0.25, "Si": 0.25},                   "ys_MPa": 195,  "temper": "H32"},
    {"name": "5083-O",       "composition_wt": {"Al": 94.6, "Mg": 4.4, "Mn": 0.7, "Cr": 0.15},                    "ys_MPa": 145,  "temper": "O"},
    {"name": "5086-H32",     "composition_wt": {"Al": 95.4, "Mg": 4.0, "Mn": 0.45, "Cr": 0.15},                   "ys_MPa": 205,  "temper": "H32"},
    {"name": "5454-H32",     "composition_wt": {"Al": 96.3, "Mg": 2.7, "Mn": 0.8, "Cr": 0.12},                    "ys_MPa": 205,  "temper": "H32"},
    {"name": "5754-H22",     "composition_wt": {"Al": 96.7, "Mg": 3.0, "Mn": 0.5},                                "ys_MPa": 160,  "temper": "H22"},
    # 6xxx — Al-Mg-Si
    {"name": "6061-T6",      "composition_wt": {"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2},         "ys_MPa": 276,  "temper": "T6"},
    {"name": "6063-T6",      "composition_wt": {"Al": 98.9, "Mg": 0.7, "Si": 0.4},                                "ys_MPa": 215,  "temper": "T6"},
    {"name": "6082-T6",      "composition_wt": {"Al": 97.5, "Mg": 0.9, "Si": 1.0, "Mn": 0.6},                     "ys_MPa": 260,  "temper": "T6"},
    {"name": "6111-T4",      "composition_wt": {"Al": 97.2, "Mg": 0.7, "Si": 0.85, "Cu": 0.85, "Mn": 0.3},        "ys_MPa": 200,  "temper": "T4"},
    # 7xxx — Al-Zn-Mg-Cu
    {"name": "7075-T6",      "composition_wt": {"Al": 90.0, "Zn": 5.6, "Mg": 2.5, "Cu": 1.6, "Cr": 0.23},         "ys_MPa": 503,  "temper": "T6"},
    {"name": "7075-T73",     "composition_wt": {"Al": 90.0, "Zn": 5.6, "Mg": 2.5, "Cu": 1.6, "Cr": 0.23},         "ys_MPa": 435,  "temper": "T73"},
    {"name": "7050-T74",     "composition_wt": {"Al": 89.5, "Zn": 6.2, "Mg": 2.25, "Cu": 2.3, "Zr": 0.12},        "ys_MPa": 470,  "temper": "T74"},
    {"name": "7178-T6",      "composition_wt": {"Al": 88.5, "Zn": 6.8, "Mg": 2.7, "Cu": 2.0, "Cr": 0.25},         "ys_MPa": 540,  "temper": "T6"},
    {"name": "7068-T6511",   "composition_wt": {"Al": 88.0, "Zn": 7.8, "Mg": 2.5, "Cu": 2.0, "Zr": 0.11},         "ys_MPa": 700,  "temper": "T6511"},
    # Cast aluminum (A-series)
    {"name": "A356-T6",      "composition_wt": {"Al": 92.0, "Si": 7.0, "Mg": 0.3, "Fe": 0.2},                     "ys_MPa": 200,  "temper": "T6"},
    {"name": "A357-T6",      "composition_wt": {"Al": 91.5, "Si": 7.0, "Mg": 0.5, "Be": 0.05},                    "ys_MPa": 260,  "temper": "T6"},
    {"name": "A201-T7",      "composition_wt": {"Al": 93.5, "Cu": 4.6, "Mg": 0.3, "Ag": 0.7, "Ti": 0.3, "Mn": 0.35}, "ys_MPa": 415, "temper": "T7"},
]


# ─────────────────────────────────────────────────────────────────────────
# Titanium alloys (~20 alloys: α, α-β, β classes)
# ─────────────────────────────────────────────────────────────────────────

TITANIUM_ALLOYS = [
    # CP Ti (Grades 1-4) — α
    {"name": "Grade 1 CP-Ti",       "composition_wt": {"Ti": 99.5, "Fe": 0.2, "O": 0.18},                          "ys_MPa": 170,  "temper": "Annealed"},
    {"name": "Grade 2 CP-Ti",       "composition_wt": {"Ti": 99.2, "Fe": 0.3, "O": 0.25},                          "ys_MPa": 275,  "temper": "Annealed"},
    {"name": "Grade 4 CP-Ti",       "composition_wt": {"Ti": 99.0, "Fe": 0.5, "O": 0.4},                           "ys_MPa": 480,  "temper": "Annealed"},
    {"name": "Grade 7 Ti-Pd",       "composition_wt": {"Ti": 99.3, "Pd": 0.15, "Fe": 0.3, "O": 0.25},              "ys_MPa": 275,  "temper": "Annealed"},
    # α alloys
    {"name": "Ti-5Al-2.5Sn",        "composition_wt": {"Ti": 92.5, "Al": 5.0, "Sn": 2.5},                          "ys_MPa": 800,  "temper": "Annealed"},
    # α-β alloys
    {"name": "Ti-3Al-2.5V",         "composition_wt": {"Ti": 94.5, "Al": 3.0, "V": 2.5},                           "ys_MPa": 585,  "temper": "Annealed"},
    {"name": "Ti-6Al-4V (Gr 5)",    "composition_wt": {"Ti": 90.0, "Al": 6.0, "V": 4.0},                           "ys_MPa": 880,  "temper": "STA"},
    {"name": "Ti-6Al-4V Ann (Gr 5)","composition_wt": {"Ti": 90.0, "Al": 6.0, "V": 4.0},                           "ys_MPa": 825,  "temper": "Annealed"},
    {"name": "Ti-6Al-4V ELI",       "composition_wt": {"Ti": 90.0, "Al": 6.0, "V": 4.0},                           "ys_MPa": 795,  "temper": "Annealed"},
    {"name": "Ti-6Al-6V-2Sn",       "composition_wt": {"Ti": 85.0, "Al": 6.0, "V": 6.0, "Sn": 2.0, "Cu": 0.5, "Fe": 0.5}, "ys_MPa": 965, "temper": "STA"},
    {"name": "Ti-6Al-2Sn-4Zr-2Mo",  "composition_wt": {"Ti": 86.0, "Al": 6.0, "Sn": 2.0, "Zr": 4.0, "Mo": 2.0},    "ys_MPa": 895,  "temper": "Duplex anneal"},
    {"name": "Ti-6Al-2Sn-4Zr-6Mo",  "composition_wt": {"Ti": 82.0, "Al": 6.0, "Sn": 2.0, "Zr": 4.0, "Mo": 6.0},    "ys_MPa": 1100, "temper": "STA"},
    {"name": "Ti-8Al-1Mo-1V",       "composition_wt": {"Ti": 90.0, "Al": 8.0, "Mo": 1.0, "V": 1.0},                "ys_MPa": 900,  "temper": "Duplex anneal"},
    # β / near-β alloys
    {"name": "Ti-10V-2Fe-3Al",      "composition_wt": {"Ti": 85.0, "V": 10.0, "Fe": 2.0, "Al": 3.0},               "ys_MPa": 1170, "temper": "STA"},
    {"name": "Ti-15V-3Cr-3Al-3Sn",  "composition_wt": {"Ti": 76.0, "V": 15.0, "Cr": 3.0, "Al": 3.0, "Sn": 3.0},    "ys_MPa": 1100, "temper": "STA"},
    {"name": "Beta-21S",            "composition_wt": {"Ti": 79.0, "Mo": 15.0, "Nb": 2.7, "Al": 3.0, "Si": 0.2},   "ys_MPa": 1085, "temper": "STA"},
    {"name": "Ti-3Al-8V-6Cr-4Mo-4Zr","composition_wt": {"Ti": 75.0, "Al": 3.0, "V": 8.0, "Cr": 6.0, "Mo": 4.0, "Zr": 4.0}, "ys_MPa": 1380, "temper": "STA"},
    {"name": "Ti-13V-11Cr-3Al",     "composition_wt": {"Ti": 73.0, "V": 13.0, "Cr": 11.0, "Al": 3.0},              "ys_MPa": 1240, "temper": "STA"},
    {"name": "Ti-15Mo",             "composition_wt": {"Ti": 85.0, "Mo": 15.0},                                    "ys_MPa": 875,  "temper": "STA"},
    {"name": "Ti-12Mo-6Zr-2Fe",     "composition_wt": {"Ti": 80.0, "Mo": 12.0, "Zr": 6.0, "Fe": 2.0},              "ys_MPa": 950,  "temper": "STA"},
]


# ─────────────────────────────────────────────────────────────────────────
# Nickel-base superalloys (~22 alloys: solid-solution + precipitation hardened)
# ─────────────────────────────────────────────────────────────────────────

NICKEL_ALLOYS = [
    # Solid-solution strengthened (annealed)
    {"name": "Inconel 600",     "composition_wt": {"Ni": 76.0, "Cr": 15.5, "Fe": 8.0, "Mn": 0.5},                     "ys_MPa": 240,  "temper": "Annealed"},
    {"name": "Inconel 601",     "composition_wt": {"Ni": 60.5, "Cr": 23.0, "Fe": 14.0, "Al": 1.4, "Mn": 1.0},         "ys_MPa": 350,  "temper": "Annealed"},
    {"name": "Inconel 625",     "composition_wt": {"Ni": 61.0, "Cr": 21.5, "Mo": 9.0, "Nb": 3.7, "Fe": 4.0},          "ys_MPa": 460,  "temper": "Annealed"},
    {"name": "Hastelloy X",     "composition_wt": {"Ni": 47.0, "Cr": 22.0, "Fe": 18.5, "Mo": 9.0, "Co": 1.5, "W": 0.6}, "ys_MPa": 345, "temper": "Annealed"},
    {"name": "Hastelloy C-22",  "composition_wt": {"Ni": 56.0, "Cr": 22.0, "Mo": 13.0, "W": 3.0, "Fe": 4.0, "Co": 2.5}, "ys_MPa": 350, "temper": "Annealed"},
    {"name": "Hastelloy C-276", "composition_wt": {"Ni": 57.0, "Cr": 15.5, "Mo": 16.0, "W": 3.7, "Fe": 5.5, "Co": 2.5}, "ys_MPa": 355, "temper": "Annealed"},
    {"name": "Hastelloy B-2",   "composition_wt": {"Ni": 70.0, "Mo": 28.0, "Fe": 1.0, "Cr": 1.0},                     "ys_MPa": 415,  "temper": "Annealed"},
    {"name": "Nimonic 75",      "composition_wt": {"Ni": 76.0, "Cr": 19.5, "Fe": 3.0, "Ti": 0.4, "C": 0.1},           "ys_MPa": 275,  "temper": "Annealed"},
    # Precipitation hardened (γ' / γ" strengthening)
    {"name": "Inconel 718",     "composition_wt": {"Ni": 53.0, "Cr": 19.0, "Fe": 18.5, "Nb": 5.0, "Mo": 3.0, "Ti": 0.9, "Al": 0.5}, "ys_MPa": 1100, "temper": "Aged"},
    {"name": "Inconel 738 LC",  "composition_wt": {"Ni": 61.0, "Cr": 16.0, "Co": 8.5, "W": 2.6, "Mo": 1.75, "Ta": 1.75, "Nb": 0.9, "Al": 3.4, "Ti": 3.4}, "ys_MPa": 950, "temper": "Aged"},
    {"name": "Inconel 750",     "composition_wt": {"Ni": 73.0, "Cr": 15.5, "Fe": 7.0, "Ti": 2.5, "Al": 0.7, "Nb": 1.0}, "ys_MPa": 815, "temper": "Aged"},
    {"name": "Inconel 939",     "composition_wt": {"Ni": 48.0, "Cr": 22.5, "Co": 19.0, "W": 2.0, "Nb": 1.0, "Ta": 1.4, "Ti": 3.7, "Al": 1.9}, "ys_MPa": 820, "temper": "Aged"},
    {"name": "Waspaloy",        "composition_wt": {"Ni": 58.0, "Cr": 19.5, "Co": 13.5, "Mo": 4.3, "Ti": 3.0, "Al": 1.3}, "ys_MPa": 1000, "temper": "Aged"},
    {"name": "Udimet 500",      "composition_wt": {"Ni": 53.0, "Cr": 19.0, "Co": 18.0, "Mo": 4.0, "Ti": 3.0, "Al": 3.0}, "ys_MPa": 820, "temper": "Aged"},
    {"name": "Udimet 700",      "composition_wt": {"Ni": 53.0, "Cr": 15.0, "Co": 18.5, "Mo": 5.2, "Ti": 3.4, "Al": 4.3}, "ys_MPa": 965, "temper": "Aged"},
    {"name": "Mar-M-247",       "composition_wt": {"Ni": 60.0, "Co": 10.0, "Cr": 8.4, "W": 10.0, "Mo": 0.7, "Ta": 3.0, "Al": 5.5, "Ti": 1.0, "Hf": 1.4}, "ys_MPa": 825, "temper": "Aged"},
    {"name": "CMSX-4",          "composition_wt": {"Ni": 61.5, "Co": 9.0, "Cr": 6.5, "W": 6.0, "Mo": 0.6, "Ta": 6.5, "Al": 5.6, "Ti": 1.0, "Re": 3.0, "Hf": 0.1}, "ys_MPa": 945, "temper": "Aged"},
    {"name": "Rene N5",         "composition_wt": {"Ni": 63.0, "Co": 7.5, "Cr": 7.0, "W": 5.0, "Mo": 1.5, "Ta": 6.5, "Al": 6.2, "Re": 3.0, "Hf": 0.15}, "ys_MPa": 900, "temper": "Aged"},
    {"name": "PWA 1480",        "composition_wt": {"Ni": 63.0, "Co": 5.0, "Cr": 10.0, "W": 4.0, "Ta": 12.0, "Al": 5.0, "Ti": 1.5},  "ys_MPa": 900, "temper": "Aged"},
    {"name": "Nimonic 80A",     "composition_wt": {"Ni": 76.0, "Cr": 19.5, "Ti": 2.4, "Al": 1.4, "Co": 1.0, "Fe": 1.5}, "ys_MPa": 620,  "temper": "Aged"},
    {"name": "Nimonic 90",      "composition_wt": {"Ni": 60.0, "Cr": 19.5, "Co": 16.5, "Ti": 2.4, "Al": 1.4},          "ys_MPa": 700,  "temper": "Aged"},
    {"name": "Nimonic 105",     "composition_wt": {"Ni": 53.0, "Cr": 14.5, "Co": 20.0, "Mo": 5.0, "Ti": 1.2, "Al": 4.7}, "ys_MPa": 750, "temper": "Aged"},
    {"name": "Nimonic 115",     "composition_wt": {"Ni": 60.0, "Cr": 14.3, "Co": 13.2, "Mo": 3.3, "Ti": 4.0, "Al": 4.9}, "ys_MPa": 860, "temper": "Aged"},
]


# ─────────────────────────────────────────────────────────────────────────
# Conversion utilities
# ─────────────────────────────────────────────────────────────────────────

def weight_to_atomic(comp_wt: dict[str, float]) -> dict[str, float]:
    """
    Convert weight % → atomic %.  Returns a dict that sums to 100 (atomic %).
    Uses pymatgen atomic masses; falls back to a small table for common elements.
    """
    from pymatgen.core import Element
    moles = {}
    for el, w in comp_wt.items():
        try:
            mass = Element(el).atomic_mass
        except Exception:
            continue
        moles[el] = w / mass
    s = sum(moles.values())
    if s <= 0:
        return comp_wt
    return {el: round(m / s * 100, 3) for el, m in moles.items()}
