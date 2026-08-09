# LeilMat — Unified Validation Scorecard

_Generated 2026-08-09T14:19:32+00:00_  ·  source-of-truth for SCIENTIFIC_ROADMAP.md and README.md sprint headlines.  Regenerate with `python -m apps.api.ml.eval.unified_scorecard --refresh all`.

Each section reads from a JSON cache at `apps/api/ml/eval/_cache/<key>.json`.  Slow sections (Scheil, Taichi KWC, LOO) are not refreshed unless `--include-slow` or an explicit `--refresh <key>` is passed; nightly CI runs the slow set.

---

## Sprint 1 — CALPHAD equilibrium phase fractions

_pycalphad equilibrium against 15 canonical reference points across Al / Fe / Ni / Ti / Cu (Massalski + ternary)._

**13 / 14 canonical references pass** (93%)  ·  total runtime 11.6s.

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

_cached 77d ago_  _(11.6s to compute)_

---

## Sprint 2 (Scheil) — Scheil-Gulliver solidification

_Non-equilibrium freezing curves on canonical castings — mushy zone, hot-tearing tendency._

_Section is slow (sprint2_scheil); skipped on the fast path.  Run `--refresh sprint2_scheil` or `--include-slow` to populate._

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

_cached 77d ago_  _(0.0s to compute)_

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
| aluminum |          5 |           5 |                15 |                100% |           0 |          0 |
| titanium |          5 |           5 |               113 |                100% |           0 |          0 |
| nickel   |          5 |           5 |                68 |                100% |           0 |          0 |
| steel    |          6 |           4 |                95 |                100% |           2 |          0 |

_cached 0s ago_  _(1.2s to compute)_

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

_cached 77d ago_  _(0.0s to compute)_

---

## Sprint 6 — Strengthening feature ablation

_5-fold CV MAE at L1/L2/L3/L4 feature levels — shows where temper one-hot and engineered physics features pay rent._

_Section is slow (sprint6_ablation); skipped on the fast path.  Run `--refresh sprint6_ablation` or `--include-slow` to populate._

---

## Sprint 7 — Inverse-design canonical briefs

_5 engineering briefs (Al wing skin, Ti implant, Ni turbine, steel, Marine Al) through the qEHVI + feasibility-filter stack._

Inverse-design canonical briefs — BoTorch qEHVI wrapped in the hard-constraint feasibility layer.

| Brief | feasible / total | family match | top YS (MPa) | elapsed (s) |
|-------|------------------|--------------|-------------:|------------:|
| Aerospace Al wing skin | 2/8 | 0.6 | 287.0 | 3.58 |
| Ti orthopaedic implant | 0/8 | 1.0 | None | 0.88 |
| Ni-base turbine disc | 7/8 | 1.0 | 981.0 | 1.21 |
| Low-cost structural steel | 0/8 | 1.0 | None | 1.68 |
| Marine Al 5xxx | 7/8 | 1.0 | 96.0 | 1.09 |

_cached 77d ago_  _(8.4s to compute)_

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

_cached 77d ago_  _(0.0s to compute)_

---

## Sprint 9 — Literature RAG with citation enforcement

_Deferred — blocked on redistributable corpus._

❌ **Deferred** — Sprint 9 (Literature RAG + citation enforcement) is blocked on a redistributable authoritative corpus (ASM Handbook, Donachie, Boyer, Reed, Polmear are all paywalled).  Auto-fetched arXiv + NIST + OSTI alternative was judged insufficient.  See the re-entry checklist in `SCIENTIFIC_ROADMAP.md` and the auto-fetch implementation sketch preserved in this plan file's git history.

---

## Sprint Appendix A — M3GNet formation energy (optional)

_Random-substitution supercell vs MP-PBE reference values.  Skipped automatically if `matgl` is not installed._

⚠ **Section skipped** — matgl not installed (No module named 'matgl').

Install with `pip install matgl` to enable the M3GNet formation-energy section.

_cached 77d ago_  _(0.0s to compute)_

---

## Sprint Appendix B — Leave-one-out YS residuals

_Worst-case LOO residuals per family — re-fits the RF per held-out alloy._

_Section is slow (ys_loo); skipped on the fast path.  Run `--refresh ys_loo` or `--include-slow` to populate._

---

## Sprint Appendix C — MP formation-energy stress test (hundreds-scale)

_Production formation-energy predictor vs PBE-DFT over hundreds of stable MP compounds across alloy systems — with a predict-zero baseline.  Records which predictor (M3GNet vs Miedema fallback) ran.  Needs MP_API_KEY._

_Section is slow (mp_formation_stress); skipped on the fast path.  Run `--refresh mp_formation_stress` or `--include-slow` to populate._

---

## Sprint Appendix D — M3GNet quaternary predictions (12 representative compositions)

