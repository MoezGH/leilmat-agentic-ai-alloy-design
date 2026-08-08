"""
Aging schedules (temperature + time) for precipitation-hardened alloys.

WHY THIS FILE EXISTS
--------------------
The temper label ("Aged", "T6") collapses every heat treatment into one
bucket.  That makes precipitate radius r̄ a per-temper constant, which in turn
makes every composition-derived strengthening feature degenerate into a
function of volume fraction alone — see the extended note in
``apps/api/ml/strengthening.py``.  Measured consequence: 54 pairs of aged-Ni
training alloys sit within |Δvf| < 0.02 yet differ in yield strength by 185
MPa on average (max 480: Inconel 718 at 1100 vs Nimonic 80A at 620).  The
difference is processing, and this file is where processing enters.

Kept as a name-keyed lookup rather than extra columns on every alloy row so
that the provenance metadata (source + confidence) stays in one auditable
place, and so partial coverage is the normal case rather than a schema hole.

SCHEMA
------
    T_C         float   primary aging temperature, degrees C
    time_s      float   hold time at that temperature, seconds
    source      str     citation for the schedule
    confidence  str     "high" | "medium" | "low"  — see below
    note        str     multi-step detail, caveats

MULTI-STEP AGING
----------------
Many superalloys use a two-step age (e.g. 718: 718 C/8 h then 621 C/8 h).
Only the PRIMARY (higher-temperature) step is recorded, because LSW coarsening
is diffusion-controlled and D is Arrhenius: with Q = 268 kJ/mol for γ', the
high-temperature step dominates r̄ growth by one to two orders of magnitude.
The second step nucleates fine tertiary γ' rather than coarsening the
secondary population.  The full schedule is recorded in ``note``.

CONFIDENCE — READ BEFORE TRUSTING
---------------------------------
These were compiled from standard heat-treatment practice and are NOT drawn
from a machine-readable licensed source (the ASM Alloy Digest / MMPDS / NIMS
ingest remains blocked on data access — see SCORECARD.md Sprint 3.5).

    "high"    Schedule is defined by an AMS/ASTM spec or is the single
              universally-published practice for that alloy.  Confident.
    "medium"  Standard practice for the alloy family, applied to this alloy;
              individual producers vary the hold time.  Directionally right,
              exact hold may differ.
    "low"     Inferred from a closely-related alloy in the same family.
              Treat as a placeholder pending a citable source.

Anything not listed here simply has no schedule; the strengthening code falls
back to the canonical per-temper radius.  That fallback is safe and is the
pre-existing behaviour — absence of an entry is never an error.
"""
from __future__ import annotations

_H = 3600.0

