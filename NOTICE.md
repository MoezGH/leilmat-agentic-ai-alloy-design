# Third-party notices

LeilMat's source code is MIT-licensed (see `LICENSE`). The items below are **not** covered by
that licence; they keep the terms of their owners. This file is a good-faith inventory, not legal
advice — items marked **verify** have not been confirmed against the upstream source.

## Data bundled in this repository

| Item | Where | Terms |
|---|---|---|
| CALPHAD thermodynamic databases (2 `.tdb` files) | `models/calphad_tdbs/` | **Per-file.** `mc_fecocrnbti_steels.tdb` is a trimmed extract of the MatCalc open database mc_fe 2.060, under **ODbL 1.0** (share-alike; keep this notice; results computed from it should carry the notice in the README of that folder). `cost507_al_alloys.tdb` is the COST 507 light-metal database obtained from opencalphad.com; its redistribution terms are **not yet confirmed**, which gates publication. Five further files (Al-Co-Cr-Ni, Al-Cr-Ni, Al-Ni, Al-Zn, C-Fe) were **removed on 2026-11-01** because none states a licence that permits redistribution (one is labelled by its author "for testing purposes only — not for research"). Full table in `models/calphad_tdbs/README.md`. |
| Alloy property values (yield strength, composition, temper) | `apps/api/ml/alloy_datasets.py`, `apps/api/ml/datasets/`, `apps/api/ml/eval/holdout_alloys.py` | Individual property values are transcribed from public handbooks and manufacturer datasheets (ASM Handbooks, Special Metals, Haynes International, ASTM/AMS specifications, MatWeb, and cited papers). The source of each row is recorded in its `source` field. Values are facts, but the sources keep their copyright; do not treat this as a licence to redistribute the source documents. |
| Aging-schedule values | `apps/api/ml/datasets/aging_schedules.py` | As above; each entry carries a `confidence` tag and a citation. Entries tagged `low`/`medium` are **not** verified against a primary source. |
| Formation-energy reference values | `apps/api/ml/eval/canonical_phases.py` | Computed values from the **Materials Project** (CC BY 4.0). Please cite Jain et al., *APL Materials* 1, 011002 (2013). Live queries additionally require the user's own MP API key and are subject to the MP terms of use. |
| Experimental ΔHf values | `apps/api/ml/eval/calorimetry_benchmark.py` | 12 values, each taken from a published experimental compilation: Kim, Meschel, Nash et al., *Sci. Data* 4, 170162 (2017) (10 values), NIST-JANAF (Mg2Si), Rzyman (FeAl). They are facts, and the compilations are the source to cite and to consult for terms. An earlier hand-compiled set of 25 was retired; see "Data quality" below. |

## Model weights and trained artifacts

| Item | Terms |
|---|---|
| M3GNet-Eform-MP-2018.6.1 weights (**not** stored in this repo) | Published by the matgl maintainers on Hugging Face (`materialyze`); trained on Materials Project data (CC BY 4.0). **No licence statement was found for the weights** (the matgl code is BSD-3-Clause). As of 2026-11 this checkpoint is **no longer downloadable** from that location, so a fresh install cannot load it and formation energy falls back to a labelled heuristic; the maintainers' deployment holds an older copy. Do not redistribute the weights, and do not publish a container image that contains them, until their licence is established. |
| `matbench_steels` dataset (via `matminer`) | **verify** upstream dataset licence. |
| `models/*.pkl` yield-strength models | Trained by this project on the datasets above. Pickle files execute code when loaded — only load files whose SHA-256 you have checked against a published manifest. |

## External simulation tools (run as separate processes, not bundled or linked)

The cloud-compute features install and execute these inside isolated sandboxes. They are not
distributed with, or linked into, this repository, so their licences do not apply to LeilMat's
source — but anyone redistributing built sandbox images should honour them. Each is believed to
be copyleft-family (**verify** exact licence and version):

- **Neper** (polycrystal tessellation) — GPL family
- **SPPARKS** (kinetic Monte Carlo grain growth) — GPL family
- **DAMASK** (crystal-plasticity spectral solver) — GPL/AGPL family
- **MOOSE** (planned phase-field work) — LGPL family

## Python and JavaScript dependencies

Declared in `apps/api/requirements.txt` and `apps/web/package.json`. A licence scan was run on
2026-11-01 over the installed Python environment (227 packages) and the web production dependencies
(about 550 packages):

- **Permissive throughout:** MIT, BSD (2/3-clause), Apache-2.0, ISC and similar account for nearly all of
  them. No GPL or AGPL package was found in either set.
- **LGPL, used as unmodified libraries:** `ase` (LGPL-2.1+) on the Python side, and `sharp-libvips`
  (LGPL-3.0+, a prebuilt image library pulled in by Next.js) on the web side.
- **MPL-2.0:** a few Python packages; file-level copyleft, no effect on this project's own files.
- **No licence field in the package metadata:** `matminer` (its repository's LICENSE is BSD-style, Lawrence
  Berkeley National Laboratory; read 2026-11-01), and, believed but **not verified**: `FiPy` (NIST; software
  written by NIST staff is not subject to copyright in the United States), `chroma-hnswlib` (Apache-2.0), the
  Daytona API clients (Apache-2.0) and `@mapbox/jsonlint-lines-primitives` (a Mapbox fork of JSON Lint,
  MIT-style). Confirm these five against their upstream repositories before a formal compliance review.

Re-run the scan before each release (`pip-licenses`, `license-checker`).

---

## Data quality — read this before relying on any benchmark number

The project's selling point is that its validation numbers are honest, so the limits of the
reference data are stated here rather than buried.

- **Verified so far:** the 8 nickel external-validation yield strengths were checked against
  manufacturer datasheets; **5 of the 8 were wrong** and were corrected (see the git log entry
  "verify all 8 nickel OOD reference values"). Four aging schedules were verified against manufacturer bulletins; the rest are
  tagged `medium`/`low` confidence in `aging_schedules.py`.
- **Audited and rebuilt (2026-11-01):** the calorimetry ΔHf references. Cross-checked against
  the `matminer` experimental formation-enthalpy compilations (Kim et al. 2017; Kingsbury), 12 of
  the original 25 compounds could be checked, and **11 of those 12 were wrong** (typically about
  half the true magnitude). The other 13 had no independent value and were removed. The benchmark now
  holds the 12 verified values.
- **Not yet verified:** the aluminium and titanium external-validation sets, the four holdout
  sets, and the training-set property values in general. Given the audits' error rates, treat headline
  accuracy figures for these as **provisional**.
- **Downstream dependency:** the `experimental_estimate` formation-energy correction
  (`apps/api/ml/experimental_correction.py`) had been fitted on the wrong values. Refitted on the 12
  verified ones it improves the leave-one-out error by only ~6 % (127 → 120 meV/atom), so it is
  **switched off** and the API no longer returns `experimental_estimate`.
