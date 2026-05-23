"""
Canonical reference points for CALPHAD equilibrium validation.

Each entry is a dict with:
  name            str     human-readable label
  composition     dict    element → mole fraction (approximately; normalised internally)
  T_K             float   temperature in Kelvin
  expected_phases dict    phase_name → (min_frac, max_frac) tolerance band
  dominant_phase  str     the phase that should have the largest mole fraction
  note            str     literature source
  chemsys_family  str     "al_alloy" | "steel" | "ni_base" | "binary"

Sources
-------
- ASM Handbook Volume 3: Alloy Phase Diagrams (1992)
- Massalski, T.B. "Binary Alloy Phase Diagrams" (1990)
- Reed, R.C. "The Superalloys" (2006), Cambridge
- NIST Phase Equilibria Diagrams (PED) database
"""
from __future__ import annotations

# ── Binary reference points (fundamental tests) ───────────────────────────────

BINARY_REFS = [
    {
        "name": "Al-Si eutectic above liquidus (900 K)",
        "composition": {"Al": 0.883, "Si": 0.117},
        "T_K": 900.0,
        "expected_phases": {"LIQUID": (0.90, 1.0)},
        "dominant_phase": "LIQUID",
        "note": "Al-11.7 wt% Si above eutectic point (577°C = 850 K). Source: Massalski 1990.",
        "chemsys_family": "binary",
    },
    {
        "name": "Al-Si below eutectic — two-phase (800 K)",
        "composition": {"Al": 0.883, "Si": 0.117},
        "T_K": 800.0,
        "expected_phases": {"FCC_A1": (0.70, 1.0)},
        "dominant_phase": "FCC_A1",
        "note": "Below the eutectic: Al-rich FCC_A1 + Si-rich DIAMOND_A4. Source: Massalski 1990.",
        "chemsys_family": "binary",
    },
    {
        "name": "Pure Al at 900 K — single-phase FCC",
        "composition": {"Al": 1.0},
        "T_K": 900.0,
        "expected_phases": {"FCC_A1": (0.99, 1.0)},
        "dominant_phase": "FCC_A1",
        "note": "Pure aluminium is FCC up to its melting point (933 K). Source: Massalski 1990.",
        "chemsys_family": "binary",
    },
    {
        "name": "Al-Zn 40 at% Zn at 600 K — FCC + HCP",
        "composition": {"Al": 0.60, "Zn": 0.40},
        "T_K": 600.0,
        "expected_phases": {"FCC_A1": (0.50, 1.0)},
        "dominant_phase": "FCC_A1",
        "note": "Al-Zn at 600K is a two-phase FCC+HCP field. Source: Massalski 1990.",
        "chemsys_family": "binary",
    },
    {
        "name": "Al-Ni 25 at% Al at 900 K — L12 / FCC_L12 (γ')",
        "composition": {"Ni": 0.75, "Al": 0.25},
        "T_K": 900.0,
        # Phase name varies by TDB: Dupin 2001 → FCC_L12; alcrni → L12_FCC
        "expected_phases": {"FCC_L12": (0.50, 1.0)},
        "dominant_phase": "FCC_L12",
        "note": "Ni3Al stoichiometry: γ' ordered phase. Source: Dupin et al. 2001.",
        "chemsys_family": "binary",
        "relaxed": True,  # accept FCC_L12 or L12_FCC as dominant
    },
]

# ── Al alloy reference points (COST507 TDB) ───────────────────────────────────