AGING_SCHEDULES: dict[str, dict] = {
    # ── Ni-Fe / Nb-strengthened (γ") ────────────────────────────────────
    "Inconel 718": {
        "T_C": 718.0, "time_s": 8 * _H, "source": "AMS-5663", "confidence": "high",
        "note": "Double age 718C/8h + 621C/8h. Strengthener is γ\" (Ni3Nb), "
                "not γ' — the γ'-based coarsening constants under-model this alloy.",
    },
    "Inconel 718-Solution": {
        "T_C": None, "time_s": None, "source": "AMS-5662", "confidence": "high",
        "note": "Solution treated only, no age — no precipitate to size.",
    },
    "Inconel 706": {
        "T_C": 720.0, "time_s": 8 * _H, "source": "AMS-5703", "confidence": "high",
        "note": "Double age 720C/8h + 620C/8h. γ' + γ\" mixed.",
    },
    "Inconel 725": {
        "T_C": 732.0, "time_s": 8 * _H,
        "source": "Special Metals INCONEL alloy 725 bulletin, Table 7 footnote "
                  "(specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-725.pdf)",
        "confidence": "high",
        "note": "VERIFIED 2026-08-07 against the manufacturer bulletin, which states: "
                "\"Solution treated at 1900F (1038C) then aged at 1350F (732C)/8 h/FC "
                "at 100F (56C)/h to 1150F (621C)/8 h/AC.\" Was recorded as 730C from "
                "recall; the published value is 732C.",
    },
    "Incoloy 925": {
        "T_C": 740.0, "time_s": 8 * _H,
        "source": "Special Metals INCOLOY alloy 925 bulletin, Fig. 3 caption "
                  "(specialmetals.com/documents/technical-bulletins/incoloy/incoloy-alloy-925.pdf)",
        "confidence": "high",
        "note": "VERIFIED 2026-08-07 — bulletin refers to \"the 1365F (740C) dual aged "
                "condition\". Was recorded as 730C from recall; published value is 740C. "
                "Second step not stated in the bulletin; 8 h primary hold retained.",
    },
    "Incoloy 903": {
        "T_C": 720.0, "time_s": 8 * _H, "source": "SMC-903", "confidence": "medium",
        "note": "Double age 720C/8h + 620C/8h; controlled-expansion alloy.",
    },
    "Incoloy 901": {
        "T_C": 790.0, "time_s": 2 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "790C/2h + 720C/24h.",
    },
    "Nimonic 942": {
        "T_C": 750.0, "time_s": 16 * _H, "source": "ASM/v3", "confidence": "low",
        "note": "Inferred from Incoloy 901 / PE16 practice — same Ni-Fe-Ti family.",
    },
    "Pyromet 860": {
        "T_C": 760.0, "time_s": 16 * _H, "source": "ASM/v3", "confidence": "low",
        "note": "Inferred from Waspaloy-class practice; producer schedules vary.",
    },
    "Nimonic PE16": {
        "T_C": 799.0, "time_s": 2 * _H,
        "source": "AZoM alloy datasheet 7671 (secondary source, reproduces "
                  "Special Metals data) — azom.com/article.aspx?ArticleID=7671",
        "confidence": "medium",
        "note": "CORRECTED 2026-08-07. Published schedule is solution 1038C/4h/AC, "
                "then 799C/2h/AC, then 699C/16h/AC. I had recorded 700C/16h — the "
                "SECOND step — which violates this module's own stated convention of "
                "recording the primary (higher-temperature) step, the one that "
                "dominates LSW coarsening. Left at medium: AZoM is a secondary "
                "aggregator, not a manufacturer bulletin.",
    },

    # ── Nimonic series (γ') ──────────────────────────────────────────────
    "Nimonic 80A": {
        "T_C": 700.0, "time_s": 16 * _H, "source": "ASM/v3", "confidence": "high",
        "note": "1080C solution + 700C/16h.",
    },
    "Nimonic 81": {
        "T_C": 700.0, "time_s": 16 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "As Nimonic 80A practice; higher-Cr variant.",
    },
    "Nimonic 90": {
        "T_C": 700.0, "time_s": 16 * _H, "source": "ASM/v3", "confidence": "high",
        "note": "1080C solution + 700C/16h.",
    },
    "Nimonic 105": {
        "T_C": 850.0, "time_s": 4 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "850C/4h + 700C/16h.",
    },
    "Nimonic 115": {
        "T_C": 1100.0, "time_s": 6 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "1100C/6h + 850C/16h; high-γ' blade alloy.",
    },
    "Nimonic 263": {
        "T_C": 800.0, "time_s": 8 * _H, "source": "ASM/v3", "confidence": "high",
        "note": "800C/8h; deliberately low-γ' for weldability.",
    },
    "Nimonic PK33": {
        "T_C": 800.0, "time_s": 4 * _H, "source": "ASM/v3", "confidence": "low",
        "note": "Inferred from Nimonic 263 / 105 practice.",
    },

    # ── Waspaloy / Udimet / Rene disc alloys ────────────────────────────
    "Waspaloy": {
        "T_C": 760.0, "time_s": 16 * _H, "source": "AMS-5708", "confidence": "high",
        "note": "1080C solution + 845C/24h stabilise + 760C/16h age.",
    },
    "Rene 41": {
        "T_C": 760.0, "time_s": 16 * _H, "source": "AMS-5712", "confidence": "high",
        "note": "1065C solution + 760C/16h.",
    },
    "Rene 80": {
        "T_C": 845.0, "time_s": 16 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "1095C/4h + 845C/16h; cast blade alloy.",
    },
    "Rene 88DT": {
        "T_C": 760.0, "time_s": 8 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "760C/8h; powder-metallurgy disc alloy.",
    },
    "Rene 95": {
        "T_C": 760.0, "time_s": 8 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "760C/8h; PM disc alloy.",
    },
    "Udimet 500": {
        "T_C": 845.0, "time_s": 24 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "845C/24h + 760C/16h.",
    },
    "Udimet 520": {
        "T_C": 845.0, "time_s": 24 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "845C/24h + 760C/16h.",
    },
    "Udimet 700": {
        "T_C": 845.0, "time_s": 24 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "845C/24h + 760C/16h.",
    },
    "Udimet 720": {
        "T_C": 760.0, "time_s": 8 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "760C/8h + 650C/24h.",
    },
    "Udimet 720Li": {
        "T_C": 760.0, "time_s": 8 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "760C/8h + 650C/24h; low-interstitial variant.",
    },
    "LSHR (Low-Solvus High-Refr)": {
        "T_C": 855.0, "time_s": 4 * _H, "source": "NASA/TM-2008", "confidence": "low",
        "note": "Supersolvus + 855C/4h; NASA research disc alloy, schedules vary by study.",
    },

    # ── Inconel / Incoloy general ───────────────────────────────────────
    "Inconel 625-Aged": {
        "T_C": 730.0, "time_s": 8 * _H, "source": "SMC-625", "confidence": "medium",
        "note": "730C/8h; δ/γ\" strengthened.",
    },
    "Inconel X-750": {
        "T_C": 730.0, "time_s": 20 * _H, "source": "AMS-5667", "confidence": "high",
        "note": "730C/20h + 620C/20h.",
    },
    "Inconel 750": {
        "T_C": 730.0, "time_s": 20 * _H, "source": "AMS-5667", "confidence": "medium",
        "note": "As X-750 practice.",
    },
    "Inconel 751": {
        "T_C": 730.0, "time_s": 20 * _H, "source": "SMC-751", "confidence": "medium",
        "note": "As X-750 practice; higher Al for valve service.",
    },
    "Inconel 740H": {
        "T_C": 800.0, "time_s": 4 * _H,
        "source": "Special Metals INCONEL alloy 740H brochure, Table 5 note + Fig. 3 text "
                  "(specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-740h.pdf)",
        "confidence": "high",
        "note": "VERIFIED 2026-08-07 — brochure states tubes were \"annealed at 2125F "
                "(1120C) and aged at 1472F (800C) for 4 hours\"; Table 5 pipe note gives "
                "\"Age = 1472F/5hrs/AC\". 800C confirmed; hold is 4-5 h by product form, "
                "4 h retained. Table 6 also reports the aging response at 760C and 800C "
                "for 4/8/16 h, all within 738-782 MPa.",
    },
    "Monel K-500": {
        "T_C": 600.0, "time_s": 16 * _H, "source": "ASM/v2", "confidence": "high",
        "note": "600C/16h; Ni3(Al,Ti) in a Ni-Cu matrix.",
    },

    # ── Haynes ───────────────────────────────────────────────────────────
    "Haynes 282": {
        "T_C": 1010.0, "time_s": 2 * _H, "source": "HAYNES-282", "confidence": "high",
        "note": "1010C/2h + 788C/8h two-step age.",
    },
    "Haynes 242": {
        "T_C": 650.0, "time_s": 24 * _H, "source": "HAYNES-242", "confidence": "high",
        "note": "650C/24h; Ni2(Mo,Cr) long-range order, NOT γ' — the γ'-based "
                "coarsening constants do not describe this alloy well.",
    },

    # ── Cast / SX blade alloys ──────────────────────────────────────────
    "Mar-M-247": {
        "T_C": 870.0, "time_s": 20 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "1080C/4h + 870C/20h.",
    },
    "CM-247LC": {
        "T_C": 870.0, "time_s": 20 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "As Mar-M-247 practice.",
    },
    "IN100": {
        "T_C": 870.0, "time_s": 10 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "1080C/4h + 870C/10h.",
    },
    "Inconel 738 LC": {
        "T_C": 845.0, "time_s": 24 * _H, "source": "ASM/v3", "confidence": "medium",
        "note": "1120C/2h + 845C/24h.",
    },
    "IN939": {
        "T_C": 850.0, "time_s": 16 * _H, "source": "ASM/v3", "confidence": "low",
        "note": "Multi-step; 850C/16h primary. Producer schedules vary widely.",
    },
    "Inconel 939": {
        "T_C": 850.0, "time_s": 16 * _H, "source": "ASM/v3", "confidence": "low",
        "note": "Multi-step; 850C/16h primary.",
    },
}


def schedule_for(name: str) -> dict | None:
    """Aging schedule for an alloy by name, or None when unknown/not aged."""
    entry = AGING_SCHEDULES.get(name)
    if entry is None or entry.get("T_C") is None or entry.get("time_s") is None:
        return None
    return entry


def coverage_report() -> dict:
    """Counts by confidence level — used by the dataset tests and scorecard."""
    out: dict[str, int] = {}
    for e in AGING_SCHEDULES.values():
        if e.get("T_C") is None:
            out["not_aged"] = out.get("not_aged", 0) + 1
        else:
            c = e.get("confidence", "unknown")
            out[c] = out.get(c, 0) + 1
    return out