_Direct M3GNet predictions on 12 4-element engineering alloy compositions (Ni-Cr-Al-Ti, Al-Zn-Mg-Cu, Fe-Cr-Ni-Mo, …).  MP has no stable ordered quaternary intermetallics for these systems; no MP_API_KEY needed._

**12/12 quaternary compositions** predicted by M3GNet (m3gnet_dft ×12).

> MP has no stable ordered quaternary intermetallics for engineering alloy systems (solid solutions, not ordered phases).  This section reports raw M3GNet extrapolations — no DFT reference available.

- Mean predicted ΔHf: **-230 meV/atom** (range -507 – 46 meV/atom).

| Composition | System | ΔHf (meV/at) | Uncertainty |
|-------------|--------|-------------:|------------:|
| Ni-Cr-Al-Ti (γ' zone) | Ni/Cr/Al/Ti | -361 | ±307 |
| Ni-Co-Cr-Al (Co-bearing) | Ni/Co/Cr/Al | -196 | ±307 |
| Ni-Fe-Cr-Mo (austenitic) | Ni/Fe/Cr/Mo | -122 | ±307 |
| Al-Zn-Mg-Cu (7xxx-like) | Al/Zn/Mg/Cu | -242 | ±307 |
| Al-Mg-Si-Cu (6xxx-like) | Al/Mg/Si/Cu | -258 | ±307 |
| Al-Cu-Mg-Zn (equimolar) | Al/Cu/Mg/Zn | -241 | ±307 |
| Ti-Al-V-Cr (equimolar) | Ti/Al/V/Cr | -242 | ±307 |
| Ti-Al-Nb-Mo (near-β) | Ti/Al/Nb/Mo | -507 | ±307 |
| Fe-Cr-Ni-Mo (stainless) | Fe/Cr/Ni/Mo | -94 | ±307 |
| Fe-Cr-Mn-Ni (equimolar) | Fe/Cr/Mn/Ni | -92 | ±307 |
| Mo-Nb-Ti-Al (refractory) | Mo/Nb/Ti/Al | -446 | ±307 |
| Co-Cr-Al-W (CMSX-like) | Co/Cr/Al/W | 46 | ±307 |

_cached 43d ago_  _(113.5s to compute)_

---

## Sprint Appendix E — M3GNet vs experimental ΔHf (calorimetry)

_M3GNet formation energy benchmarked against experimental calorimetry values (NIST WebBook, CALPHAD tables) — not MP-PBE.  Closes the DFT-error gap; no network needed._

**25 intermetallics** benchmarked against experimental ΔHf from NIST WebBook / CALPHAD assessments (not MP-PBE).  Predictor: **m3gnet_dft ×25**.

- **MAE 232 meV/atom** vs experiment (median 223, max 512).
- Naive predict-zero baseline: 133 meV/atom → model **✗ does NOT beat** the baseline.
- Conformal-envelope coverage: 96%.

_Higher MAE vs experiment than vs MP-PBE is expected: DFT errors compound with GNN errors.  This section quantifies the combined gap._

_cached 43d ago_  _(88.2s to compute)_

---

## Sprint Appendix F — Yield strength — external OOD validation

_Yield-strength predictions on alloys from published commercial datasheets (MatWeb, ASM Alloy Digest) — truly OOD, not in training. Tests conformal interval coverage on unseen alloy families._

Yield-strength prediction on alloys sourced exclusively from published commercial datasheets — **truly external OOD** (not in training set).

**Aluminum** — 8 alloys
  MAE 48 MPa · envelope coverage 100% · 8 predicted / 0 refused

**Titanium** — 8 alloys
  MAE 93 MPa · envelope coverage 75% · 8 predicted / 0 refused

**Nickel** — 8 alloys
  MAE 169 MPa · envelope coverage 88% · 8 predicted / 0 refused

_cached 1s ago_  _(1.2s to compute)_

---

## Sprint Appendix G — HEA formation energy + cross-module consistency

_Two sub-tests: (G1) M3GNet on near-equimolar HEA compositions (Cantor, AlCoCrFeNi, …); (G2) sign-agreement between CALPHAD stable-phase predictions and M3GNet ΔHf for 18 canonical phases._

**G1 — HEA formation energy** — 10 near-equimolar multi-principal-element alloys.  Predictor: **m3gnet_dft ×10**.

- **MAE 243 meV/atom** (median 235, max 432).
- Naive predict-zero baseline: 107 meV/atom → model **✗ does NOT beat** the baseline.
- Conformal-envelope coverage: 100%.

**G2 — CALPHAD / M3GNet sign agreement** — 13/13 canonical phases have consistent stability sign (**100%**).

_All canonical phases consistent — no sign disagreements._

_cached 43d ago_  _(29.2s to compute)_

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
