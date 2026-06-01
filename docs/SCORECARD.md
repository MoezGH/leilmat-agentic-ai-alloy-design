# LeilMat — Unified Validation Scorecard

_Generated 2026-06-01T08:43:45+00:00_  ·  source-of-truth for SCIENTIFIC_ROADMAP.md and README.md sprint headlines.  Regenerate with `python -m apps.api.ml.eval.unified_scorecard --refresh all`.

Each section reads from a JSON cache at `apps/api/ml/eval/_cache/<key>.json`.  Slow sections (Scheil, Taichi KWC, LOO) are not refreshed unless `--include-slow` or an explicit `--refresh <key>` is passed; nightly CI runs the slow set.

---

## Sprint 1 — CALPHAD equilibrium phase fractions

_pycalphad equilibrium against 15 canonical reference points across Al / Fe / Ni / Ti / Cu (Massalski + ternary)._

**13 / 14 canonical references pass** (93%)  ·  total runtime 28.8s.

| Reference | Outcome | Notes |
|-----------|:-------:|-------|
| Al-Si eutectic above liquidus (900 K) | ✓ | LIQUID 1.00 |
| Al-Si below eutectic — two-phase (800 K) | ✓ | FCC_A1 0.89, DIAMOND_A4 0.11 |
| Pure Al at 900 K — single-phase FCC | ✓ | FCC_A1 1.00 |
| Al-Zn 40 at% Zn at 600 K — FCC + HCP | ✓ | FCC_A1 1.00 |
| Al-Ni 25 at% Al at 900 K — L12 / FCC_L12 (γ') | ✓ | FCC_L12 1.00 |
| 6061 at 803 K (530°C solutionising T) | ✓ | ALFESI_BETA 0.02, FCC_A1 0.97, MG2SI 0.01 |
| 6061 at 448 K (175°C T6 ageing T) — Mg2Si present | ✓ | FCC_A1 0.96, ALCU_THETA 0.01, ALFESI_ALPHA 0.01 |
| Al-12 wt% Si casting alloy at 900 K — single-phase LIQUID | ✓ | LIQUID 1.00 |
| 7075 at 750 K (477°C) — FCC_A1 dominant | ✓ | AL13CR2 0.01, FCC_A1 0.94, LIQUID 0.05 |
| 5083 at 600 K (327°C) — FCC_A1 + trace Al12Mg17 | ✓ | FCC_A1 0.97, AL13CR2 0.01, AL6MN 0.03 |
| Fe-C 0.8 wt% C at 1050 K (777°C) — austenite (FCC_A1) | ✗ | FCC_A1 0.31, BCC_A2 0.69 |
| 304 SS at 1373 K (1100°C) — austenite or delta-ferrite | ✓ | BCC_B2 1.00 |
| Ni3Al (γ') at 25 at% Al — FCC_L12 / L12_FCC | ✓ | FCC_L12 1.00 |
| Ni-Al γ/γ' two-phase at 10 at% Al — FCC + γ' | ✓ | FCC_L12 1.00 |

_cached 0s ago_  _(29.4s to compute)_

---

## Sprint 2 (Scheil) — Scheil-Gulliver solidification

_Non-equilibrium freezing curves on canonical castings — mushy zone, hot-tearing tendency._

**6 / 6 castings pass** (100%)  ·  total runtime 208.9s.

| Casting | Outcome | Liquidus K | Solidus K | Mushy K |
|---------|:-------:|-----------:|----------:|--------:|
| A356 (Al-7Si-0.3Mg) | ✓ | 885.0 | 772.36 | 112.64 |
| Al-12Si (eutectic) | ✓ | 855.0 | 849.86 | 5.14 |
| 2024 Al-Cu wrought | ✓ | 910.0 | 775.56 | 134.44 |
| 6061 Al-Mg-Si wrought | ✓ | 925.0 | 790.02 | 134.98 |
| 7075 Al-Zn-Mg-Cu wrought | ✓ | 935.0 | 814.86 | 120.14 |
| AlSi9Cu3 (die-cast 380.0) | ✓ | 860.0 | 784.86 | 75.14 |

_cached 0s ago_  _(208.9s to compute)_

---

## Sprint 2 (TTT) — Fe-C TTT diagrams (Kirkaldy-Venugopalan)

_Pearlite / bainite nose temperatures + Andrews Ms / Bs on AISI 1045 / 4140 / 4340 / IN 718 austenitisation._

**6 / 6 steels pass** (100%).

| Steel | Outcome | Pearlite nose | Bainite nose | Ms |
|-------|:-------:|---------------|--------------|----|
| AISI 1045 (medium-C plain-C) | ✓ | 566.2°C / 2.39s | 544.4°C / 3.73s | 323.6°C |
| AISI 4140 (Cr-Mo, oil-quenched) | ✓ | 580.4°C / 91.68s | 477.0°C / 41.12s | 327.6°C |
| AISI 4340 (Ni-Cr-Mo, deep-hardening) | ✓ | 556.6°C / 1102.67s | 440.7°C / 252.77s | 302.4°C |
| AISI 1080 (eutectoid plain-C) | ✓ | 569.5°C / 10.03s | 468.7°C / 1142.06s | 175.0°C |
| AISI 5140 (Cr-only) | ✓ | 579.5°C / 39.14s | 500.8°C / 17.52s | 330.9°C |
| AISI 8620 (Ni-Cr-Mo carburising) | ✓ | 566.3°C / 21.84s | 536.1°C / 0.84s | 410.0°C |

_cached 0s ago_  _(0.0s to compute)_

---

## Sprint 2.5 + 2.6 — Microstructure rendering (FiPy + Taichi KWC)

_Per-test invariants; no aggregate runner._

Microstructure simulators (FiPy schematic + full Taichi anisotropic KWC dendrite) ship with **16 regression tests** (8 fast smoke + 8 slow simulation) across the two sprints.  No aggregate scorecard — each test asserts a specific morphological or physical invariant (six-arm dendrite, monotone growth, latent-heat suppression near seed, Karma-Rappel tip-velocity band).

Validation artifacts: `docs/sprint_2_6/dendrite_morphology.png`, `tip_velocity.png`, `local_validation.png`.

_(Static section — no JSON cache.)_

---

## Sprint 3 + 4 + 6 (YS) — Yield-strength holdout on canonical alloys

_Per-family RF + temper + physics features on alloys guaranteed not to leak into training (defence-in-depth filter)._

Held-out canonical alloys per family — production model on alloys never seen during training.  ``In CI`` is the fraction of in-domain alloys whose literature YS fell inside the 90% conformal interval.

| Family | n hold-out | n in-domain | In-dom. MAE (MPa) | In CI (target ≥85%) | OOD correct | False-pos. |
|--------|-----------:|------------:|------------------:|--------------------:|------------:|-----------:|
| aluminum |          5 |           5 |                19 |                100% |           0 |          0 |
| titanium |          5 |           5 |               143 |                100% |           0 |          0 |
| nickel   |          5 |           5 |                75 |                100% |           0 |          0 |
| steel    |          6 |           4 |               188 |                100% |           2 |          0 |

_cached 0s ago_  _(0.9s to compute)_

---

## Sprint 3.5 — NIMS / MMPDS / ASM Alloy Digest ingest

_Deferred — blocked on data access._

❌ **Deferred** — Sprint 3.5 (NIMS / MMPDS / ASM Alloy Digest ingest) is blocked on data access, not on engineering.  Closing the Ti CV-MAE gap (101 MPa actual vs ≤80 MPa target) needs ~50-100 NIMS or MMPDS-08 entries.  See `SCIENTIFIC_ROADMAP.md` for the re-entry checklist.

---

## Sprint 5 — KWN precipitation kinetics

_Kampmann-Wagner numerical: CNT nucleation + Zener growth + LSW coarsening across 6 canonical TEM/SAXS reference points._

**6 / 6 canonical cases pass** (100%)  ·  factor-of-2-to-4 tolerance on (vf, r̄).

| Case | Phase | vf pred / ref / factor | r̄ pred / ref (nm) / factor | Outcome |
|------|-------|------------------------|----------------------------|:-------:|
| Al-4Cu T6 | Al2Cu_theta_prime | 0.06952 / 0.03 / 2.32× | 24.725 / 50.0 / 2.02× | ✓ |
| 6061-T6 β" | Mg2Si_beta_doubleprime | 0.02224 / 0.012 / 1.85× | 12.306 / 5.0 / 2.46× | ✓ |
| 7075-T6 η' | MgZn2_eta_prime | 0.0482 / 0.05 / 1.04× | 13.146 / 10.0 / 1.31× | ✓ |
| IN 718 γ" (peak-age) | Ni3Nb_gamma_doubleprime | 0.06372 / 0.15 / 2.35× | 12.214 / 30.0 / 2.46× | ✓ |
| MgZn2 η' (140 °C, 12 h) | MgZn2_eta_prime | 0.04824 / 0.045 / 1.07× | 21.91 / 18.0 / 1.22× | ✓ |
| Al-Cu θ' under-aged | Al2Cu_theta_prime | 0.06952 / 0.02 / 3.48× | 15.576 / 20.0 / 1.28× | ✓ |

**Known limitations (deliberately out of scope):**

- `Ti-6-4 STA α-platelets`: α widmanstätten in Ti-6-4 STA is a β→α+β massive transformation, not a classical-nucleation problem.  KWN underpredicts because the matrix composition partitioning is not modelled.
- `IN 718 γ' (low-Al chemistry)`: γ' in IN 718 incorporates Al + Ti + Nb; the single-solute KWN model with Al alone reports under-saturated.  A multi-component γ' driving force from CALPHAD is needed (Sprint 5.5).

_cached 0s ago_  _(0.0s to compute)_

---

## Sprint 6 — Strengthening feature ablation

_5-fold CV MAE at L1/L2/L3/L4 feature levels — shows where temper one-hot and engineered physics features pay rent._

Per-family CV MAE at four feature levels: L1 composition only · L2 +temper · L3 +physics · L4 all.  Lower is better.

| Family | n | L1 comp | L2 +temper | L3 +physics | L4 all | Δ temper | Δ physics on top |
|--------|--:|--------:|-----------:|------------:|-------:|---------:|-----------------:|
| aluminum      | 105 |    79.8 |       41.4 |        62.3 |   41.7 |   +38.4 |            -0.3 |
| titanium      | 39 |   112.3 |      100.5 |       103.2 |  100.6 |   +11.8 |            -0.1 |
| nickel        | 55 |   156.3 |      108.4 |       101.5 |  106.0 |   +47.9 |            +2.4 |
| general_steel | 107 |   162.5 |      126.8 |       157.0 |  119.1 |   +35.7 |            +7.7 |

_cached 0s ago_  _(12.6s to compute)_

---

## Sprint 7 — Inverse-design canonical briefs

_5 engineering briefs (Al wing skin, Ti implant, Ni turbine, steel, Marine Al) through the qEHVI + feasibility-filter stack._

Inverse-design canonical briefs — BoTorch qEHVI wrapped in the hard-constraint feasibility layer.

| Brief | feasible / total | family match | top YS (MPa) | elapsed (s) |
|-------|------------------|--------------|-------------:|------------:|
| Aerospace Al wing skin | 2/8 | 0.6 | 287.0 | 8.13 |
| Ti orthopaedic implant | 0/8 | 1.0 | None | 5.17 |
| Ni-base turbine disc | 7/8 | 1.0 | 979.0 | 10.71 |
| Low-cost structural steel | 0/8 | 1.0 | None | 7.11 |
| Marine Al 5xxx | 7/8 | 1.0 | 96.0 | 6.38 |

_cached 0s ago_  _(37.5s to compute)_

---

## Sprint 8 — Hierarchical cost model

_17 canonical supplier quotes — spot price × form × cert × heat-treatment × supplier-minimum overhead._

**17 / 17 quotes within factor-of-2** (100%)  ·  13/17 within ±50% (76%)  ·  7/17 within ±25% (41%).

| Alloy | Family | Pred $ | Ref $ | Ratio | ±25% | ±50% |
|-------|--------|------:|------:|------:|:----:|:----:|
| AISI 1018 CD bar | plain_carbon_steel | $1.41 | $1.80 | 1.28× | — | ✓ |
| AISI 1045 HR plate, ASTM | plain_carbon_steel | $1.72 | $1.65 | 1.04× | ✓ | ✓ |
| AISI 4140 Q&T bar, AMS 6382 | low_alloy_steel | $4.14 | $7.20 | 1.74× | — | — |
| AISI 4340 Q&T bar, AMS 6414 | low_alloy_steel | $5.02 | $9.50 | 1.89× | — | — |
| AISI 304 plate, ASTM A240 | stainless | $6.64 | $6.80 | 1.02× | ✓ | ✓ |
| AISI 316L plate, ASME | ph_stainless | $11.36 | $11.50 | 1.01× | ✓ | ✓ |
| 17-4 PH H900 bar, AMS 5643 | ph_stainless | $19.73 | $13.00 | 1.52× | — | — |
| 6061-T651 plate, AMS 4027 | aluminum_aerospace | $8.72 | $9.50 | 1.09× | ✓ | ✓ |
| 7075-T651 plate, AMS 4045 | aluminum_aerospace | $9.62 | $14.00 | 1.46× | — | ✓ |
| 2024-T351 plate, AMS 4037 | aluminum_aerospace | $9.90 | $11.50 | 1.16× | ✓ | ✓ |
| A356-T6 casting (commercial) | aluminum_commercial | $3.28 | $3.50 | 1.07× | ✓ | ✓ |
| Ti-6Al-4V plate, AMS 4911 | titanium | $60.93 | $95.00 | 1.56× | — | — |
| Grade 2 CP-Ti plate, AMS 4902 | titanium | $67.09 | $55.00 | 1.22× | ✓ | ✓ |
| Inconel 718 bar, AMS 5662 | nickel | $104.29 | $70.00 | 1.49× | — | ✓ |
| Inconel 625 bar, AMS 5666 | nickel | $75.27 | $55.00 | 1.37× | — | ✓ |
| Hastelloy C-276 bar, AMS | nickel | $108.78 | $85.00 | 1.28× | — | ✓ |
| Monel 400 bar (ASTM B164) | nickel | $51.60 | $35.00 | 1.47× | — | ✓ |

_cached 0s ago_  _(0.0s to compute)_

---

## Sprint 9 — Literature RAG with citation enforcement

_Deferred — blocked on redistributable corpus._

❌ **Deferred** — Sprint 9 (Literature RAG + citation enforcement) is blocked on a redistributable authoritative corpus (ASM Handbook, Donachie, Boyer, Reed, Polmear are all paywalled).  Auto-fetched arXiv + NIST + OSTI alternative was judged insufficient.  See the re-entry checklist in `SCIENTIFIC_ROADMAP.md` and the auto-fetch implementation sketch preserved in this plan file's git history.

---

## Sprint Appendix A — M3GNet formation energy (optional)

_Random-substitution supercell vs MP-PBE reference values.  Skipped automatically if `matgl` is not installed._

Overall MAE **225 meV/atom** over 18 references  ·  envelope coverage 33.3%.

| Class | n | MAE (meV/at) | Median | Max |
|-------|--:|-------------:|-------:|----:|
| Pure elements | 5 | 0 | 0 | 0 |
| Intermetallics | 13 | 312 | 322 | 676 |

_cached 0s ago_  _(0.0s to compute)_

---

## Sprint Appendix B — Leave-one-out YS residuals

_Worst-case LOO residuals per family — re-fits the RF per held-out alloy._

Leave-one-out residuals per family — re-fits the RF for every alloy removed, gives an honest per-prediction error estimate.

**Aluminum — top 5 worst LOO predictions:**

| Alloy | Truth | LOO pred | Abs. err |
|-------|------:|---------:|---------:|
| 7075-O | 103 | 466 | 363 |
| 2024-O | 75 | 375 | 300 |
| 8081-T6 | 70 | 329 | 259 |
| 2014-O | 97 | 343 | 246 |
| 7068-T6511 | 700 | 485 | 215 |

**Titanium — top 5 worst LOO predictions:**

| Alloy | Truth | LOO pred | Abs. err |
|-------|------:|---------:|---------:|
| Gamma-TiAl (4822) | 450 | 1057 | 607 |
| Ti-15Mo | 540 | 893 | 353 |
| Ti-29Nb-13Ta-4.6Zr | 815 | 1093 | 278 |
| Ti-3Al-2.5V | 585 | 861 | 276 |
| Ti-10V-2Fe-3Al | 1170 | 951 | 219 |

**Nickel — top 5 worst LOO predictions:**

| Alloy | Truth | LOO pred | Abs. err |
|-------|------:|---------:|---------:|
| Inconel 718 | 1100 | 515 | 585 |
| Inconel 718-Solution | 380 | 895 | 515 |
| Hastelloy C-2000 | 345 | 743 | 398 |
| Inconel 617 | 290 | 674 | 384 |
| ATI-718Plus | 1170 | 789 | 381 |

_cached 0s ago_  _(29.6s to compute)_

---


## How to regenerate

```bash
# fast refresh (CALPHAD, TTT, precipitation, briefs, cost, holdout)
python -m apps.api.ml.eval.unified_scorecard --refresh all

# include the slow runners too (Scheil, LOO, ablation — multi-minute)
python -m apps.api.ml.eval.unified_scorecard --refresh all --include-slow

# selective — only one or two sections
python -m apps.api.ml.eval.unified_scorecard --refresh sprint5_precipitation

# emit to stdout instead of docs/SCORECARD.md
python -m apps.api.ml.eval.unified_scorecard --out -
```
