"""
Extended aluminum-alloy training entries (Sprint 3).

Every entry has a ``source`` citation and a ``value_type`` ∈ {typical,
minimum, certified}.  Only ``typical`` and ``certified`` enter the
training set; ``minimum`` values are reserved for held-out QA.

Sources used:
* "ASM/v2"  → ASM Handbook Vol. 2 — Properties and Selection: Nonferrous
              Alloys and Special-Purpose Materials, 10th ed.
* "ASM/v15" → ASM Handbook Vol. 15 — Casting.
* "AMS-####"→ AMS aerospace material specifications (typical minimum YS).
* "MIL-5J"  → MIL-HDBK-5J Metallic Materials Properties for Aerospace.
* "ASTM-B###" → ASTM B-series specifications (wrought Al alloys).
"""

ENTRIES = [
    # ─────────────────────────────────────────────────────────────────────
    # 1xxx — Commercially-pure aluminium
    # ─────────────────────────────────────────────────────────────────────
    {"name": "1100-O",     "composition_wt": {"Al": 99.0, "Si": 0.5, "Fe": 0.5},
     "ys_MPa": 34,  "temper": "O",   "source": "ASM/v2", "value_type": "typical"},
    {"name": "1100-H12",   "composition_wt": {"Al": 99.0, "Si": 0.5, "Fe": 0.5},
     "ys_MPa": 103, "temper": "H12", "source": "ASM/v2", "value_type": "typical"},
    {"name": "1100-H18",   "composition_wt": {"Al": 99.0, "Si": 0.5, "Fe": 0.5},
     "ys_MPa": 152, "temper": "H18", "source": "ASM/v2", "value_type": "typical"},
    {"name": "1050-O",     "composition_wt": {"Al": 99.5, "Si": 0.25, "Fe": 0.25},
     "ys_MPa": 28,  "temper": "O",   "source": "ASM/v2", "value_type": "typical"},
    {"name": "1060-H18",   "composition_wt": {"Al": 99.6, "Si": 0.2, "Fe": 0.2},
     "ys_MPa": 124, "temper": "H18", "source": "ASM/v2", "value_type": "typical"},
    {"name": "1199-O",     "composition_wt": {"Al": 99.99, "Si": 0.006, "Fe": 0.006},
     "ys_MPa": 10,  "temper": "O",   "source": "ASM/v2", "value_type": "typical"},
    {"name": "1350-H19",   "composition_wt": {"Al": 99.5, "Si": 0.1, "Fe": 0.4},
     "ys_MPa": 165, "temper": "H19", "source": "ASTM-B230", "value_type": "minimum"},

    # ─────────────────────────────────────────────────────────────────────
    # 2xxx — Al-Cu / Al-Cu-Mg / Al-Li
    # ─────────────────────────────────────────────────────────────────────
    {"name": "2011-T3",    "composition_wt": {"Al": 92.7, "Cu": 5.5, "Bi": 0.5, "Pb": 0.5, "Fe": 0.7, "Si": 0.4},
     "ys_MPa": 296, "temper": "T3",  "source": "ASM/v2", "value_type": "typical"},
    {"name": "2011-T8",    "composition_wt": {"Al": 92.7, "Cu": 5.5, "Bi": 0.5, "Pb": 0.5, "Fe": 0.7, "Si": 0.4},
     "ys_MPa": 310, "temper": "T8",  "source": "ASM/v2", "value_type": "typical"},
    {"name": "2014-O",     "composition_wt": {"Al": 92.5, "Cu": 4.4, "Si": 0.8, "Mn": 0.8, "Mg": 0.5},
     "ys_MPa": 97,  "temper": "O",   "source": "ASM/v2", "value_type": "typical"},
    {"name": "2014-T4",    "composition_wt": {"Al": 92.5, "Cu": 4.4, "Si": 0.8, "Mn": 0.8, "Mg": 0.5},
     "ys_MPa": 290, "temper": "T4",  "source": "ASM/v2", "value_type": "typical"},
    {"name": "2017-T351",  "composition_wt": {"Al": 93.5, "Cu": 4.0, "Mg": 0.6, "Mn": 0.7, "Si": 0.5, "Fe": 0.7},
     "ys_MPa": 275, "temper": "T351","source": "ASM/v2", "value_type": "typical"},
    {"name": "2024-O",     "composition_wt": {"Al": 93.5, "Cu": 4.4, "Mg": 1.5, "Mn": 0.6},
     "ys_MPa": 75,  "temper": "O",   "source": "ASM/v2", "value_type": "typical"},
    {"name": "2024-T351",  "composition_wt": {"Al": 93.5, "Cu": 4.4, "Mg": 1.5, "Mn": 0.6},
     "ys_MPa": 325, "temper": "T351","source": "MIL-5J", "value_type": "certified"},
    {"name": "2024-T4",    "composition_wt": {"Al": 93.5, "Cu": 4.4, "Mg": 1.5, "Mn": 0.6},
     "ys_MPa": 324, "temper": "T4",  "source": "ASM/v2", "value_type": "typical"},
    {"name": "2024-T8",    "composition_wt": {"Al": 93.5, "Cu": 4.4, "Mg": 1.5, "Mn": 0.6},
     "ys_MPa": 450, "temper": "T8",  "source": "ASM/v2", "value_type": "typical"},
    {"name": "2124-T851",  "composition_wt": {"Al": 93.4, "Cu": 4.4, "Mg": 1.5, "Mn": 0.6, "Fe": 0.3},
     "ys_MPa": 440, "temper": "T851","source": "MIL-5J", "value_type": "certified"},
    {"name": "2219-T87",   "composition_wt": {"Al": 93.0, "Cu": 6.3, "Mn": 0.3, "V": 0.1, "Zr": 0.18, "Ti": 0.06},
     "ys_MPa": 393, "temper": "T87", "source": "ASM/v2", "value_type": "typical"},
    {"name": "2219-T81",   "composition_wt": {"Al": 93.0, "Cu": 6.3, "Mn": 0.3, "V": 0.1, "Zr": 0.18, "Ti": 0.06},
     "ys_MPa": 350, "temper": "T81", "source": "ASM/v2", "value_type": "typical"},
    {"name": "2618-T6",    "composition_wt": {"Al": 93.7, "Cu": 2.3, "Mg": 1.6, "Fe": 1.1, "Ni": 1.0, "Si": 0.18},
     "ys_MPa": 372, "temper": "T6",  "source": "ASM/v2", "value_type": "typical"},
    {"name": "2090-T81",   "composition_wt": {"Al": 95.4, "Cu": 2.7, "Li": 2.1, "Zr": 0.12},
     "ys_MPa": 462, "temper": "T81", "source": "MIL-5J", "value_type": "certified"},
    {"name": "2195-T87",   "composition_wt": {"Al": 94.2, "Cu": 4.0, "Li": 1.0, "Mg": 0.4, "Ag": 0.4, "Zr": 0.12},
     "ys_MPa": 558, "temper": "T87", "source": "ASM/v2", "value_type": "typical"},
    {"name": "2199-T8E74", "composition_wt": {"Al": 94.5, "Cu": 2.6, "Li": 1.6, "Mg": 0.2, "Mn": 0.3, "Zr": 0.09, "Zn": 0.5},
     "ys_MPa": 460, "temper": "T8E74","source": "ASM/v2","value_type": "typical"},

    # ─────────────────────────────────────────────────────────────────────
    # 3xxx — Al-Mn (work-hardened)
    # ─────────────────────────────────────────────────────────────────────
    {"name": "3003-O",     "composition_wt": {"Al": 97.5, "Mn": 1.2, "Cu": 0.12, "Fe": 0.7, "Si": 0.6},
     "ys_MPa": 41,  "temper": "O",   "source": "ASM/v2", "value_type": "typical"},
    {"name": "3003-H14",   "composition_wt": {"Al": 97.5, "Mn": 1.2, "Cu": 0.12, "Fe": 0.7, "Si": 0.6},
     "ys_MPa": 145, "temper": "H14", "source": "ASM/v2", "value_type": "typical"},
    {"name": "3004-O",     "composition_wt": {"Al": 96.4, "Mn": 1.2, "Mg": 1.0, "Si": 0.3, "Fe": 0.7},
     "ys_MPa": 69,  "temper": "O",   "source": "ASM/v2", "value_type": "typical"},
    {"name": "3004-H38",   "composition_wt": {"Al": 96.4, "Mn": 1.2, "Mg": 1.0, "Si": 0.3, "Fe": 0.7},
     "ys_MPa": 248, "temper": "H38", "source": "ASM/v2", "value_type": "typical"},
    {"name": "3104-H19",   "composition_wt": {"Al": 96.4, "Mn": 1.1, "Mg": 1.0, "Si": 0.4, "Fe": 0.6, "Cu": 0.18},
     "ys_MPa": 285, "temper": "H19", "source": "ASM/v2", "value_type": "typical"},

    # ─────────────────────────────────────────────────────────────────────
    # 4xxx — Al-Si (mostly weld filler / cast)
    # ─────────────────────────────────────────────────────────────────────
    {"name": "4043-O",     "composition_wt": {"Al": 94.7, "Si": 5.0, "Fe": 0.3},
     "ys_MPa": 55,  "temper": "O",   "source": "ASM/v2", "value_type": "typical"},
    {"name": "4047-O",     "composition_wt": {"Al": 87.9, "Si": 12.0, "Fe": 0.1},
     "ys_MPa": 70,  "temper": "O",   "source": "ASM/v2", "value_type": "typical"},

    # ─────────────────────────────────────────────────────────────────────
    # 5xxx — Al-Mg (marine, cryogenic)
    # ─────────────────────────────────────────────────────────────────────
    {"name": "5005-H14",   "composition_wt": {"Al": 99.0, "Mg": 0.8, "Fe": 0.7, "Si": 0.3},
     "ys_MPa": 152, "temper": "H14", "source": "ASM/v2", "value_type": "typical"},
    {"name": "5052-O",     "composition_wt": {"Al": 97.0, "Mg": 2.5, "Cr": 0.25, "Si": 0.25},
     "ys_MPa": 90,  "temper": "O",   "source": "ASM/v2", "value_type": "typical"},
    {"name": "5052-H34",   "composition_wt": {"Al": 97.0, "Mg": 2.5, "Cr": 0.25, "Si": 0.25},
     "ys_MPa": 215, "temper": "H34", "source": "ASM/v2", "value_type": "typical"},
    {"name": "5052-H38",   "composition_wt": {"Al": 97.0, "Mg": 2.5, "Cr": 0.25, "Si": 0.25},
     "ys_MPa": 255, "temper": "H38", "source": "ASM/v2", "value_type": "typical"},
    {"name": "5083-H111",  "composition_wt": {"Al": 94.6, "Mg": 4.4, "Mn": 0.7, "Cr": 0.15},
     "ys_MPa": 165, "temper": "H111","source": "ASTM-B928","value_type": "minimum"},
    {"name": "5083-H116",  "composition_wt": {"Al": 94.6, "Mg": 4.4, "Mn": 0.7, "Cr": 0.15},
     "ys_MPa": 215, "temper": "H116","source": "ASTM-B928","value_type": "minimum"},
    {"name": "5086-O",     "composition_wt": {"Al": 95.4, "Mg": 4.0, "Mn": 0.45, "Cr": 0.15},
     "ys_MPa": 117, "temper": "O",   "source": "ASM/v2", "value_type": "typical"},
    {"name": "5086-H116",  "composition_wt": {"Al": 95.4, "Mg": 4.0, "Mn": 0.45, "Cr": 0.15},
     "ys_MPa": 207, "temper": "H116","source": "ASTM-B928","value_type": "minimum"},
    {"name": "5154-O",     "composition_wt": {"Al": 96.0, "Mg": 3.5, "Cr": 0.25, "Mn": 0.1},
     "ys_MPa": 110, "temper": "O",   "source": "ASM/v2", "value_type": "typical"},
    {"name": "5251-H22",   "composition_wt": {"Al": 96.7, "Mg": 2.1, "Mn": 0.4, "Fe": 0.5, "Si": 0.4},
     "ys_MPa": 150, "temper": "H22", "source": "ASM/v2", "value_type": "typical"},
    {"name": "5456-O",     "composition_wt": {"Al": 93.9, "Mg": 5.1, "Mn": 0.8, "Cr": 0.12, "Cu": 0.08},
     "ys_MPa": 160, "temper": "O",   "source": "ASTM-B928","value_type": "minimum"},
    {"name": "5456-H116",  "composition_wt": {"Al": 93.9, "Mg": 5.1, "Mn": 0.8, "Cr": 0.12, "Cu": 0.08},
     "ys_MPa": 230, "temper": "H116","source": "ASTM-B928","value_type": "minimum"},
    {"name": "5754-O",     "composition_wt": {"Al": 96.7, "Mg": 3.0, "Mn": 0.5},
     "ys_MPa": 100, "temper": "O",   "source": "ASM/v2", "value_type": "typical"},

    # ─────────────────────────────────────────────────────────────────────
    # 6xxx — Al-Mg-Si (heat-treatable structural)
    # ─────────────────────────────────────────────────────────────────────
    # NOTE: 6005A-T6 held out for testing (see eval/holdout_alloys.py)
    {"name": "6060-T6",    "composition_wt": {"Al": 98.9, "Mg": 0.5, "Si": 0.4, "Fe": 0.2},
     "ys_MPa": 160, "temper": "T6",  "source": "ASM/v2", "value_type": "typical"},
    {"name": "6061-O",     "composition_wt": {"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2},
     "ys_MPa": 55,  "temper": "O",   "source": "ASM/v2", "value_type": "typical"},
    {"name": "6061-T4",    "composition_wt": {"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2},
     "ys_MPa": 145, "temper": "T4",  "source": "ASM/v2", "value_type": "typical"},
    {"name": "6061-T651",  "composition_wt": {"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2},
     "ys_MPa": 276, "temper": "T651","source": "MIL-5J", "value_type": "certified"},
    {"name": "6063-O",     "composition_wt": {"Al": 98.9, "Mg": 0.7, "Si": 0.4},
     "ys_MPa": 50,  "temper": "O",   "source": "ASM/v2", "value_type": "typical"},
    {"name": "6063-T5",    "composition_wt": {"Al": 98.9, "Mg": 0.7, "Si": 0.4},
     "ys_MPa": 145, "temper": "T5",  "source": "ASM/v2", "value_type": "typical"},
    {"name": "6066-T6",    "composition_wt": {"Al": 96.6, "Mg": 1.0, "Si": 1.3, "Cu": 1.0, "Mn": 0.9},
     "ys_MPa": 359, "temper": "T6",  "source": "ASM/v2", "value_type": "typical"},
    {"name": "6082-T4",    "composition_wt": {"Al": 97.5, "Mg": 0.9, "Si": 1.0, "Mn": 0.6},
     "ys_MPa": 170, "temper": "T4",  "source": "ASM/v2", "value_type": "typical"},
    {"name": "6101-T6",    "composition_wt": {"Al": 99.0, "Mg": 0.55, "Si": 0.5},
     "ys_MPa": 193, "temper": "T6",  "source": "ASM/v2", "value_type": "typical"},
    {"name": "6201-T81",   "composition_wt": {"Al": 98.5, "Mg": 0.7, "Si": 0.7},
     "ys_MPa": 290, "temper": "T81", "source": "ASM/v2", "value_type": "typical"},
    {"name": "6463-T6",    "composition_wt": {"Al": 98.9, "Mg": 0.7, "Si": 0.4},
     "ys_MPa": 215, "temper": "T6",  "source": "ASM/v2", "value_type": "typical"},

    # ─────────────────────────────────────────────────────────────────────
    # 7xxx — Al-Zn-Mg-Cu (high-strength aerospace)
    # ─────────────────────────────────────────────────────────────────────
    {"name": "7005-T53",   "composition_wt": {"Al": 95.5, "Zn": 4.5, "Mg": 1.4, "Mn": 0.4, "Cr": 0.13, "Zr": 0.14, "Ti": 0.04},
     "ys_MPa": 290, "temper": "T53", "source": "ASM/v2", "value_type": "typical"},
    {"name": "7039-T64",   "composition_wt": {"Al": 92.6, "Zn": 4.0, "Mg": 2.8, "Mn": 0.3, "Cr": 0.2},
     "ys_MPa": 380, "temper": "T64", "source": "ASM/v2", "value_type": "typical"},
    {"name": "7049-T73",   "composition_wt": {"Al": 88.9, "Zn": 7.6, "Mg": 2.4, "Cu": 1.4, "Cr": 0.15},
     "ys_MPa": 462, "temper": "T73", "source": "MIL-5J", "value_type": "certified"},
    {"name": "7050-T7451", "composition_wt": {"Al": 89.5, "Zn": 6.2, "Mg": 2.25, "Cu": 2.3, "Zr": 0.12},
     "ys_MPa": 462, "temper": "T7451","source": "MIL-5J","value_type": "certified"},
    {"name": "7050-T7651", "composition_wt": {"Al": 89.5, "Zn": 6.2, "Mg": 2.25, "Cu": 2.3, "Zr": 0.12},
     "ys_MPa": 510, "temper": "T7651","source": "MIL-5J","value_type": "certified"},
    {"name": "7075-O",     "composition_wt": {"Al": 90.0, "Zn": 5.6, "Mg": 2.5, "Cu": 1.6, "Cr": 0.23},
     "ys_MPa": 103, "temper": "O",   "source": "ASM/v2", "value_type": "typical"},
    {"name": "7075-T651",  "composition_wt": {"Al": 90.0, "Zn": 5.6, "Mg": 2.5, "Cu": 1.6, "Cr": 0.23},
     "ys_MPa": 503, "temper": "T651","source": "MIL-5J", "value_type": "certified"},
    {"name": "7075-T7351", "composition_wt": {"Al": 90.0, "Zn": 5.6, "Mg": 2.5, "Cu": 1.6, "Cr": 0.23},
     "ys_MPa": 421, "temper": "T7351","source": "MIL-5J","value_type": "certified"},
    # NOTE: 7150-T7751 held out for testing (see eval/holdout_alloys.py)
    {"name": "7178-T7651", "composition_wt": {"Al": 88.5, "Zn": 6.8, "Mg": 2.7, "Cu": 2.0, "Cr": 0.25},
     "ys_MPa": 500, "temper": "T7651","source": "MIL-5J","value_type": "certified"},
    {"name": "7475-T7351", "composition_wt": {"Al": 90.3, "Zn": 5.7, "Mg": 2.3, "Cu": 1.5, "Cr": 0.2},
     "ys_MPa": 435, "temper": "T7351","source": "MIL-5J","value_type": "certified"},

    # ─────────────────────────────────────────────────────────────────────
    # 8xxx — Al-Li and other special
    # ─────────────────────────────────────────────────────────────────────
    # NOTE: 8090-T8771 held out for testing (see eval/holdout_alloys.py)
    {"name": "8090-T851",  "composition_wt": {"Al": 94.0, "Li": 2.5, "Cu": 1.3, "Mg": 0.9, "Zr": 0.1},
     "ys_MPa": 360, "temper": "T851","source": "ASM/v2","value_type": "typical"},
    {"name": "8081-T6",    "composition_wt": {"Al": 79.0, "Sn": 20.0, "Cu": 1.0},
     "ys_MPa": 70,  "temper": "T6",  "source": "ASM/v2", "value_type": "typical"},

    # ─────────────────────────────────────────────────────────────────────
    # Cast aluminum (Aluminum Association Axxx and 3xx.x series)
    # ─────────────────────────────────────────────────────────────────────
    {"name": "319-T6",     "composition_wt": {"Al": 88.5, "Si": 6.0, "Cu": 3.5, "Fe": 0.8, "Mn": 0.5},
     "ys_MPa": 165, "temper": "T6",  "source": "ASM/v15","value_type": "typical"},
    {"name": "332-T5",     "composition_wt": {"Al": 84.0, "Si": 9.5, "Cu": 3.0, "Mg": 1.0, "Ni": 1.0, "Fe": 1.2},
     "ys_MPa": 195, "temper": "T5",  "source": "ASM/v15","value_type": "typical"},
    {"name": "354-T6",     "composition_wt": {"Al": 90.0, "Si": 9.0, "Cu": 1.8, "Mg": 0.5, "Fe": 0.2},
     "ys_MPa": 285, "temper": "T6",  "source": "ASM/v15","value_type": "typical"},
    {"name": "355-T6",     "composition_wt": {"Al": 91.0, "Si": 5.0, "Cu": 1.2, "Mg": 0.5, "Fe": 0.6, "Mn": 0.5},
     "ys_MPa": 195, "temper": "T6",  "source": "ASM/v15","value_type": "typical"},
    {"name": "380-F",      "composition_wt": {"Al": 86.0, "Si": 8.5, "Cu": 3.5, "Fe": 1.3, "Zn": 1.0, "Ni": 0.5},
     "ys_MPa": 159, "temper": "F",   "source": "ASM/v15","value_type": "typical"},
    {"name": "413-F",      "composition_wt": {"Al": 87.0, "Si": 12.0, "Cu": 0.6, "Fe": 1.3},
     "ys_MPa": 145, "temper": "F",   "source": "ASM/v15","value_type": "typical"},
    {"name": "443-F",      "composition_wt": {"Al": 94.2, "Si": 5.2, "Fe": 0.6, "Mn": 0.4},
     "ys_MPa": 55,  "temper": "F",   "source": "ASM/v15","value_type": "typical"},
    {"name": "535-F",      "composition_wt": {"Al": 92.7, "Mg": 6.8, "Mn": 0.18, "Ti": 0.18, "Be": 0.005},
     "ys_MPa": 138, "temper": "F",   "source": "ASM/v15","value_type": "typical"},
    {"name": "712-F",      "composition_wt": {"Al": 89.3, "Zn": 5.8, "Mg": 0.6, "Cu": 0.5, "Cr": 0.5, "Ti": 0.2},
     "ys_MPa": 165, "temper": "F",   "source": "ASM/v15","value_type": "typical"},
    {"name": "850-T5",     "composition_wt": {"Al": 91.0, "Sn": 6.0, "Cu": 1.0, "Ni": 1.0},
     "ys_MPa": 76,  "temper": "T5",  "source": "ASM/v15","value_type": "typical"},
]
