"""
Extended titanium-alloy training entries (Sprint 3).

Sources:
* "Boyer94"   → Boyer, R.R., Welsch, G., Collings, E.W. "Materials
                Properties Handbook: Titanium Alloys", ASM, 1994.
* "Donachie00"→ Donachie, M.J. "Titanium: A Technical Guide", ASM, 2nd ed., 2000.
* "ASTM-Fxxx" → ASTM F-series biomedical implant specifications.
* "ASTM-B348" → ASTM B348 industrial bar/billet (CP & alloy Ti).
* "ASM/v2"    → ASM Handbook Vol. 2.
* "AMS-####"  → AMS aerospace material specs.
"""

ENTRIES = [
    # ─────────────────────────────────────────────────────────────────────
    # CP-Ti grades (ASTM B348, F67)
    # ─────────────────────────────────────────────────────────────────────
    # NOTE: Grade 3 CP-Ti held out for testing (see eval/holdout_alloys.py)
    # Grade 7 = Grade 2 CP-Ti + 0.12–0.25 Pd; same mech. minimums as Grade 2
    # (YS 275 MPa min).  (NB: ASTM Grade 5 is Ti-6Al-4V — not this alloy.)
    {"name": "Grade 7 Ti-0.15Pd","composition_wt": {"Ti": 99.47, "Pd": 0.15, "Fe": 0.2, "O": 0.18},
     "ys_MPa": 275, "temper": "Annealed", "source": "ASTM-B348", "value_type": "minimum"},
    {"name": "Grade 6 Ti-5Al-2.5Sn ELI","composition_wt": {"Ti": 92.5, "Al": 5.0, "Sn": 2.5, "O": 0.12},
     "ys_MPa": 725, "temper": "Annealed", "source": "Boyer94",   "value_type": "typical"},
    {"name": "Grade 11 Ti-Pd",   "composition_wt": {"Ti": 99.5, "Pd": 0.15, "Fe": 0.2, "O": 0.18},
     "ys_MPa": 170, "temper": "Annealed", "source": "ASTM-B348", "value_type": "minimum"},
    {"name": "Grade 12 Ti-0.3Mo-0.8Ni","composition_wt": {"Ti": 98.9, "Mo": 0.3, "Ni": 0.8},
     "ys_MPa": 345, "temper": "Annealed", "source": "ASTM-B348", "value_type": "minimum"},

    # ─────────────────────────────────────────────────────────────────────
    # Alpha and near-alpha alloys
    # ─────────────────────────────────────────────────────────────────────
    {"name": "Ti-8Al-1Mo-1V",    "composition_wt": {"Ti": 90.0, "Al": 8.0, "Mo": 1.0, "V": 1.0},
     "ys_MPa": 880, "temper": "Duplex anneal", "source": "Boyer94", "value_type": "typical"},
    {"name": "IMI-685",          "composition_wt": {"Ti": 86.5, "Al": 6.0, "Zr": 5.0, "Mo": 0.5, "Si": 0.25},
     "ys_MPa": 900, "temper": "β-anneal",      "source": "Donachie00", "value_type": "typical"},
    {"name": "IMI-829",          "composition_wt": {"Ti": 86.4, "Al": 5.5, "Sn": 3.5, "Zr": 3.0, "Nb": 1.0, "Mo": 0.3, "Si": 0.3},
     "ys_MPa": 860, "temper": "β-anneal",      "source": "Donachie00", "value_type": "typical"},
    {"name": "IMI-834",          "composition_wt": {"Ti": 81.0, "Al": 5.8, "Sn": 4.0, "Zr": 3.5, "Nb": 0.7, "Mo": 0.5, "Si": 0.35, "C": 0.06},
     "ys_MPa": 910, "temper": "β-anneal",      "source": "Donachie00", "value_type": "typical"},
    {"name": "Ti-1100",          "composition_wt": {"Ti": 84.0, "Al": 6.0, "Sn": 2.75, "Zr": 4.0, "Mo": 0.4, "Si": 0.45},
     "ys_MPa": 850, "temper": "β-anneal",      "source": "Donachie00", "value_type": "typical"},

    # ─────────────────────────────────────────────────────────────────────
    # α-β alloys (mainstays of industrial Ti)
    # ─────────────────────────────────────────────────────────────────────
    {"name": "Ti-6Al-4V Mill",   "composition_wt": {"Ti": 90.0, "Al": 6.0, "V": 4.0},
     "ys_MPa": 830, "temper": "Mill-annealed", "source": "AMS-4928",  "value_type": "minimum"},
    {"name": "Ti-6Al-4V Beta",   "composition_wt": {"Ti": 90.0, "Al": 6.0, "V": 4.0},
     "ys_MPa": 855, "temper": "β-anneal",      "source": "Boyer94",   "value_type": "typical"},
    # NOTE: Ti-6Al-7Nb held out for testing (see eval/holdout_alloys.py)
    {"name": "Ti-6Al-2Sn-4Zr-2Mo-Si","composition_wt": {"Ti": 85.8, "Al": 6.0, "Sn": 2.0, "Zr": 4.0, "Mo": 2.0, "Si": 0.1},
     "ys_MPa": 970, "temper": "STA",            "source": "Boyer94", "value_type": "typical"},
    {"name": "Ti-4Al-4Mo-2Sn-0.5Si (550)","composition_wt": {"Ti": 89.0, "Al": 4.0, "Mo": 4.0, "Sn": 2.0, "Si": 0.5},
     "ys_MPa": 960, "temper": "STA",            "source": "Donachie00", "value_type": "typical"},
    {"name": "IMI-550",          "composition_wt": {"Ti": 89.0, "Al": 4.0, "Mo": 4.0, "Sn": 2.0, "Si": 0.5},
     "ys_MPa": 1000,"temper": "STA",            "source": "Donachie00", "value_type": "typical"},
    {"name": "IMI-679",          "composition_wt": {"Ti": 80.55, "Al": 2.25, "Sn": 11.0, "Zr": 5.0, "Mo": 1.0, "Si": 0.2},
     "ys_MPa": 1020,"temper": "STA",            "source": "Donachie00", "value_type": "typical"},

    # ─────────────────────────────────────────────────────────────────────
    # Metastable β and β alloys
    # ─────────────────────────────────────────────────────────────────────
    {"name": "Ti-13V-11Cr-3Al",  "composition_wt": {"Ti": 73.0, "V": 13.0, "Cr": 11.0, "Al": 3.0},
     "ys_MPa": 1170,"temper": "STA",          "source": "Boyer94",   "value_type": "typical"},
    {"name": "Ti-15V-3Cr-3Al-3Sn","composition_wt": {"Ti": 76.0, "V": 15.0, "Cr": 3.0, "Al": 3.0, "Sn": 3.0},
     "ys_MPa": 1200,"temper": "STA",          "source": "Boyer94",   "value_type": "typical"},
    {"name": "Beta-21S",         "composition_wt": {"Ti": 78.0, "Mo": 15.0, "Nb": 2.7, "Al": 3.0, "Si": 0.2},
     "ys_MPa": 1240,"temper": "STA",          "source": "Boyer94",   "value_type": "typical"},
    {"name": "Beta-C (Ti-3Al-8V-6Cr-4Mo-4Zr)","composition_wt": {"Ti": 75.0, "Al": 3.0, "V": 8.0, "Cr": 6.0, "Mo": 4.0, "Zr": 4.0},
     "ys_MPa": 1310,"temper": "STA",          "source": "Boyer94",   "value_type": "typical"},
    # NOTE: Ti-LCB held out for testing (see eval/holdout_alloys.py)
    {"name": "Ti-10V-2Fe-3Al",   "composition_wt": {"Ti": 85.0, "V": 10.0, "Fe": 2.0, "Al": 3.0},
     "ys_MPa": 1170,"temper": "STA",          "source": "Boyer94",   "value_type": "typical"},
    {"name": "Beta-CEZ",         "composition_wt": {"Ti": 81.5, "Al": 5.0, "Sn": 2.0, "Zr": 4.0, "Mo": 4.0, "Cr": 2.0, "Fe": 1.0, "Si": 0.25},
     "ys_MPa": 1170,"temper": "STA",          "source": "Donachie00","value_type": "typical"},
    # NOTE: Ti-5553 held out for testing (see eval/holdout_alloys.py)

    # ─────────────────────────────────────────────────────────────────────
    # Biomedical implant alloys (ASTM F-series)
    # ─────────────────────────────────────────────────────────────────────
    # NOTE: Ti-13Nb-13Zr held out for testing (see eval/holdout_alloys.py)
    {"name": "Ti-12Mo-6Zr-2Fe",  "composition_wt": {"Ti": 80.0, "Mo": 12.0, "Zr": 6.0, "Fe": 2.0},
     "ys_MPa": 1000,"temper": "STA",         "source": "ASTM-F1813", "value_type": "minimum"},
    {"name": "Ti-15Mo",          "composition_wt": {"Ti": 85.0, "Mo": 15.0},
     "ys_MPa": 540, "temper": "Annealed",     "source": "ASTM-F2066", "value_type": "minimum"},
    {"name": "Ti-29Nb-13Ta-4.6Zr","composition_wt": {"Ti": 53.4, "Nb": 29.0, "Ta": 13.0, "Zr": 4.6},
     "ys_MPa": 815, "temper": "STA",         "source": "ASTM-F2066", "value_type": "minimum"},

    # ─────────────────────────────────────────────────────────────────────
    # Ti-Aluminide intermetallics
    # ─────────────────────────────────────────────────────────────────────
    {"name": "Gamma-TiAl (4822)","composition_wt": {"Ti": 60.0, "Al": 34.0, "Nb": 4.0, "Cr": 1.0, "B": 0.4},
     "ys_MPa": 450, "temper": "HIP+Aged",    "source": "Donachie00", "value_type": "typical"},

    # ─────────────────────────────────────────────────────────────────────
    # Coverage expansion (2026-07-03) — targets the two gaps exposed by the
    # decontaminated Appendix F OOD test:
    #   (a) annealed / solution-treated β alloys — training had these
    #       compositions only in the STA condition, so annealed β alloys
    #       were over-predicted by 200-300 MPa;
    #   (b) moderate-strength annealed near-α alloys — the model read any
    #       Al≈5-6 chemistry as Ti-6Al-4V-class (~850 MPa).
    # The merge dedup key is (name, temper), so annealed variants of STA
    # training alloys land as new rows, not duplicates.
    # ─────────────────────────────────────────────────────────────────────
    # (a) β / near-β alloys in the annealed (solution-treated) condition
    {"name": "Ti-15V-3Cr-3Al-3Sn","composition_wt": {"Ti": 76.0, "V": 15.0, "Cr": 3.0, "Al": 3.0, "Sn": 3.0},
     "ys_MPa": 770, "temper": "Annealed",    "source": "Boyer94",    "value_type": "typical"},
    {"name": "Beta-21S",         "composition_wt": {"Ti": 79.0, "Mo": 15.0, "Nb": 2.7, "Al": 3.0, "Si": 0.2},
     "ys_MPa": 830, "temper": "Annealed",    "source": "Boyer94",    "value_type": "typical"},
    {"name": "Ti-3Al-8V-6Cr-4Mo-4Zr","composition_wt": {"Ti": 75.0, "Al": 3.0, "V": 8.0, "Cr": 6.0, "Mo": 4.0, "Zr": 4.0},
     "ys_MPa": 860, "temper": "Annealed",    "source": "Boyer94",    "value_type": "typical"},
    {"name": "Ti-13V-11Cr-3Al",  "composition_wt": {"Ti": 73.0, "V": 13.0, "Cr": 11.0, "Al": 3.0},
     "ys_MPa": 830, "temper": "Annealed",    "source": "Boyer94",    "value_type": "typical"},
    # high-strength β STA compositions not previously represented
    {"name": "VT22 (Ti-5Al-5V-5Mo-1Cr-1Fe)","composition_wt": {"Ti": 83.0, "Al": 5.0, "V": 5.0, "Mo": 5.0, "Cr": 1.0, "Fe": 1.0},
     "ys_MPa": 1100,"temper": "STA",         "source": "Boyer94",    "value_type": "typical"},
    {"name": "Ti-15Mo-5Zr-3Al",  "composition_wt": {"Ti": 77.0, "Mo": 15.0, "Zr": 5.0, "Al": 3.0},
     "ys_MPa": 1080,"temper": "STA",         "source": "Boyer94",    "value_type": "typical"},
    # (b) moderate-strength annealed near-α alloys
    {"name": "OT4-1 (Ti-2Al-1.5Mn)","composition_wt": {"Ti": 96.5, "Al": 2.0, "Mn": 1.5},
     "ys_MPa": 550, "temper": "Annealed",    "source": "Boyer94",    "value_type": "typical"},
    {"name": "VT20 (Ti-6Al-2Zr-1Mo-1V)","composition_wt": {"Ti": 90.0, "Al": 6.0, "Zr": 2.0, "Mo": 1.0, "V": 1.0},
     "ys_MPa": 800, "temper": "Annealed",    "source": "Boyer94",    "value_type": "typical"},
]
