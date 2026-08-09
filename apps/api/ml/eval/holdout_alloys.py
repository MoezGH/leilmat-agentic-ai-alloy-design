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
        "expected_in_domain": True,
        "note": (
            "Second-gen Al-Li for aerospace. Marked OOD before Sprint 3; "
            "now in-domain since the expanded training set contains other "
            "Al-Li alloys (2090-T81, 2195-T87, 2199-T8E74, 8090-T851)."
        ),
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
        "expected_in_domain": True,
        "note": (
            "Biomedical β-alloy. Marked OOD before Sprint 3; now in-domain "
            "since the expanded training set contains other biomedical β-Ti "
            "(Ti-29Nb-13Ta-4.6Zr, Ti-15Mo, Ti-12Mo-6Zr-2Fe)."
        ),
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
        "expected_in_domain": True,
        "note": (
            "High-Cr (30%) solid solution. Marked OOD before Sprint 3; "
            "now in-domain since the expanded training set contains other "
            "high-Cr Ni alloys (Hastelloy C-22 22Cr, Hastelloy G-30 30Cr, "
            "Inconel 601 23Cr)."
        ),
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
# External OOD datasheets (Appendix F)
#
# Alloys sourced exclusively from published commercial datasheets (MatWeb,
# ASM Alloy Digest, manufacturer PDFs).
#
# CONTAMINATION GUARD (2026-07-03): the first version of these lists reused
# alloys that were already in the training rosters (2024-T4, Waspaloy,
# Ti-3Al-2.5V, …), so Appendix F was silently re-testing training data.
# Every alloy below has been verified absent — by name AND composition —
# from alloy_datasets.py (training) and from the holdout sets above.
# When editing, re-verify against both.
#
# Compositions are in weight percent (same convention as the holdout sets).
# ─────────────────────────────────────────────────────────────────────────

ALUMINUM_OOD_EXTERNAL: list[dict] = [
    {
        "name": "7010-T7651",
        "composition_wt": {"Al": 89.23, "Zn": 6.2, "Mg": 2.4, "Cu": 1.8, "Zr": 0.12,
                           "Mn": 0.10, "Fe": 0.15},
        "ys_MPa": 448,
        "temper": "T7651",
        "expected_in_domain": True,
        "note": "Airbus wing-skin 7xxx (Zr-stabilised, no Cr). Source: ASM Alloy Digest.",
    },
    {
        "name": "7055-T7751",
        "composition_wt": {"Al": 87.4, "Zn": 8.0, "Mg": 2.05, "Cu": 2.3, "Zr": 0.11,
                           "Fe": 0.15},
        "ys_MPa": 614,
        "temper": "T7751",
        "expected_in_domain": True,
        "note": "Boeing 777 upper wing skin; highest-strength commercial 7xxx plate. "
                "Source: AMS 4206 / Alcoa datasheet.",
    },
    {
        "name": "7449-T7951",
        "composition_wt": {"Al": 87.6, "Zn": 8.1, "Mg": 2.1, "Cu": 1.9, "Zr": 0.12,
                           "Fe": 0.15},
        "ys_MPa": 546,
        "temper": "T7951",
        "expected_in_domain": True,
        "note": "A380 upper-wing plate (Constellium). Source: ASM Alloy Digest.",
    },
    {
        "name": "6013-T6",
        "composition_wt": {"Al": 96.8, "Mg": 0.95, "Si": 0.75, "Cu": 0.9, "Mn": 0.35,
                           "Fe": 0.25},
        "ys_MPa": 340,
        "temper": "T6",
        "expected_in_domain": True,
        "note": "Cu-bearing 6xxx aerospace sheet (weldable 2024 substitute). "
                "Source: Alcoa datasheet.",
    },
    {
        "name": "6151-T6",
        "composition_wt": {"Al": 97.9, "Si": 0.9, "Mg": 0.6, "Cr": 0.25, "Fe": 0.3},
        "ys_MPa": 295,
        "temper": "T6",
        "expected_in_domain": True,
        "note": "Forging alloy (automotive/aircraft fittings). Source: ASM Handbook v.2.",
    },
    {
        "name": "6351-T6",
        "composition_wt": {"Al": 97.5, "Si": 1.0, "Mg": 0.6, "Mn": 0.6, "Fe": 0.25},
        "ys_MPa": 285,
        "temper": "T6",
        "expected_in_domain": True,
        "note": "Structural extrusion (Mn-bearing 6xxx, no Cr). Source: MatWeb.",
    },
    {
        "name": "2025-T6",
        "composition_wt": {"Al": 93.6, "Cu": 4.4, "Si": 0.8, "Mn": 0.8, "Fe": 0.4},
        "ys_MPa": 255,
        "temper": "T6",
        "expected_in_domain": True,
        "note": "Propeller-forging 2xxx (Mg-free Al-Cu-Si-Mn). Source: ASM Handbook v.2.",
    },
    {
        "name": "5182-O",
        "composition_wt": {"Al": 95.0, "Mg": 4.5, "Mn": 0.35, "Fe": 0.15},
        "ys_MPa": 130,
        "temper": "O",
        "expected_in_domain": True,
        "note": "Auto-body / can-end sheet; tests low-strength end. Source: MatWeb.",
    },
]

