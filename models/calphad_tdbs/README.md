# CALPHAD TDB files — provenance, terms, and what each one actually models

> **Correction (2026-10).** An earlier version of this file stated that *all* files here are
> open-source or public-domain under the BSD-3-Clause licence of pycalphad "as a whole".
> The file headers do not support that. The pycalphad licence covers pycalphad's own code;
> it does not by itself relicense third-party data files that state their own terms, and
> several of these do. The table below reports what each file's **own header** says.

## Provenance and terms

| File | What the file header says | Terms / status |
|---|---|---|
| `cost507_al_alloys.tdb` | "Obtained from http://www.opencalphad.com/databases.html — COST-507, Round II (January 1999), frozen version — thermodynamic database for **light metal alloys**" | Redistribution terms **not yet verified** against the COST 507 / opencalphad.com source. Confirm before publishing. |
| `mc_fecocrnbti_steels.tdb` | "Based on Matcalc steel database 2.060; **used under ODbL**. Only Fe-Co-Cr-Nb-Ti parameters retained (for performance in test)" | **ODbL 1.0** (share-alike data licence). This file stays under ODbL and must keep its notice; it cannot be relabelled BSD/MIT. |
| `alcocrni_nibase.tdb` | "**FOR TESTING PURPOSES ONLY -- NOT FOR RESEARCH**" — CRALDAD v1, Al-Co-Cr-Ni combined from four ternaries | Author-declared test file. Not validated for engineering predictions. See "Open decision" below. |
| `alcrni_nibase.tdb` | No provenance in the file | Source not stated in the file; previously attributed to the pycalphad test suite. Unverified. |
| `alni_binary.tdb` | "Database file written 2014-10-21; from database: USER" | The previous README attributed this to Dupin et al. 2001. The header does not say so. Unverified. |
| `alzn_binary.tdb` | "TDB file created by T.Abe, K.Hashimoto and Y.Sawada", 2011 | Attribution confirmed by header. Licence terms not stated. |
| `cfe_binary.tdb` | "Database has pressure dependence, which is useful for testing. From database: User data 2014.06.09" | The previous README attributed this to "Broshe et al." The header does not say so. Unverified. |

Files were obtained from the pycalphad test suite (per the earlier README); that is a
distribution channel, not a licence grant for the data inside.

## What each file actually models

"Declares an element" and "models an element" are different things: a component with no
`PARAMETER` statements is silently treated as zero-energy, which yields plausible-looking but
meaningless equilibria. The registry in `apps/api/ml/calphad/databases.py` now claims only
elements that carry at least one parameter, and `test_tdb_registry_matches_file_contents`
enforces it for every bundled file.

| File | Elements with parameters | Notes |
|---|---|---|
| `cost507_al_alloys.tdb` | 26 (Al, Mg, Si, Cu, Fe, Mn, Cr, Ti, Zr, Zn, Ni, Mo, Li, Sn, V, W, Nb, Ta, Hf, Y, Ce, Nd, B, C, N, …) | An **aluminium / light-metal** assessment. Routing refuses Fe-, Ni- or Co-based compositions (> 50 at%) rather than answer them from it. |
| `mc_fecocrnbti_steels.tdb` | **5**: Fe, Cr, Co, Nb, Ti | A trimmed extract. It declares 24 elements but carries **no** parameters for Ni, Mo, Si, C, Mn, Al, W, V, Cu, B, N or O. It is **not** a stainless-steel or Ni-superalloy database. |
| `alcocrni_nibase.tdb` | Al, Co, Cr, Ni | Test file (see above). |
| `alcrni_nibase.tdb` | Al, Cr, Ni | |
| `alni_binary.tdb` | Al, Ni | Gives the γ/γ′ (FCC_L12) references. |
| `alzn_binary.tdb` | Al, Zn | |
| `cfe_binary.tdb` | C, Fe | Known limitation: the 0.8 wt% C eutectoid reference fails on this file (see `docs/SCORECARD.md`). |

## Coverage — what the engine will and will not answer

| Alloy class | Behaviour |
|---|---|
| Al alloys (1xxx–8xxx), incl. minor Fe/Ni additions | Answered from `cost507_al_alloys.tdb` |
| Binary systems with a dedicated file (Ni-Al, Al-Zn, C-Fe) | Answered from that file |
| Al-Cr-Ni / Al-Co-Cr-Ni | Answered from the Ni-base research files (see caveat above) |
| **Fe-Cr-Ni steels (304, 316, …)** | **Refused** — no bundled open database models them |
| **Multicomponent Ni-base superalloys (718, …)** | **Refused** — no bundled open database models them |

Refusing is deliberate. Before this correction, 304/316 were routed to COST507 and returned
99.8 % ordered BCC_B2 at 1100 °C, where austenitic stainless is FCC austenite.

## Open decision

`alcocrni_nibase.tdb` is routed for Al-Co-Cr-Ni compositions even though its author labels it
"FOR TESTING PURPOSES ONLY -- NOT FOR RESEARCH". Whether to keep, flag, or remove it from
routing is a product decision and has not been made here.

## Extending with commercial or better-validated databases

Drop any `.tdb` into this directory and register it in `apps/api/ml/calphad/databases.py`
(`_USER_REGISTRY`, priority ≥ 10). Commercial databases (Thermo-Calc TCFE / TCNi / TCAL /
TCTi, CompuTherm PanFe / PanNi / PanAl) are preferred automatically where they cover the
composition. This is the supported way to enable Fe-Cr-Ni steels and Ni superalloys.