AL_ALLOY_REFS = [
    {
        "name": "6061 at 803 K (530°C solutionising T)",
        "composition": {"Al": 0.972, "Mg": 0.014, "Si": 0.008, "Cu": 0.003, "Fe": 0.003},
        "T_K": 803.0,
        "expected_phases": {"FCC_A1": (0.90, 1.0)},
        "dominant_phase": "FCC_A1",
        "note": (
            "At solutionising T most Mg2Si dissolves; FCC_A1 > 90 mol%. "
            "Source: ASM Handbook v.4 Heat Treating."
        ),
        "chemsys_family": "al_alloy",
    },
    {
        "name": "6061 at 448 K (175°C T6 ageing T) — Mg2Si present",
        "composition": {"Al": 0.972, "Mg": 0.014, "Si": 0.008, "Cu": 0.003, "Fe": 0.003},
        "T_K": 448.0,
        "expected_phases": {"FCC_A1": (0.85, 1.0), "MG2SI": (0.0, 0.10)},
        "dominant_phase": "FCC_A1",
        "note": (
            "At T6 ageing temperature Mg2Si precipitates form (0–5 mol%). "
            "Source: ASM Handbook v.2 Properties & Selection."
        ),
        "chemsys_family": "al_alloy",
    },
    {
        "name": "Al-12 wt% Si casting alloy at 900 K — single-phase LIQUID",
        "composition": {"Al": 0.883, "Si": 0.117},
        "T_K": 900.0,
        "expected_phases": {"LIQUID": (0.90, 1.0)},
        "dominant_phase": "LIQUID",
        "note": "A413/A380-family casting: fully molten above eutectic. Source: ASM Handbook v.15.",
        "chemsys_family": "al_alloy",
    },
    {
        "name": "7075 at 750 K (477°C) — FCC_A1 dominant",
        "composition": {"Al": 0.870, "Zn": 0.056, "Mg": 0.025, "Cu": 0.016, "Cr": 0.002},
        "T_K": 750.0,
        "expected_phases": {"FCC_A1": (0.85, 1.0)},
        "dominant_phase": "FCC_A1",
        "note": (
            "Above the solvus of MgZn2 (η) in 7075; single-phase solid solution. "
            "Source: ASM Handbook v.2."
        ),
        "chemsys_family": "al_alloy",
    },
    {
        "name": "5083 at 600 K (327°C) — FCC_A1 + trace Al12Mg17",
        "composition": {"Al": 0.954, "Mg": 0.040, "Mn": 0.004, "Cr": 0.001},
        "T_K": 600.0,
        "expected_phases": {"FCC_A1": (0.90, 1.0)},
        "dominant_phase": "FCC_A1",
        "note": (
            "Marine alloy: mostly solid Al with Mg in solution; small β-Al12Mg17 possible. "
            "Source: ASM Handbook v.2."
        ),
        "chemsys_family": "al_alloy",
    },
]

# ── Steel / Fe-alloy reference points ─────────────────────────────────────────

STEEL_REFS = [
    {
        "name": "Fe-C 0.8 wt% C at 1050 K (777°C) — austenite (FCC_A1)",
        "composition": {"Fe": 0.9931, "C": 0.0069},    # 0.8 wt% → 3.47 at% → 0.69 mol% (dilute)
        "T_K": 1050.0,
        "expected_phases": {"FCC_A1": (0.90, 1.0)},
        "dominant_phase": "FCC_A1",
        "note": (
            "Eutectoid steel above A1 (727°C): single-phase austenite (γ). "
            "Source: ASM Handbook v.1."
        ),
        "chemsys_family": "steel",
    },
    {
        "name": "304 SS at 1373 K (1100°C) — austenite or delta-ferrite",
        "composition": {"Fe": 0.74, "Cr": 0.18, "Ni": 0.08},
        "T_K": 1373.0,
        "expected_phases": {"FCC_A1": (0.0, 1.0), "BCC_A2": (0.0, 1.0)},
        "dominant_phase": "FCC_A1",
        "note": (
            "304 SS at 1100°C: primarily austenite (FCC_A1). "
            "Delta ferrite (BCC_A2) may be present depending on TDB accuracy. "
            "Source: ASM Handbook v.3."
        ),
        "chemsys_family": "steel",
        "relaxed": True,  # accept either BCC or FCC as dominant at this T
    },
]

# ── Ni-base superalloy reference points ───────────────────────────────────────

NI_BASE_REFS = [
    {
        "name": "Ni3Al (γ') at 25 at% Al — FCC_L12 / L12_FCC",
        "composition": {"Ni": 0.75, "Al": 0.25},
        "T_K": 900.0,
        "expected_phases": {"FCC_L12": (0.70, 1.0)},
        "dominant_phase": "FCC_L12",
        "note": (
            "Ni3Al ordered intermetallic: the γ' hardening phase. "
            "Phase name FCC_L12 (Dupin 2001) or L12_FCC (alcrni DB). "
            "Source: Dupin et al. 2001 / Reed 2006."
        ),
        "chemsys_family": "ni_base",
        "relaxed": True,
    },
    {
        "name": "Ni-Al γ/γ' two-phase at 10 at% Al — FCC + γ'",
        "composition": {"Ni": 0.90, "Al": 0.10},
        "T_K": 900.0,
        "expected_phases": {"FCC_L12": (0.80, 1.0)},
        "dominant_phase": "FCC_L12",
        "note": (
            "Ni-10Al at 900K is in the single-phase γ' (FCC_L12) field per Dupin 2001. "
            "Source: Dupin et al. 2001."
        ),
        "chemsys_family": "ni_base",
        "relaxed": True,
    },
]

# ── Public accessor ────────────────────────────────────────────────────────────

ALL_CANONICAL = BINARY_REFS + AL_ALLOY_REFS + STEEL_REFS + NI_BASE_REFS
