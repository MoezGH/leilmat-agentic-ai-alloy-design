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
# General engineering steels (~36 alloys: mild, low-alloy, austenitic /
# ferritic / martensitic / PH stainless, tool, ARMOR / weathering).
#
# Fills the gap left by matbench_steels, which only covers ultra-high-strength
# martensitic / maraging / AHSS (1000-2500 MPa). Common engineering steels
# (AISI 1018, AISI 304, AISI 4140, A36 plate) are far below that range — they
# were correctly OOD-refused before this dataset, but that meant the model
# couldn't say anything about most steels a designer would actually encounter.
#
# References: ASM Handbook v.1 (Properties and Selection: Iron Steels and
# High-Performance Alloys, 10th ed.), ASTM material spec sheets, ASME Boiler
# and Pressure Vessel Code Section II Part D, AISI/SAE J403/J404.
# ─────────────────────────────────────────────────────────────────────────

GENERAL_STEEL_ALLOYS = [
    # ── Mild / low-carbon structural (100-400 MPa range) ───────────────
    {"name": "AISI 1008 CRS",      "composition_wt": {"Fe": 99.0, "C": 0.08, "Mn": 0.45, "S": 0.05, "P": 0.04},                       "ys_MPa": 285,  "temper": "Cold rolled"},
    {"name": "AISI 1010 HR",       "composition_wt": {"Fe": 99.2, "C": 0.10, "Mn": 0.45, "S": 0.05, "P": 0.04},                       "ys_MPa": 305,  "temper": "Hot rolled"},
    {"name": "AISI 1018 CD",       "composition_wt": {"Fe": 98.85, "C": 0.18, "Mn": 0.75, "Si": 0.15, "S": 0.05, "P": 0.04},          "ys_MPa": 370,  "temper": "Cold drawn"},
    {"name": "AISI 1020 HR",       "composition_wt": {"Fe": 99.1, "C": 0.20, "Mn": 0.45, "Si": 0.15, "S": 0.05, "P": 0.04},           "ys_MPa": 295,  "temper": "Hot rolled"},
    {"name": "AISI 1045 N",        "composition_wt": {"Fe": 98.5, "C": 0.45, "Mn": 0.75, "Si": 0.20, "S": 0.05, "P": 0.04},           "ys_MPa": 450,  "temper": "Normalised"},
    {"name": "ASTM A36 plate",     "composition_wt": {"Fe": 98.0, "C": 0.25, "Mn": 1.0, "Si": 0.40, "Cu": 0.20, "S": 0.05, "P": 0.05}, "ys_MPa": 250, "temper": "As-rolled"},
    {"name": "ASTM A572 Gr50",     "composition_wt": {"Fe": 97.8, "C": 0.23, "Mn": 1.35, "Si": 0.40, "Cu": 0.20, "V": 0.04, "Nb": 0.05}, "ys_MPa": 345, "temper": "HSLA"},
    {"name": "ASTM A992 W-flange", "composition_wt": {"Fe": 97.7, "C": 0.23, "Mn": 1.5, "Si": 0.40, "Cu": 0.15, "Cr": 0.03, "Ni": 0.04, "V": 0.06, "Nb": 0.03}, "ys_MPa": 345, "temper": "HSLA"},
    {"name": "ASTM A588 Cor-Ten",  "composition_wt": {"Fe": 96.7, "C": 0.20, "Mn": 1.0, "Si": 0.45, "Cu": 0.4, "Cr": 0.55, "Ni": 0.4, "V": 0.07}, "ys_MPa": 345, "temper": "Weathering"},

    # ── Low-alloy / Q&T (400-1000 MPa) ─────────────────────────────────
    {"name": "AISI 4130 Q&T",      "composition_wt": {"Fe": 97.0, "C": 0.32, "Mn": 0.55, "Si": 0.25, "Cr": 1.0, "Mo": 0.2},           "ys_MPa": 460,  "temper": "Q&T 650°C"},
    {"name": "AISI 4140 Q&T",      "composition_wt": {"Fe": 96.5, "C": 0.40, "Mn": 0.85, "Si": 0.25, "Cr": 1.0, "Mo": 0.2},           "ys_MPa": 655,  "temper": "Q&T 400°C"},
    {"name": "AISI 4340 Q&T",      "composition_wt": {"Fe": 95.7, "C": 0.40, "Mn": 0.70, "Si": 0.25, "Cr": 0.8, "Mo": 0.25, "Ni": 1.85}, "ys_MPa": 855, "temper": "Q&T 425°C"},
    {"name": "AISI 8620 case",     "composition_wt": {"Fe": 97.0, "C": 0.20, "Mn": 0.85, "Si": 0.25, "Cr": 0.50, "Mo": 0.20, "Ni": 0.55}, "ys_MPa": 415, "temper": "Carburised + Q&T"},
    {"name": "AISI 5160 spring",   "composition_wt": {"Fe": 97.4, "C": 0.60, "Mn": 0.85, "Si": 0.25, "Cr": 0.85},                     "ys_MPa": 1080, "temper": "Q&T 450°C"},
    {"name": "AISI 9310 carb.",    "composition_wt": {"Fe": 94.5, "C": 0.10, "Mn": 0.55, "Si": 0.25, "Cr": 1.2, "Mo": 0.12, "Ni": 3.25}, "ys_MPa": 825, "temper": "Carburised + Q&T"},
    {"name": "300M ultrahigh-str.","composition_wt": {"Fe": 95.0, "C": 0.42, "Mn": 0.75, "Si": 1.6, "Cr": 0.85, "Mo": 0.4, "Ni": 1.85, "V": 0.07}, "ys_MPa": 1620, "temper": "Q&T 300°C"},

    # ── Austenitic stainless (200-300 MPa annealed) ────────────────────
    {"name": "AISI 304 stainless", "composition_wt": {"Fe": 70.0, "C": 0.07, "Cr": 19.0, "Ni": 9.0, "Mn": 1.5, "Si": 0.5, "P": 0.04, "S": 0.03}, "ys_MPa": 215, "temper": "Annealed"},
    {"name": "AISI 304L stainless","composition_wt": {"Fe": 70.4, "C": 0.025, "Cr": 18.5, "Ni": 9.5, "Mn": 1.5, "Si": 0.5},           "ys_MPa": 170,  "temper": "Annealed"},
    {"name": "AISI 316 stainless", "composition_wt": {"Fe": 67.0, "C": 0.07, "Cr": 17.0, "Ni": 12.0, "Mo": 2.5, "Mn": 1.5, "Si": 0.5}, "ys_MPa": 240, "temper": "Annealed"},
    {"name": "AISI 316L stainless","composition_wt": {"Fe": 67.5, "C": 0.025, "Cr": 17.0, "Ni": 12.0, "Mo": 2.5, "Mn": 1.5, "Si": 0.5}, "ys_MPa": 205, "temper": "Annealed"},
    {"name": "AISI 321 stabilised","composition_wt": {"Fe": 70.0, "C": 0.07, "Cr": 18.0, "Ni": 10.5, "Ti": 0.5, "Mn": 1.5, "Si": 0.5}, "ys_MPa": 240, "temper": "Annealed"},
    {"name": "AISI 347 stabilised","composition_wt": {"Fe": 69.0, "C": 0.06, "Cr": 18.0, "Ni": 11.0, "Nb": 0.8, "Mn": 1.5, "Si": 0.5}, "ys_MPa": 240, "temper": "Annealed"},
    {"name": "Nitronic 60",        "composition_wt": {"Fe": 62.5, "C": 0.07, "Cr": 17.0, "Ni": 8.5, "Mn": 8.0, "Si": 4.0, "N": 0.15}, "ys_MPa": 415, "temper": "Annealed (N-strengthened)"},

    # ── Ferritic stainless (~250-450 MPa) ──────────────────────────────
    {"name": "AISI 409 ferritic",  "composition_wt": {"Fe": 86.6, "C": 0.05, "Cr": 11.0, "Ti": 0.45, "Mn": 1.0, "Si": 0.5},           "ys_MPa": 200,  "temper": "Annealed"},
    {"name": "AISI 430 ferritic",  "composition_wt": {"Fe": 81.0, "C": 0.07, "Cr": 17.0, "Mn": 1.0, "Si": 0.5},                       "ys_MPa": 275,  "temper": "Annealed"},
    {"name": "AISI 444 superfer.", "composition_wt": {"Fe": 79.0, "C": 0.02, "Cr": 18.5, "Mo": 2.0, "Ti": 0.3, "Mn": 0.5, "Si": 0.5}, "ys_MPa": 310,  "temper": "Annealed"},

    # ── Martensitic stainless (500-1300 MPa) ───────────────────────────
    {"name": "AISI 410 martensit.","composition_wt": {"Fe": 86.7, "C": 0.15, "Cr": 12.5, "Mn": 1.0, "Si": 0.5},                       "ys_MPa": 415,  "temper": "Q&T 600°C"},
    {"name": "AISI 420 martensit.","composition_wt": {"Fe": 84.5, "C": 0.30, "Cr": 13.5, "Mn": 1.0, "Si": 0.5},                       "ys_MPa": 690,  "temper": "Q&T 400°C"},
    {"name": "AISI 440C bearings", "composition_wt": {"Fe": 80.5, "C": 1.05, "Cr": 17.0, "Mn": 1.0, "Si": 0.5, "Mo": 0.5},            "ys_MPa": 1900, "temper": "Q&T 200°C"},

    # ── Precipitation-hardening stainless (1000-1500 MPa) ──────────────
    {"name": "17-4PH H900",        "composition_wt": {"Fe": 74.7, "C": 0.04, "Cr": 16.0, "Ni": 4.2, "Cu": 3.4, "Nb": 0.3, "Mn": 1.0}, "ys_MPa": 1170, "temper": "H900 (aged 482°C)"},
    {"name": "17-7PH RH950",       "composition_wt": {"Fe": 75.5, "C": 0.07, "Cr": 17.0, "Ni": 7.0, "Al": 1.15, "Mn": 1.0, "Si": 0.5}, "ys_MPa": 1170, "temper": "RH950"},
    {"name": "15-5PH H900",        "composition_wt": {"Fe": 75.8, "C": 0.05, "Cr": 15.0, "Ni": 4.7, "Cu": 3.5, "Nb": 0.3, "Mn": 1.0}, "ys_MPa": 1170, "temper": "H900"},
    {"name": "13-8 Mo H950",       "composition_wt": {"Fe": 74.7, "C": 0.04, "Cr": 13.0, "Ni": 8.2, "Mo": 2.2, "Al": 1.0, "Mn": 0.5}, "ys_MPa": 1380, "temper": "H950"},

    # ── Modern HSLA / pipeline (350-800 MPa) ───────────────────────────
    {"name": "API X65 pipeline",   "composition_wt": {"Fe": 97.6, "C": 0.10, "Mn": 1.4, "Si": 0.25, "Cu": 0.20, "Nb": 0.05, "V": 0.06, "Ti": 0.02}, "ys_MPa": 450, "temper": "TMCP"},
    {"name": "API X80 pipeline",   "composition_wt": {"Fe": 97.3, "C": 0.07, "Mn": 1.85, "Si": 0.25, "Cu": 0.20, "Ni": 0.10, "Nb": 0.08, "V": 0.04, "Mo": 0.10, "Ti": 0.02}, "ys_MPa": 555, "temper": "TMCP"},
]


