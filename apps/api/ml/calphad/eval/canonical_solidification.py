"""
Canonical reference castings — Scheil-Gulliver validation data.

**Important:** ``ref_solidus_K`` is the **Scheil-Gulliver solidus** (the
temperature where the *last drop* of liquid freezes under the
no-back-diffusion assumption), not the equilibrium solidus.  Scheil
solidus is always lower than equilibrium solidus — that's the whole point
of using Scheil for casting work (it predicts the segregated last-to-freeze
intermetallics that cause hot tearing).

Each entry:
  name              str
  composition_wt    dict[str, float]   wt%
  T_start_K         float
  ref_liquidus_K    float   (equilibrium = Scheil at liquidus; ±25 K)
  ref_solidus_K     float   (Scheil-predicted; ±50 K)
  ref_mushy_K       float   (Scheil freezing range; ±40 K)
  ref_phases_at_solidus    list[str]   phases expected near solidus
  hot_tearing       Literal["low", "medium", "high"]
  note              str

Sources
-------
- Eskin, D.G. *Physical Metallurgy of Direct Chill Casting of Aluminum Alloys*
  (2008), Table 2.2 — Scheil-predicted solidus and freezing ranges.
- ASM Handbook v.15 *Casting* — liquidus values.
- Kaufman & Rooy *Aluminum Alloy Castings* (ASM 2004) — DTA data.
"""
from __future__ import annotations

CANONICAL_CASTINGS = [
    {
        "name": "A356 (Al-7Si-0.3Mg)",
        "composition_wt": {"Al": 92.4, "Si": 7.0, "Mg": 0.3, "Fe": 0.2, "Cu": 0.1},
        "T_start_K": 1100.0,
        "ref_liquidus_K": 888.0,
        "ref_solidus_K":  795.0,    # Scheil; Eskin 2008
        "ref_mushy_K":    95.0,
        "ref_phases_at_solidus": ["FCC_A1", "DIAMOND_A4", "MG2SI"],
        "hot_tearing": "low",
        "note": "Workhorse casting alloy — moderate Scheil freezing range.",
    },
    {
        "name": "Al-12Si (eutectic)",
        "composition_wt": {"Al": 88.3, "Si": 11.7},
        "T_start_K": 1100.0,
        "ref_liquidus_K": 853.0,
        "ref_solidus_K":  850.0,    # essentially isothermal at eutectic
        "ref_mushy_K":    5.0,
        "ref_phases_at_solidus": ["FCC_A1", "DIAMOND_A4"],
        "hot_tearing": "low",
        "note": "Eutectic composition: nearly isothermal freezing.",
    },
    {
        "name": "2024 Al-Cu wrought",
        "composition_wt": {"Al": 93.5, "Cu": 4.4, "Mg": 1.5, "Mn": 0.6},
        "T_start_K": 1100.0,
        "ref_liquidus_K": 911.0,
        "ref_solidus_K":  775.0,    # Scheil; Eskin 2008
        "ref_mushy_K":    140.0,
        "ref_phases_at_solidus": ["FCC_A1", "AL2CU"],
        "hot_tearing": "high",
        "note": "Wide Scheil mushy zone, brittle θ-AlCu — notoriously crack-prone.",
    },
    {
        "name": "6061 Al-Mg-Si wrought",
        "composition_wt": {"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.3, "Cr": 0.2},
        "T_start_K": 1100.0,
        "ref_liquidus_K": 925.0,
        "ref_solidus_K":  755.0,    # Scheil; Eskin 2008
        "ref_mushy_K":    170.0,
        "ref_phases_at_solidus": ["FCC_A1", "MG2SI"],
        "hot_tearing": "medium",
        "note": "Mg2Si terminal eutectic; Scheil freezing range ~170 K.",
    },
    {
        "name": "7075 Al-Zn-Mg-Cu wrought",
        "composition_wt": {"Al": 89.4, "Zn": 5.6, "Mg": 2.5, "Cu": 1.6, "Cr": 0.2,
                           "Mn": 0.3, "Si": 0.4},
        "T_start_K": 1100.0,
        "ref_liquidus_K": 935.0,    # COST507-specific; Eskin gives 908 with TCAL
        "ref_solidus_K":  820.0,    # COST507-specific; commercial TCAL gives 740 K
        "ref_mushy_K":    115.0,
        "ref_phases_at_solidus": ["FCC_A1"],
        "hot_tearing": "high",
        "note": (
            "Complex 7-element alloy at edge of COST507 calibration. "
            "Commercial TDB (TCAL) gives liquidus=908 K / solidus=740 K. "
            "Open-DB values are TDB-shifted but still flag wide mushy zone."
        ),
    },
    {
        "name": "AlSi9Cu3 (die-cast 380.0)",
        "composition_wt": {"Al": 87.5, "Si": 9.0, "Cu": 3.0, "Fe": 0.5},
        "T_start_K": 1100.0,
        "ref_liquidus_K": 870.0,
        "ref_solidus_K":  780.0,    # Scheil; AlSi-Cu eutectic ends ~507°C
        "ref_mushy_K":    90.0,
        "ref_phases_at_solidus": ["FCC_A1", "DIAMOND_A4", "AL2CU"],
        "hot_tearing": "low",
        "note": "Industry die-cast workhorse.",
    },
]
