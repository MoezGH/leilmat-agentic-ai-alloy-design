# CALPHAD TDB files: provenance, terms, and what each one actually models

> **2026-11-01.** Seven files used to live here. Five were **removed** because none carries a licence that
> permits redistribution: `alcocrni_nibase.tdb` (labelled by its author "FOR TESTING PURPOSES ONLY -- NOT
> FOR RESEARCH"), `alzn_binary.tdb` ("Copyright (C) NIMS 2009", no licence), and `alni_binary.tdb`,
> `alcrni_nibase.tdb`, `cfe_binary.tdb` (no author or terms in the file). The pycalphad licence (MIT)
> covers pycalphad's code, not data files that happened to be distributed with its tests. Systems only
> those files covered (Al-Ni, Al-Cr-Ni, Al-Co-Cr-Ni, C-Fe) are now **refused**. They stay in the git
> history and, if their terms are later confirmed, can return.

## Provenance and terms

| File | What the file header says | Terms / status |
|---|---|---|
| `mc_fecocrnbti_steels.tdb` | "Based on Matcalc steel database 2.060; **used under ODbL**. Only Fe-Co-Cr-Nb-Ti parameters retained (for performance in test)" | **ODbL 1.0** (share-alike), contents under the DbCL 1.0, per MatCalc's open-databases page. This file is a *derivative database*: it stays under ODbL with this notice and must not be relabelled MIT. Results computed from it should say: "Computed with data from the MatCalc open database (mc_fe), licensed under the ODbL 1.0." |
| `cost507_al_alloys.tdb` | "Obtained from http://www.opencalphad.com/databases.html — COST-507, Round II (January 1999), frozen version — thermodynamic database for **light metal alloys**" | Redistribution terms **not yet confirmed** (the opencalphad.com page and the NIST records could not be read on 2026-11-01). **Confirm before publishing**, or replace it with a fetch-at-install step. |

## What each file actually models

"Declares an element" and "models an element" are different things: a component with no
`PARAMETER` statements is silently treated as zero-energy, which yields plausible-looking but
meaningless equilibria. The registry in `apps/api/ml/calphad/databases.py` claims only
elements that carry at least one parameter, and `test_tdb_registry_matches_file_contents`
enforces it for every bundled file.

| File | Elements with parameters | Notes |
|---|---|---|
| `cost507_al_alloys.tdb` | 26 (Al, Mg, Si, Cu, Fe, Mn, Cr, Ti, Zr, Zn, Ni, Mo, Li, Sn, V, W, Nb, Ta, Hf, Y, Ce, Nd, B, C, N, …) | An **aluminium / light-metal** assessment. Routing refuses Fe-, Ni- or Co-based compositions (> 50 at%) rather than answer them from it. |
| `mc_fecocrnbti_steels.tdb` | **5**: Fe, Cr, Co, Nb, Ti | A trimmed extract. It declares 24 elements but carries **no** parameters for Ni, Mo, Si, C, Mn, Al, W, V, Cu, B, N or O. It is **not** a stainless-steel or Ni-superalloy database. |

## Coverage: what the engine will and will not answer

| Alloy class | Behaviour |
|---|---|
| Al alloys (1xxx-8xxx), incl. minor Fe/Ni additions, and Al-Zn | Answered from `cost507_al_alloys.tdb` |
| Fe-Co-Cr-Nb-Ti compositions | Answered from `mc_fecocrnbti_steels.tdb` |
| **Plain Fe-C steels, Fe-Cr-Ni steels (304, 316, ...)** | **Refused**: no bundled database models them |
| **Ni-Al, Al-Cr-Ni, Al-Co-Cr-Ni, multicomponent Ni-base superalloys (718, ...)** | **Refused**: no bundled database models them |

Refusing is deliberate. Before the refusals, 304/316 were routed to COST 507 and returned
99.8 % ordered BCC_B2 at 1100 C, where austenitic stainless is FCC austenite.

## Getting wider coverage under one clear licence

MatCalc publishes **open** thermodynamic databases, free of charge under the ODbL 1.0 with the DbCL for
contents (https://www.matcalc.at/index.php/databases/open-databases, checked 2026-11-01):

| Database | Release | Elements |
|---|---|---|
| `mc_fe` | 2.062 (2024-11-08) | Fe, Al, B, C, Co, Cr, Cu, H, Hf, La, Mn, Mo, N, Nb, Ni, O, P, Pd, S, Si, Ta, Ti, V, W, Y |
| `mc_ni` | 2.036 (2024-08-24) | Ni, Al, B, C, Co, Cr, Cu, Fe, Hf, La, Mn, Mo, N, Nb, O, S, Si, Ti, V, W, Y, Zr |
| `mc_al` | 2.037 (2025-07-25) | Al, Cr, Cu, Fe, Mg, Mn, Ni, Sc, Si, Ti, Zn, Zr |

These would cover the steels and superalloys that are refused today. **Not yet checked:** that pycalphad
parses and solves the full files correctly and fast enough, and that the validation references pass.

## Extending with commercial or better-validated databases

Drop any `.tdb` into this directory and register it in `apps/api/ml/calphad/databases.py`
(`_USER_REGISTRY`, priority >= 10). Commercial databases (Thermo-Calc TCFE / TCNi / TCAL /
TCTi, CompuTherm PanFe / PanNi / PanAl) are preferred automatically where they cover the
composition. This is the supported way to enable Fe-Cr-Ni steels and Ni superalloys.
