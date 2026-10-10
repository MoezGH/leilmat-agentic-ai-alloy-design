# Third-party notices

LeilMat's source code is MIT-licensed (see `LICENSE`). The items below are **not** covered by
that licence; they keep the terms of their owners. This file is a good-faith inventory, not legal
advice — items marked **verify** have not been confirmed against the upstream source.

## Data bundled in this repository

| Item | Where | Terms |
|---|---|---|
| CALPHAD thermodynamic databases (7 `.tdb` files) | `models/calphad_tdbs/` | **Per-file, and not uniform.** One is derived from MatCalc under **ODbL 1.0** (share-alike); one is labelled by its author *"for testing purposes only — not for research"*; redistribution terms of the COST 507 file are **verify**. Full table in `models/calphad_tdbs/README.md`. |
| Alloy property values (yield strength, composition, temper) | `apps/api/ml/alloy_datasets.py`, `apps/api/ml/datasets/`, `apps/api/ml/eval/holdout_alloys.py` | Individual property values are transcribed from public handbooks and manufacturer datasheets (ASM Handbooks, Special Metals, Haynes International, ASTM/AMS specifications, MatWeb, and cited papers). The source of each row is recorded in its `source` field. Values are facts, but the sources keep their copyright; do not treat this as a licence to redistribute the source documents. |
| Aging-schedule values | `apps/api/ml/datasets/aging_schedules.py` | As above; each entry carries a `confidence` tag and a citation. Entries tagged `low`/`medium` are **not** verified against a primary source. |
| Formation-energy reference values | `apps/api/ml/eval/canonical_phases.py` | Computed values from the **Materials Project** (CC BY 4.0). Please cite Jain et al., *APL Materials* 1, 011002 (2013). Live queries additionally require the user's own MP API key and are subject to the MP terms of use. |
| Experimental ΔHf values | `apps/api/ml/eval/calorimetry_benchmark.py` | Attributed to NIST WebBook/JANAF, Kubaschewski et al., Meschel & Kleppa, Hultgren et al. **These 25 values were compiled by the maintainers and have NOT been verified row-by-row against those sources** — see "Data quality" below. |

## Model weights and trained artifacts

| Item | Terms |
|---|---|
| M3GNet-Eform-MP-2018.6.1 weights (fetched at image-build time, **not** stored in this repo) | Published by the matgl maintainers on Hugging Face (`materialyze`). Trained on Materials Project data (CC BY 4.0). **verify** the model card's licence. |
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

Declared in `apps/api/requirements.txt` and `apps/web/package.json`. To the best of our
knowledge these are permissively licensed (MIT / BSD / Apache-2.0), but no machine-generated
licence report has been produced yet. **Before release, generate one** (for example
`pip-licenses` and `license-checker`) and attach it here.

## Data quality — read this before relying on any benchmark number

The project's selling point is that its validation numbers are honest, so the limits of the
reference data are stated here rather than buried.

- **Verified so far:** the 8 nickel external-validation yield strengths were checked against
  manufacturer datasheets; **5 of the 8 were wrong** and were corrected (see the git log entry
  "verify all 8 nickel OOD reference values"). Four aging schedules were verified against manufacturer bulletins; the rest are
  tagged `medium`/`low` confidence in `aging_schedules.py`.
- **Not yet verified:** the aluminium and titanium external-validation sets, the four holdout
  sets, the 25 calorimetry ΔHf references, and the training-set property values in general.
  Given the nickel audit's error rate, treat headline accuracy figures for these as
  **provisional**.
- **Downstream dependency:** the `experimental_estimate` formation-energy correction
  (`apps/api/ml/experimental_correction.py`) was fitted on the 25 unverified calorimetry
  references, so its reported leave-one-out error inherits that uncertainty.