# ─────────────────────────────────────────────────────────────────────────
# Sprint 3 — extended entries (provenance-tagged) appended below.
# Each *_ALLOYS list is the deduplicated union of the base set above and
# the entries in ``apps.api.ml.datasets.extended.<family>``.  Trainers
# import the *_ALLOYS name, so they automatically pick up the new data.
# ─────────────────────────────────────────────────────────────────────────

def _append_extended():
    """Merge Sprint-3 extended entries into the *_ALLOYS lists in place,
    deduplicating by (canonical_name, temper) so that the carefully-curated
    base entries above are preserved when there is overlap.

    Defence in depth: any extended entry whose name appears in
    ``apps.api.ml.eval.holdout_alloys.ALL_HOLDOUT`` is silently dropped to
    prevent training-on-holdout data leakage — even if a future maintainer
    accidentally adds one.
    """
    try:
        from apps.api.ml.datasets.crosswalk import canonical_name
        from apps.api.ml.datasets.extended import (
            aluminum as _al_ext,
            titanium as _ti_ext,
            nickel   as _ni_ext,
            general_steel as _st_ext,
        )
    except ImportError:
        return  # extended package not present; base set unchanged.

    # Build a per-family holdout-name blocklist for training-data leakage defence.
    try:
        from apps.api.ml.eval.holdout_alloys import ALL_HOLDOUT
        holdout_blocklist = {
            "aluminum":      {h["name"] for h in ALL_HOLDOUT.get("aluminum", [])},
            "titanium":      {h["name"] for h in ALL_HOLDOUT.get("titanium", [])},
            "nickel":        {h["name"] for h in ALL_HOLDOUT.get("nickel", [])},
            # Holdout key is "steel"; trainer key is "general_steel"
            "general_steel": {h["name"] for h in ALL_HOLDOUT.get("steel", [])},
        }
    except ImportError:
        holdout_blocklist = {"aluminum": set(), "titanium": set(),
                             "nickel": set(), "general_steel": set()}

    def _strip_blocked(base_list, blocked):
        """Remove any base entries whose name appears in the holdout blocklist."""
        keep = [e for e in base_list if e["name"] not in blocked]
        # Mutate the list in place (we can't reassign the global from inside)
        base_list[:] = keep

    def _merge(family, base_list, extended_entries):
        blocked = holdout_blocklist.get(family, set())
        # First strip any base entries that leak into the held-out test set.
        # (Without this, evaluation on held-out alloys would measure memorisation.)
        _strip_blocked(base_list, blocked)
        seen = {(canonical_name(e["name"]), e.get("temper", "")) for e in base_list}
        for entry in extended_entries:
            if entry["name"] in blocked:
                continue  # don't leak held-out alloys into training
            key = (canonical_name(entry["name"]), entry.get("temper", ""))
            if key not in seen:
                base_list.append(entry)
                seen.add(key)

    _merge("aluminum",      ALUMINUM_ALLOYS,      getattr(_al_ext, "ENTRIES", []))
    _merge("titanium",      TITANIUM_ALLOYS,      getattr(_ti_ext, "ENTRIES", []))
    _merge("nickel",        NICKEL_ALLOYS,        getattr(_ni_ext, "ENTRIES", []))
    _merge("general_steel", GENERAL_STEEL_ALLOYS, getattr(_st_ext, "ENTRIES", []))


_append_extended()


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
