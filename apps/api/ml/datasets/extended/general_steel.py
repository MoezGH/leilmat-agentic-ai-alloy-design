"""
Extended general-steel training entries (Sprint 3).

These extend the GENERAL_STEEL_ALLOYS set used by the fall-through
``general_steel_ys_rf`` model.  Covers carbon, low-alloy, stainless, PH,
duplex, and HSLA steels — the "everyday engineering" range that the
matbench_steels (ultra-high-strength) model can't cover.

Sources:
* "ASM/v1"   → ASM Handbook Vol. 1 — Properties and Selection: Irons, Steels,
               and High-Performance Alloys.
* "ASM/v4"   → ASM Handbook Vol. 4 — Heat Treating.
* "ASTM-A###"→ ASTM A-series structural / mechanical-tubing / stainless-steel
               specifications.
* "AISI-SAE" → SAE J404 / J1086 chemical-composition cross-reference.
* "MIL-5J"   → MIL-HDBK-5J aerospace-grade certified properties.
"""

ENTRIES = [
    # ─────────────────────────────────────────────────────────────────────
    # AISI 10xx — Plain-carbon steels
    # ─────────────────────────────────────────────────────────────────────
    {"name": "AISI 1010 HR",   "composition_wt": {"Fe": 99.3, "C": 0.10, "Mn": 0.45, "Si": 0.20},
     "ys_MPa": 180, "temper": "Hot-rolled",      "source": "ASM/v1", "value_type": "typical"},
    {"name": "AISI 1018 CD",   "composition_wt": {"Fe": 98.9, "C": 0.18, "Mn": 0.75, "Si": 0.15},
     "ys_MPa": 370, "temper": "Cold-drawn",      "source": "ASM/v1", "value_type": "typical"},
    {"name": "AISI 1020 HR",   "composition_wt": {"Fe": 99.0, "C": 0.20, "Mn": 0.45, "Si": 0.20},
     "ys_MPa": 220, "temper": "Hot-rolled",      "source": "ASM/v1", "value_type": "typical"},
    {"name": "AISI 1025 N",    "composition_wt": {"Fe": 98.8, "C": 0.25, "Mn": 0.45, "Si": 0.20},
     "ys_MPa": 280, "temper": "Normalised",      "source": "ASM/v1", "value_type": "typical"},
    {"name": "AISI 1030 N",    "composition_wt": {"Fe": 98.7, "C": 0.30, "Mn": 0.75, "Si": 0.20},
     "ys_MPa": 345, "temper": "Normalised",      "source": "ASM/v1", "value_type": "typical"},
    {"name": "AISI 1040 N",    "composition_wt": {"Fe": 98.4, "C": 0.40, "Mn": 0.75, "Si": 0.20},
     "ys_MPa": 415, "temper": "Normalised",      "source": "ASM/v1", "value_type": "typical"},
    {"name": "AISI 1050 N",    "composition_wt": {"Fe": 98.2, "C": 0.50, "Mn": 0.75, "Si": 0.20},
     "ys_MPa": 490, "temper": "Normalised",      "source": "ASM/v1", "value_type": "typical"},
    {"name": "AISI 1060 N",    "composition_wt": {"Fe": 98.0, "C": 0.60, "Mn": 0.75, "Si": 0.20},
     "ys_MPa": 555, "temper": "Normalised",      "source": "ASM/v1", "value_type": "typical"},
    {"name": "AISI 1080 N",    "composition_wt": {"Fe": 97.8, "C": 0.80, "Mn": 0.75, "Si": 0.20},
     "ys_MPa": 525, "temper": "Normalised",      "source": "ASM/v1", "value_type": "typical"},
    {"name": "AISI 1095 N",    "composition_wt": {"Fe": 97.5, "C": 0.95, "Mn": 0.40, "Si": 0.20},
     "ys_MPa": 525, "temper": "Normalised",      "source": "ASM/v1", "value_type": "typical"},

    # ─────────────────────────────────────────────────────────────────────
    # AISI 41xx / 43xx — Cr-Mo and Ni-Cr-Mo low-alloy
    # ─────────────────────────────────────────────────────────────────────
    {"name": "AISI 4130 N",    "composition_wt": {"Fe": 97.5, "C": 0.30, "Mn": 0.5, "Si": 0.25, "Cr": 0.95, "Mo": 0.2},
     "ys_MPa": 460, "temper": "Normalised",      "source": "ASM/v1", "value_type": "typical"},
    {"name": "AISI 4130 Q&T",  "composition_wt": {"Fe": 97.5, "C": 0.30, "Mn": 0.5, "Si": 0.25, "Cr": 0.95, "Mo": 0.2},
     "ys_MPa": 700, "temper": "Q&T",             "source": "ASM/v4", "value_type": "typical"},
    {"name": "AISI 4140 N",    "composition_wt": {"Fe": 96.7, "C": 0.40, "Mn": 0.85, "Si": 0.25, "Cr": 1.0, "Mo": 0.2},
     "ys_MPa": 655, "temper": "Normalised",      "source": "ASM/v1", "value_type": "typical"},
    {"name": "AISI 4140 Q&T",  "composition_wt": {"Fe": 96.7, "C": 0.40, "Mn": 0.85, "Si": 0.25, "Cr": 1.0, "Mo": 0.2},
     "ys_MPa": 875, "temper": "Q&T",             "source": "ASM/v4", "value_type": "typical"},
    {"name": "AISI 4145 Q&T",  "composition_wt": {"Fe": 96.6, "C": 0.45, "Mn": 0.85, "Si": 0.25, "Cr": 1.0, "Mo": 0.2},
     "ys_MPa": 930, "temper": "Q&T",             "source": "ASM/v4", "value_type": "typical"},
    {"name": "AISI 4340 N",    "composition_wt": {"Fe": 95.7, "C": 0.40, "Ni": 1.8, "Cr": 0.8, "Mo": 0.25, "Mn": 0.70, "Si": 0.25},
     "ys_MPa": 710, "temper": "Normalised",      "source": "ASM/v1", "value_type": "typical"},
    {"name": "AISI 4340 Q&T",  "composition_wt": {"Fe": 95.7, "C": 0.40, "Ni": 1.8, "Cr": 0.8, "Mo": 0.25, "Mn": 0.70, "Si": 0.25},
     "ys_MPa": 1140,"temper": "Q&T",             "source": "ASM/v4", "value_type": "typical"},
    {"name": "AISI 4615 Q&T",  "composition_wt": {"Fe": 96.7, "C": 0.15, "Mn": 0.5, "Si": 0.25, "Ni": 1.83, "Mo": 0.5},
     "ys_MPa": 595, "temper": "Q&T",             "source": "ASM/v4", "value_type": "typical"},
    {"name": "AISI 4820 Q&T",  "composition_wt": {"Fe": 95.6, "C": 0.20, "Mn": 0.6, "Si": 0.25, "Ni": 3.5, "Mo": 0.25},
     "ys_MPa": 690, "temper": "Q&T",             "source": "ASM/v4", "value_type": "typical"},
    {"name": "AISI 5140 Q&T",  "composition_wt": {"Fe": 97.4, "C": 0.40, "Cr": 0.85, "Mn": 0.85, "Si": 0.25},
     "ys_MPa": 760, "temper": "Q&T",             "source": "ASM/v4", "value_type": "typical"},
    {"name": "AISI 5160 Q&T",  "composition_wt": {"Fe": 97.0, "C": 0.60, "Mn": 0.9, "Si": 0.25, "Cr": 0.85},
     "ys_MPa": 1000,"temper": "Q&T",             "source": "ASM/v4", "value_type": "typical"},
    {"name": "AISI 6150 Q&T",  "composition_wt": {"Fe": 97.0, "C": 0.50, "Mn": 0.85, "Si": 0.25, "Cr": 0.95, "V": 0.15},
     "ys_MPa": 1050,"temper": "Q&T",             "source": "ASM/v4", "value_type": "typical"},
    {"name": "AISI 8620 N",    "composition_wt": {"Fe": 97.1, "C": 0.20, "Mn": 0.80, "Si": 0.25, "Ni": 0.55, "Cr": 0.50, "Mo": 0.20},
     "ys_MPa": 360, "temper": "Normalised",      "source": "ASM/v1", "value_type": "typical"},
    {"name": "AISI 8620 Carb", "composition_wt": {"Fe": 97.1, "C": 0.20, "Mn": 0.80, "Si": 0.25, "Ni": 0.55, "Cr": 0.50, "Mo": 0.20},
     "ys_MPa": 540, "temper": "Carburised",      "source": "ASM/v4", "value_type": "typical"},
    {"name": "AISI 8740 Q&T",  "composition_wt": {"Fe": 96.4, "C": 0.40, "Mn": 0.85, "Si": 0.25, "Ni": 0.55, "Cr": 0.50, "Mo": 0.25},
     "ys_MPa": 825, "temper": "Q&T",             "source": "ASM/v4", "value_type": "typical"},
    {"name": "AISI 9260 Q&T",  "composition_wt": {"Fe": 96.0, "C": 0.60, "Mn": 0.85, "Si": 2.0, "Cr": 0.0},
     "ys_MPa": 1140,"temper": "Q&T",             "source": "ASM/v4", "value_type": "typical"},

    # ─────────────────────────────────────────────────────────────────────
    # Austenitic stainless steels (304/316 families)
    # ─────────────────────────────────────────────────────────────────────
    {"name": "AISI 301 Ann",   "composition_wt": {"Fe": 73.0, "Cr": 17.0, "Ni": 7.0, "Mn": 2.0, "Si": 0.75, "C": 0.15},
     "ys_MPa": 275, "temper": "Annealed",        "source": "ASTM-A276", "value_type": "minimum"},
    {"name": "AISI 304 Ann",   "composition_wt": {"Fe": 70.0, "Cr": 19.0, "Ni": 9.0, "Mn": 1.5, "Si": 0.5, "C": 0.07},
     "ys_MPa": 215, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "AISI 304L Ann",  "composition_wt": {"Fe": 70.3, "Cr": 19.0, "Ni": 9.0, "Mn": 1.5, "Si": 0.5, "C": 0.025},
     "ys_MPa": 170, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "AISI 309 Ann",   "composition_wt": {"Fe": 60.0, "Cr": 23.0, "Ni": 14.0, "Mn": 2.0, "Si": 0.75, "C": 0.15},
     "ys_MPa": 205, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "AISI 310 Ann",   "composition_wt": {"Fe": 53.0, "Cr": 25.0, "Ni": 20.0, "Mn": 2.0, "Si": 0.75, "C": 0.20},
     "ys_MPa": 205, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "AISI 316 Ann",   "composition_wt": {"Fe": 66.5, "Cr": 17.0, "Ni": 12.0, "Mo": 2.5, "Mn": 1.5, "Si": 0.5, "C": 0.07},
     "ys_MPa": 205, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "AISI 316L Ann",  "composition_wt": {"Fe": 66.8, "Cr": 17.0, "Ni": 12.0, "Mo": 2.5, "Mn": 1.5, "Si": 0.5, "C": 0.025},
     "ys_MPa": 170, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "AISI 316Ti Ann", "composition_wt": {"Fe": 66.5, "Cr": 17.0, "Ni": 12.0, "Mo": 2.5, "Ti": 0.5, "Mn": 1.5, "Si": 0.5, "C": 0.05},
     "ys_MPa": 240, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "AISI 317L Ann",  "composition_wt": {"Fe": 63.0, "Cr": 19.0, "Ni": 13.0, "Mo": 3.5, "Mn": 1.5, "Si": 0.5, "C": 0.025},
     "ys_MPa": 205, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "AISI 321 Ann",   "composition_wt": {"Fe": 70.0, "Cr": 18.0, "Ni": 10.5, "Ti": 0.5, "Mn": 1.5, "Si": 0.5, "C": 0.07},
     "ys_MPa": 205, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "AISI 347 Ann",   "composition_wt": {"Fe": 69.0, "Cr": 18.0, "Ni": 11.0, "Nb": 0.8, "Mn": 1.5, "Si": 0.5, "C": 0.07},
     "ys_MPa": 205, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "AISI 904L Ann",  "composition_wt": {"Fe": 47.0, "Cr": 21.0, "Ni": 25.0, "Mo": 4.5, "Cu": 1.5, "Mn": 1.0, "Si": 0.5, "C": 0.02},
     "ys_MPa": 215, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},

    # ─────────────────────────────────────────────────────────────────────
    # Ferritic stainless
    # ─────────────────────────────────────────────────────────────────────
    {"name": "AISI 409 Ann",   "composition_wt": {"Fe": 87.0, "Cr": 11.0, "Ti": 0.5, "Mn": 1.0, "Si": 0.5, "C": 0.08, "Ni": 0.5},
     "ys_MPa": 205, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "AISI 430 Ann",   "composition_wt": {"Fe": 80.0, "Cr": 17.0, "Mn": 1.0, "Si": 0.5, "C": 0.10, "Ni": 0.5},
     "ys_MPa": 240, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "AISI 434 Ann",   "composition_wt": {"Fe": 79.5, "Cr": 17.0, "Mo": 1.0, "Mn": 1.0, "Si": 0.5, "C": 0.10, "Ni": 0.5},
     "ys_MPa": 240, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "AISI 444 Ann",   "composition_wt": {"Fe": 79.0, "Cr": 18.5, "Mo": 2.0, "Ti": 0.4, "Nb": 0.3, "Mn": 1.0, "Si": 0.5, "C": 0.025, "Ni": 0.5},
     "ys_MPa": 275, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "AISI 446 Ann",   "composition_wt": {"Fe": 73.0, "Cr": 25.0, "Mn": 1.0, "Si": 0.5, "C": 0.20, "Ni": 0.5},
     "ys_MPa": 275, "temper": "Annealed",        "source": "ASTM-A240", "value_type": "minimum"},

    # ─────────────────────────────────────────────────────────────────────
    # Martensitic stainless
    # ─────────────────────────────────────────────────────────────────────
    {"name": "AISI 410 Ann",   "composition_wt": {"Fe": 86.0, "Cr": 12.5, "Mn": 1.0, "Si": 0.5, "C": 0.12, "Ni": 0.5},
     "ys_MPa": 275, "temper": "Annealed",        "source": "ASTM-A276", "value_type": "minimum"},
    {"name": "AISI 410 Q&T",   "composition_wt": {"Fe": 86.0, "Cr": 12.5, "Mn": 1.0, "Si": 0.5, "C": 0.12, "Ni": 0.5},
     "ys_MPa": 760, "temper": "Q&T",             "source": "ASTM-A276", "value_type": "typical"},
    {"name": "AISI 416 Q&T",   "composition_wt": {"Fe": 85.5, "Cr": 12.5, "Mn": 1.0, "Si": 1.0, "S": 0.3, "C": 0.15, "Ni": 0.5},
     "ys_MPa": 690, "temper": "Q&T",             "source": "ASTM-A276", "value_type": "typical"},
    {"name": "AISI 420 Q&T",   "composition_wt": {"Fe": 85.0, "Cr": 13.0, "Mn": 1.0, "Si": 1.0, "C": 0.35, "Ni": 0.5},
     "ys_MPa": 1240,"temper": "Q&T",             "source": "ASTM-A276", "value_type": "typical"},
    {"name": "AISI 422 Q&T",   "composition_wt": {"Fe": 83.0, "Cr": 12.0, "Ni": 0.8, "Mo": 1.0, "W": 1.0, "V": 0.25, "C": 0.22, "Mn": 0.8, "Si": 0.4},
     "ys_MPa": 825, "temper": "Q&T",             "source": "ASM/v1",     "value_type": "typical"},
    {"name": "AISI 431 Q&T",   "composition_wt": {"Fe": 81.0, "Cr": 16.0, "Ni": 2.0, "Mn": 1.0, "Si": 0.5, "C": 0.18},
     "ys_MPa": 655, "temper": "Q&T",             "source": "ASTM-A276", "value_type": "typical"},
    {"name": "AISI 440A Q&T",  "composition_wt": {"Fe": 82.5, "Cr": 16.5, "Mo": 0.6, "C": 0.65, "Mn": 1.0, "Si": 0.5, "Ni": 0.5},
     "ys_MPa": 1380,"temper": "Q&T",             "source": "ASM/v1",     "value_type": "typical"},
    {"name": "AISI 440C Q&T",  "composition_wt": {"Fe": 80.5, "Cr": 17.0, "Mo": 0.6, "C": 1.05, "Mn": 1.0, "Si": 0.5, "Ni": 0.5},
     "ys_MPa": 1900,"temper": "Q&T",             "source": "ASM/v1",     "value_type": "typical"},

    # ─────────────────────────────────────────────────────────────────────
    # Precipitation-hardening (PH) stainless
    # ─────────────────────────────────────────────────────────────────────
    {"name": "17-4 PH H900",   "composition_wt": {"Fe": 73.0, "Cr": 16.5, "Ni": 4.0, "Cu": 4.0, "Nb": 0.3, "Mn": 1.0, "Si": 0.5, "C": 0.04},
     "ys_MPa": 1170,"temper": "H900",          "source": "AMS-5643", "value_type": "minimum"},
    {"name": "17-4 PH H1025",  "composition_wt": {"Fe": 73.0, "Cr": 16.5, "Ni": 4.0, "Cu": 4.0, "Nb": 0.3, "Mn": 1.0, "Si": 0.5, "C": 0.04},
     "ys_MPa": 1000,"temper": "H1025",         "source": "AMS-5643", "value_type": "minimum"},
    {"name": "17-4 PH H1150",  "composition_wt": {"Fe": 73.0, "Cr": 16.5, "Ni": 4.0, "Cu": 4.0, "Nb": 0.3, "Mn": 1.0, "Si": 0.5, "C": 0.04},
     "ys_MPa": 795, "temper": "H1150",         "source": "AMS-5643", "value_type": "minimum"},
    {"name": "17-7 PH TH1050", "composition_wt": {"Fe": 73.0, "Cr": 17.0, "Ni": 7.0, "Al": 1.2, "Mn": 1.0, "Si": 0.5, "C": 0.07},
     "ys_MPa": 1170,"temper": "TH1050",        "source": "AMS-5528", "value_type": "minimum"},
    {"name": "15-5 PH H900",   "composition_wt": {"Fe": 74.0, "Cr": 15.0, "Ni": 4.7, "Cu": 3.5, "Nb": 0.3, "Mn": 1.0, "Si": 0.5, "C": 0.04},
     "ys_MPa": 1170,"temper": "H900",          "source": "AMS-5659", "value_type": "minimum"},
    {"name": "PH 13-8 Mo H1000","composition_wt": {"Fe": 73.0, "Cr": 13.0, "Ni": 8.0, "Mo": 2.2, "Al": 1.1, "Mn": 0.1, "Si": 0.1, "C": 0.04},
     "ys_MPa": 1340,"temper": "H1000",         "source": "AMS-5629", "value_type": "minimum"},
    {"name": "A-286 Aged",     "composition_wt": {"Fe": 53.5, "Ni": 25.5, "Cr": 14.7, "Mo": 1.25, "Ti": 2.1, "Al": 0.2, "V": 0.3, "Mn": 1.4, "Si": 0.5, "C": 0.05, "B": 0.005},
     "ys_MPa": 660, "temper": "Aged",          "source": "AMS-5731", "value_type": "minimum"},
    {"name": "Custom 465 H950","composition_wt": {"Fe": 73.5, "Cr": 11.5, "Ni": 11.0, "Mo": 1.0, "Ti": 1.6, "Al": 0.05, "C": 0.015},
     "ys_MPa": 1620,"temper": "H950",          "source": "AMS-5936", "value_type": "minimum"},

    # ─────────────────────────────────────────────────────────────────────
    # Duplex stainless
    # ─────────────────────────────────────────────────────────────────────
    {"name": "Duplex 2205 Ann","composition_wt": {"Fe": 67.5, "Cr": 22.0, "Ni": 5.5, "Mo": 3.0, "Mn": 1.5, "N": 0.16, "Si": 0.5, "C": 0.02},
     "ys_MPa": 450, "temper": "Annealed",      "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "Duplex 2304 Ann","composition_wt": {"Fe": 71.5, "Cr": 23.0, "Ni": 4.0, "Mo": 0.3, "Mn": 1.5, "N": 0.10, "Si": 0.5, "C": 0.025},
     "ys_MPa": 400, "temper": "Annealed",      "source": "ASTM-A240", "value_type": "minimum"},
    {"name": "Duplex 2507 Ann","composition_wt": {"Fe": 62.5, "Cr": 25.0, "Ni": 7.0, "Mo": 4.0, "Mn": 1.0, "N": 0.27, "Si": 0.5, "C": 0.02},
     "ys_MPa": 550, "temper": "Annealed",      "source": "ASTM-A240", "value_type": "minimum"},

    # ─────────────────────────────────────────────────────────────────────
    # Tool steels (lower-alloy ones still in domain; high-alloy excluded)
    # ─────────────────────────────────────────────────────────────────────
    {"name": "O1 Q&T",         "composition_wt": {"Fe": 96.0, "C": 0.94, "Mn": 1.2, "Cr": 0.5, "W": 0.5, "V": 0.2, "Si": 0.3},
     "ys_MPa": 1380,"temper": "Q&T",          "source": "ASM/v1", "value_type": "typical"},
    {"name": "A2 Q&T",         "composition_wt": {"Fe": 90.0, "C": 1.0, "Mn": 0.7, "Cr": 5.0, "Mo": 1.1, "V": 0.25, "Si": 0.3},
     "ys_MPa": 1600,"temper": "Q&T",          "source": "ASM/v1", "value_type": "typical"},
    {"name": "S7 Q&T",         "composition_wt": {"Fe": 92.0, "C": 0.5, "Cr": 3.25, "Mo": 1.4, "Mn": 0.7, "Si": 0.3},
     "ys_MPa": 1450,"temper": "Q&T",          "source": "ASM/v1", "value_type": "typical"},

    # ─────────────────────────────────────────────────────────────────────
    # HSLA / pressure-vessel / structural
    # ─────────────────────────────────────────────────────────────────────
    {"name": "ASTM A36",       "composition_wt": {"Fe": 98.9, "C": 0.26, "Mn": 1.0, "Si": 0.4, "Cu": 0.2, "P": 0.04, "S": 0.05},
     "ys_MPa": 250, "temper": "As-rolled",     "source": "ASTM-A36",  "value_type": "minimum"},
    {"name": "ASTM A516 Gr70", "composition_wt": {"Fe": 98.5, "C": 0.28, "Mn": 1.0, "Si": 0.3, "P": 0.025, "S": 0.025},
     "ys_MPa": 260, "temper": "Normalised",    "source": "ASTM-A516", "value_type": "minimum"},
    {"name": "ASTM A572 Gr50", "composition_wt": {"Fe": 98.6, "C": 0.23, "Mn": 1.35, "Si": 0.4, "Cu": 0.2, "Nb": 0.05, "V": 0.05},
     "ys_MPa": 345, "temper": "As-rolled",     "source": "ASTM-A572", "value_type": "minimum"},
    {"name": "ASTM A588 Gr50", "composition_wt": {"Fe": 98.0, "C": 0.19, "Mn": 1.25, "Si": 0.4, "Cu": 0.4, "Cr": 0.5, "Ni": 0.5, "V": 0.05},
     "ys_MPa": 345, "temper": "As-rolled",     "source": "ASTM-A588", "value_type": "minimum"},
    {"name": "ASTM A656 Gr80", "composition_wt": {"Fe": 98.0, "C": 0.18, "Mn": 1.65, "Si": 0.6, "Nb": 0.1, "V": 0.08, "Ti": 0.05, "Al": 0.05},
     "ys_MPa": 550, "temper": "Controlled-roll","source": "ASTM-A656","value_type": "minimum"},
    {"name": "HY-80",          "composition_wt": {"Fe": 95.5, "C": 0.18, "Mn": 0.35, "Si": 0.25, "Ni": 2.75, "Cr": 1.4, "Mo": 0.45},
     "ys_MPa": 550, "temper": "Q&T",           "source": "MIL-S-16216","value_type": "minimum"},
    {"name": "HY-100",         "composition_wt": {"Fe": 95.0, "C": 0.18, "Mn": 0.35, "Si": 0.25, "Ni": 3.0, "Cr": 1.55, "Mo": 0.55},
     "ys_MPa": 690, "temper": "Q&T",           "source": "MIL-S-16216","value_type": "minimum"},
    {"name": "HY-130",         "composition_wt": {"Fe": 94.0, "C": 0.12, "Mn": 0.75, "Si": 0.25, "Ni": 5.0, "Cr": 0.6, "Mo": 0.55, "V": 0.05},
     "ys_MPa": 895, "temper": "Q&T",           "source": "MIL-S-24371","value_type": "minimum"},
]