TITANIUM_OOD_EXTERNAL: list[dict] = [
    {
        "name": "Ti-11.5Mo-6Zr-4.5Sn (Beta III)",
        "composition_wt": {"Ti": 78.0, "Mo": 11.5, "Zr": 6.0, "Sn": 4.5},
        "ys_MPa": 884,
        "temper": "STA",
        "expected_in_domain": True,
        "note": "Metastable-β; high Mo content. Source: ASM 1994.",
    },
    {
        "name": "Ti-17 (Ti-5Al-2Sn-2Zr-4Mo-4Cr)",
        "composition_wt": {"Ti": 83.0, "Al": 5.0, "Sn": 2.0, "Zr": 2.0, "Mo": 4.0, "Cr": 4.0},
        "ys_MPa": 1035,
        "temper": "STA",
        "expected_in_domain": True,
        "note": "β-rich α-β fan-disc alloy (GE). Source: TIMET datasheet.",
    },
    {
        "name": "SP-700 (Ti-4.5Al-3V-2Mo-2Fe)",
        "composition_wt": {"Ti": 88.5, "Al": 4.5, "V": 3.0, "Mo": 2.0, "Fe": 2.0},
        "ys_MPa": 1030,
        "temper": "STA",
        "expected_in_domain": True,
        "note": "Superplastically-formable α-β alloy (NKK). Source: ASM Alloy Digest.",
    },
    {
        "name": "Ti-6211 (Ti-6Al-2Nb-1Ta-0.8Mo)",
        "composition_wt": {"Ti": 90.2, "Al": 6.0, "Nb": 2.0, "Ta": 1.0, "Mo": 0.8},
        "ys_MPa": 620,
        "temper": "Annealed",
        "expected_in_domain": True,
        "note": "Naval near-α alloy (deep-submergence hulls). Source: ASM Handbook.",
    },
    {
        "name": "Ti-5111 (Ti-5Al-1Sn-1Zr-1V-0.8Mo)",
        "composition_wt": {"Ti": 91.2, "Al": 5.0, "Sn": 1.0, "Zr": 1.0, "V": 1.0, "Mo": 0.8},
        "ys_MPa": 590,
        "temper": "Annealed",
        "expected_in_domain": True,
        "note": "Naval near-α alloy; high toughness. Source: ASM Alloy Digest.",
    },
    {
        "name": "Ti-6-22-22 (Ti-6Al-2Sn-2Zr-2Cr-2Mo)",
        "composition_wt": {"Ti": 86.0, "Al": 6.0, "Sn": 2.0, "Zr": 2.0, "Cr": 2.0, "Mo": 2.0},
        "ys_MPa": 1000,
        "temper": "STA",
        "expected_in_domain": True,
        "note": "F-22 airframe α-β alloy. Source: Boyer 1994.",
    },
    {
        "name": "Ti-2.5Cu (IMI 230)",
        "composition_wt": {"Ti": 97.5, "Cu": 2.5},
        "ys_MPa": 525,
        "temper": "STA",
        "expected_in_domain": True,
        "note": "Age-hardenable Ti-Cu binary. NB: an earlier revision of this entry "
                "claimed Cu was absent from Ti training and marked it OOD — both were "
                "wrong. Cu is present at 0.5 wt% in Ti-6Al-6V-2Sn, making this a ~5x "
                "extrapolation, and the model predicts it to within 35 MPa. "
                "Source: Timet IMI 230 datasheet.",
    },
    {
        "name": "TNZT (Ti-35Nb-7Zr-5Ta)",
        "composition_wt": {"Ti": 53.0, "Nb": 35.0, "Zr": 7.0, "Ta": 5.0},
        "ys_MPa": 547,
        "temper": "Annealed",
        "expected_in_domain": True,
        "note": "Biomedical low-modulus β (training has Ti-29Nb-13Ta-4.6Zr, so the "
                "Nb-Ta-Zr region is represented). Source: Banerjee & Williams 2013.",
    },
]

