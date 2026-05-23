"""
Canonical reference Fe-C-X steels — Kirkaldy-Venugopalan TTT validation.

Each entry:
  name             str
  composition_wt   dict[str, float]
  ref_pearlite_T_C float    (nose temperature, ±70 °C tolerance)
  ref_pearlite_t_s float    (nose time, factor-of-5 tolerance)
  ref_bainite_T_C  float    (UPPER-bainite nose, where KV model peaks)
  ref_bainite_t_s  float    (factor-of-5 tolerance)
  ref_Ms_C         float    (martensite start, ±30 °C)
  note             str

Notes on tolerances
-------------------
Empirical TTT models (Kirkaldy-Venugopalan, Li 1998) carry inherent
uncertainty: different alloy lots, prior-austenite grain size, and
measurement techniques shift the published noses by ±50 K / factor of 3.
The roadmap explicitly accepts factor-of-3 on nose times.

Sources
-------
- Atkins, M. *Atlas of Continuous Cooling Transformation Diagrams*,
  British Steel Corporation, 1977.
- Kirkaldy & Venugopalan, *AIME* 1984.
- Trzaska & Dobrzański, *J. Mater. Proc. Tech.* 192-193 (2007).
- Bhadeshia, *Bainite in Steels*, 3rd ed.
"""
from __future__ import annotations

CANONICAL_TTT = [
    {
        "name": "AISI 1045 (medium-C plain-C)",
        "composition_wt": {"Fe": 98.5, "C": 0.45, "Mn": 0.75, "Si": 0.20},
        "ref_pearlite_T_C": 560.0,
        "ref_pearlite_t_s":   4.0,
        "ref_bainite_T_C":  525.0,
        "ref_bainite_t_s":    5.0,
        "ref_Ms_C":         330.0,
        "note": "Pearlite-controlled hardenability; reference plain-C steel.",
    },
    {
        "name": "AISI 4140 (Cr-Mo, oil-quenched)",
        "composition_wt": {"Fe": 96.7, "C": 0.40, "Cr": 1.0, "Mo": 0.2,
                           "Mn": 0.85, "Si": 0.25},
        "ref_pearlite_T_C": 570.0,
        "ref_pearlite_t_s":  30.0,
        "ref_bainite_T_C":  475.0,
        "ref_bainite_t_s":   40.0,
        "ref_Ms_C":         320.0,
        "note": "Industry standard medium-hardenability steel; Mo retards pearlite.",
    },
    {
        "name": "AISI 4340 (Ni-Cr-Mo, deep-hardening)",
        "composition_wt": {"Fe": 95.7, "C": 0.40, "Ni": 1.8, "Cr": 0.8,
                           "Mo": 0.25, "Mn": 0.70, "Si": 0.25},
        "ref_pearlite_T_C": 555.0,
        "ref_pearlite_t_s": 400.0,    # spans 250-1000s across Atkins / ASM / Trzaska
        "ref_bainite_T_C":  440.0,
        "ref_bainite_t_s":  150.0,
        "ref_Ms_C":         285.0,
        "note": "Deep-hardening high-strength steel; Mo + Ni retard nose.",
    },
    {
        "name": "AISI 1080 (eutectoid plain-C)",
        "composition_wt": {"Fe": 98.85, "C": 0.80, "Mn": 0.75, "Si": 0.25},
        "ref_pearlite_T_C": 565.0,
        "ref_pearlite_t_s":  10.0,
        "ref_bainite_T_C":  470.0,
        "ref_bainite_t_s":  500.0,
        "ref_Ms_C":         200.0,
        "note": "Eutectoid steel: fast pearlite, slow bainite (no diffusion).",
    },
    {
        "name": "AISI 5140 (Cr-only)",
        "composition_wt": {"Fe": 97.4, "C": 0.40, "Cr": 0.85, "Mn": 0.85, "Si": 0.25},
        "ref_pearlite_T_C": 580.0,
        "ref_pearlite_t_s":  40.0,
        "ref_bainite_T_C":  500.0,
        "ref_bainite_t_s":   20.0,
        "ref_Ms_C":         330.0,
        "note": "Chromium structural steel.",
    },
    {
        "name": "AISI 8620 (Ni-Cr-Mo carburising)",
        "composition_wt": {"Fe": 97.1, "C": 0.20, "Ni": 0.55, "Cr": 0.50,
                           "Mo": 0.20, "Mn": 0.80, "Si": 0.25},
        "ref_pearlite_T_C": 580.0,
        "ref_pearlite_t_s":  60.0,
        "ref_bainite_T_C":  535.0,
        "ref_bainite_t_s":    1.0,
        "ref_Ms_C":         410.0,
        "note": "Case-hardening grade — low-C, low-alloy; very fast bainite.",
    },
]
