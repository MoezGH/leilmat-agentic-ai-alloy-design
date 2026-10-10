# Contributing to LeilMat

Thanks for helping. LeilMat's value is that its numbers are **honest** — every prediction
carries uncertainty and provenance, and every claim is backed by a validation row that can
fail. Most of the guidelines below exist to protect that.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r apps/api/requirements.txt

# Trained models are not in git (pickles execute code when loaded). Train once:
python -m apps.api.ml.training            # a few minutes; downloads matbench steels

python -m pytest apps/api -q              # ~3 min; M3GNet tests skip without `matgl`
python -m apps.api.ml.eval.unified_scorecard   # regenerate docs/SCORECARD.md
```

Copy `.env.example` to `.env` for the optional integrations (OpenRouter, Materials Project,
Daytona cloud sims). Nothing in `.env` is required for the core science modules, and `.env`
is gitignored — never commit it.

## Rules that protect the science

1. **A validation reference must be able to fail.** No `(0.0, 1.0)` fraction bounds, no
   check that is skipped, no tolerance widened until a row passes. If the engine gets a row
   wrong, the row stays red and we document why. (A 304-stainless reference once "passed" at
   99.8 % of the wrong phase because it could not fail — see
   `apps/api/ml/calphad/eval/test_tdb_registry.py`.)
2. **Refuse rather than extrapolate.** If no validated model/database covers an input, return a
   clear refusal with a reason, not a plausible-looking number.
3. **Cite every data row, and say how sure you are.** Property values need a `source`. If you
   typed a number from memory, say so — and verify it against a primary source before it feeds
   a benchmark. Reference sets that have not been audited are listed in `NOTICE.md`; the one
   audit done so far found 5 of 8 values wrong.
4. **Never tune against the held-out set.** Holdout and external-OOD alloys are blocklisted from
   training (`alloy_datasets._append_extended`); don't prune training data to improve a
   validation score, and don't select only the favourable corrections when fixing references.
5. **Publish negative results.** A change that doesn't help is still worth a commit message
   and, if it's easy to retry by mistake, a test or comment that records why it fails.
6. **Don't claim what a data file doesn't contain.** A database that *declares* an element is
   not a database that *models* it (`test_tdb_registry_matches_file_contents`).

## Pull requests

- Keep PRs focused; include tests for new behaviour and the scorecard section you affected.
- Run the full suite. Tests that need optional heavy dependencies must skip cleanly, not fail.
- Do **not** commit trained models (`models/*.pkl`), `.env` files, third-party PDFs or
  datasets, or anything with credentials or hostnames.
- New bundled data (databases, datasets, weights) needs its licence recorded in `NOTICE.md`.
  If you can't establish that it's redistributable, don't add it.

## Licence

By contributing you agree your contribution is licensed under the project's MIT licence.