NICKEL_OOD_EXTERNAL: list[dict] = [
    {
        "name": "Haynes 230",
        "composition_wt": {"Ni": 57.0, "Cr": 22.0, "W": 14.0, "Mo": 2.0,
                           "Fe": 3.0, "Al": 0.3, "C": 0.10},
        "ys_MPa": 385,
        "temper": "Annealed",
        "expected_in_domain": True,
        "note": "High-W solid-solution alloy. Source: Haynes International.",
    },
    {
        "name": "Haynes 282",
        "composition_wt": {"Ni": 57.0, "Cr": 19.5, "Co": 10.0, "Mo": 8.5,
                           "Ti": 2.1, "Al": 1.5, "Fe": 1.5, "C": 0.06},
        "ys_MPa": 733,
        "temper": "Aged",
        "expected_in_domain": True,
        "note": "Wrought γ' superalloy (2005) — newer than any training alloy. "
                "CORRECTED 2026-08-07 from 715 MPa. Source: Haynes International "
                "282 brochure — age-hardened plate, room-temp 0.2% yield = "
                "106.3 ksi (733 MPa), UTS 169.7 ksi (1170 MPa). Standard age is "
                "1010C/2h/AC + 788C/8h/AC, matching the recorded schedule. "
                "haynesintl.com/wp-content/uploads/2023/09/282-brochure.pdf",
    },
    {
        "name": "Inconel 686",
        "composition_wt": {"Ni": 57.0, "Cr": 20.5, "Mo": 16.3, "W": 3.9, "Fe": 1.0},
        "ys_MPa": 365,
        "temper": "Annealed",
        "expected_in_domain": True,
        "note": "Ni-Cr-Mo-W corrosion alloy (beyond C-276 Mo+W). Source: Special Metals.",
    },
    {
        "name": "Incoloy 925",
        "composition_wt": {"Ni": 44.0, "Fe": 26.0, "Cr": 21.0, "Mo": 3.0,
                           "Ti": 2.1, "Cu": 1.8, "Al": 0.3},
        "ys_MPa": 832,
        "temper": "Aged",
        "expected_in_domain": True,
        "note": "Age-hardenable oil-and-gas alloy; Ni < 50% tests routing threshold. "
                "CORRECTED 2026-08-07 from 690 MPa, which was below even the "
                "SMC HA 46 spec minimum (724-758). Source: Special Metals "
                "INCOLOY alloy 925 bulletin Table 6, Round/Solution-Annealed "
                "and Aged, 0.2% offset = 120.6 ksi (832 MPa). "
                "specialmetals.com/documents/technical-bulletins/incoloy/incoloy-alloy-925.pdf",
    },
    {
        "name": "Nimonic PE16",
        "composition_wt": {"Ni": 43.5, "Fe": 33.0, "Cr": 16.5, "Mo": 3.3,
                           "Ti": 1.2, "Al": 1.2},
        "ys_MPa": 450,
        "temper": "Aged",
        "expected_in_domain": True,
        "note": "Fe-rich γ' alloy (fast-reactor cladding). CORRECTED 2026-08-07 "
                "from 530 MPa (recall, unsourced) to the published 0.2% proof "
                "stress of 450 MPa (65,300 psi) for precipitation-hardened "
                "material. NOTE: this correction makes the model look WORSE on "
                "this alloy, not better — applied anyway, because selecting only "
                "favourable corrections would corrupt the test set. Source: AZoM "
                "datasheet 7671 (secondary aggregator) — "
                "azom.com/article.aspx?ArticleID=7671",
    },
    {
        "name": "Haynes 214",
        "composition_wt": {"Ni": 75.0, "Cr": 16.0, "Al": 4.5, "Fe": 3.0, "C": 0.05},
        "ys_MPa": 615,
        "temper": "Annealed",
        "expected_in_domain": True,
        "note": "Alumina-forming Ni-Cr-Al (4.5% Al without Ti). CORRECTED "
                "2026-08-07 from 580 MPa. Source: Haynes International 214 "
                "brochure, cold-rolled + solution-annealed sheet 2.0-3.2 mm, "
                "room-temp 0.2% offset = 89.4 ksi (615 MPa). "
                "KNOWN MODEL LIMITATION, not a data problem: this alloy's 4.5% Al "
                "precipitates gamma-prime below 955C, so it is gamma-prime "
                "strengthened even in the 'Annealed' condition. The temper label "
                "drives Orowan vf to zero, so the model predicts a plain "
                "solid-solution strength (~303 MPa) and under-shoots by ~310 MPa. "
                "haynesintl.com/wp-content/uploads/2024/08/214-brochure.pdf",
    },
    {
        "name": "Inconel 740H",
        "composition_wt": {"Ni": 50.2, "Cr": 24.5, "Co": 20.0, "Nb": 1.5,
                           "Ti": 1.35, "Al": 1.35, "Fe": 0.7, "Mn": 0.3, "Si": 0.15},
        "ys_MPa": 742,
        "temper": "Aged",
        "expected_in_domain": True,
        "note": "A-USC boiler alloy (ASME Code Case 2702). CORRECTED 2026-08-07 "
                "from 680 MPa. Source: Special Metals INCONEL alloy 740H "
                "brochure Table 5 (extruded, solution annealed + aged pipe), "
                "room-temperature 0.2% YS = 107.7 ksi (742 MPa) longitudinal, "
                "105.0 ksi (724 MPa) transverse; Table 6 plate aging response "
                "spans 738-782 MPa. "
                "specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-740h.pdf",
    },
    {
        "name": "MAR-M-200",
        "composition_wt": {"Ni": 59.5, "W": 12.5, "Co": 10.0, "Cr": 9.0,
                           "Al": 5.0, "Ti": 2.0, "Nb": 1.0, "C": 0.15},
        "ys_MPa": 840,
        "temper": "Aged",
        "expected_in_domain": True,
        "note": "Classic cast turbine-blade alloy (W-strengthened; Mar-M-247 is in "
                "training but has Hf/Ta chemistry). Source: ASM Handbook v.3.",
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

ALL_OOD_EXTERNAL = {
    "aluminum": ALUMINUM_OOD_EXTERNAL,
    "titanium": TITANIUM_OOD_EXTERNAL,
    "nickel":   NICKEL_OOD_EXTERNAL,
}
