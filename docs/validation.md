# Validation

LeilMat's central claim is not that its models are accurate — it is that **you can see how
accurate they are, and that the checks are able to fail.** This page explains how that is built,
what is and isn't verified today, and how to add to it without weakening it.

The numbers themselves live in [`SCORECARD.md`](SCORECARD.md). It is generated, never edited by
hand, and it — not the README — is the source of truth.

## The unified scorecard

`apps/api/ml/eval/unified_scorecard.py` is a CLI that runs every validation section, caches each
section's result as JSON, and renders them into `docs/SCORECARD.md`.

```bash
python -m apps.api.ml.eval.unified_scorecard                    # fast path: reuse cached results
python -m apps.api.ml.eval.unified_scorecard --list             # sections, cache keys, which are slow
python -m apps.api.ml.eval.unified_scorecard --refresh <key>    # recompute one section
python -m apps.api.ml.eval.unified_scorecard --include-slow     # also recompute the slow ones
python -m apps.api.ml.eval.unified_scorecard --out other.md     # write elsewhere
```

Results are cached in `apps/api/ml/eval/_cache/<key>.json` (git-ignored); a section shows how old its
cache is. Slow sections (Scheil, leave-one-out, strengthening ablation, the Materials Project stress
test) are only recomputed when asked.

## What is validated, in tiers

| Tier | What it checks | Where |
|---|---|---|
| **Canonical references** | CALPHAD phase fractions against textbook points; formation energy against Materials Project values for stable phases; KWN precipitation against TEM/SAXS data; TTT curves; hierarchical cost against list prices | `ml/*/eval/` |
| **Holdout sets** | Yield strength on alloys per family that are *blocklisted from training* | `ml/eval/holdout_alloys.py` |
| **External out-of-distribution** | Yield strength on commercial alloys taken from manufacturer datasheets, also blocklisted | `holdout_alloys.py` → `ys_ood_external` |
| **Stress tests** | Formation energy over hundreds of Materials Project compounds; quaternary predictions; comparison with experimental calorimetry; high-entropy alloys; cross-module consistency | `unified_scorecard` appendices |

The training pipeline refuses to ingest any alloy that appears in a holdout or external set
(`alloy_datasets._append_extended`), so a later dataset expansion cannot quietly leak test data
into training.

## Rules that keep it honest

These are enforced by tests where they can be, and by review where they can't.

1. **A reference must be able to fail.** Every canonical reference needs at least one check with
   a real bound. A row whose bounds are `(0.0, 1.0)` and whose dominant-phase check is skipped
   proves nothing. `relaxed` no longer means "skip the check": it means "accept any phase in an
   explicit `acceptable_dominant` list" (typically TDB naming aliases such as `FCC_L12` /
   `L12_FCC`), and with no list it falls back to strict equality.
2. **Don't widen a tolerance to make a row pass.** If the engine is wrong, the row stays red and
   we write down why. For example, Fe-Cr-Ni steels are *refused* by the CALPHAD engine because no
   bundled open database models them; that shows as an error in the scorecard rather than being
   hidden.
3. **Contract tests guard what files claim.** A thermodynamic database may only be registered
   for elements it carries parameters for (`test_tdb_registry_matches_file_contents`).
4. **Never tune on the held-out data.** Don't prune training data to improve a holdout score, and
   don't apply only the favourable corrections when you fix reference values.
5. **Record negative results where they'll be found.** If an approach is a measured dead end, leave
   the evidence in the code. Example: replacing Orowan *bypass* with APB *shearing* for nickel
   cannot change a tree model's output (the two features have Spearman ρ ≈ 0.998 at a fixed
   per-temper radius), and a test fails if that ever stops being true.

## Data quality

Validation is only as good as its reference values, and **those have not all been checked.**

- **Audited:** the 8 nickel external-validation yield strengths were compared against manufacturer
  datasheets. **Five of the eight were wrong** and were corrected. A handful of aging schedules were
  verified against manufacturer bulletins; the rest carry a `confidence` tag
  (`high` / `medium` / `low`) in `ml/datasets/aging_schedules.py`.
- **Audited, and rebuilt:** the experimental calorimetry values for formation energy. Checked against
  two published compilations (Kim et al. 2017 and the Kingsbury compilation, both distributed with
  `matminer`), 11 of the 12 compounds that could be checked had a wrong hand-compiled value (typically half
  the true magnitude). The other 13 had no independent value and were removed. The benchmark now holds 12
  verified values (M3GNet MAE 127 meV/atom against experiment), and the linear "experimental correction"
  that had been fitted on the wrong numbers is switched off.
- **Not yet audited:** the aluminium and titanium external sets, the four holdout sets, and the
  training-set property values in general.

Treat accuracy figures that depend on those as **provisional**. [`NOTICE.md`](../NOTICE.md) keeps
the current list. If you verify a set, please contribute the correction and update the list.

## Adding a validation row or section

1. **Pick a reference you can cite** — a manufacturer datasheet, a standard, or a primary paper —
   and record the citation in the row. If you typed a number from memory, say so and verify it
   before it feeds a benchmark.
2. **Make it falsifiable.** Choose bounds that a wrong answer would violate. Add
   `acceptable_dominant` if a phase has alias names.
3. **For a new section**, add a `SectionSpec` to `SECTIONS` in `unified_scorecard.py` with a
   `cache_key`, a `runner` (returns JSON-serialisable data), a `renderer` (returns Markdown) and
   `is_slow`. Lazy-import heavy dependencies inside the runner.
4. **Add a test** with a stub predictor so it runs without network access or optional packages;
   see `ml/eval/test_calorimetry_benchmark.py` for the pattern.
5. Regenerate: `python -m apps.api.ml.eval.unified_scorecard --refresh <your-key>`.
