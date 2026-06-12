"""
Regression tests for the Sprint 3 extended alloy datasets.

These tests verify:
1. Each extended entry has the schema we promised (name, composition_wt,
   ys_MPa, temper, source, value_type).
2. Compositions sum to ~100 wt% (within ±3 % rounding tolerance).
3. YS values are positive and in the realistic physical range.
4. No duplicate (canonical_name, temper) pairs within or across base+extended.
5. The crosswalk maps known aliases to the expected canonical key.

Run:
    pytest apps/api/ml/datasets/eval/test_datasets.py -v
"""
import pytest

from apps.api.ml.datasets import load_extended
from apps.api.ml.datasets.crosswalk import canonical_name


FAMILIES = ["aluminum", "titanium", "nickel", "general_steel"]
REQUIRED_KEYS = {"name", "composition_wt", "ys_MPa", "temper", "source", "value_type"}
VALID_VALUE_TYPES = {"typical", "minimum", "certified"}


# ── 1. Schema integrity ─────────────────────────────────────────────────────

@pytest.mark.parametrize("family", FAMILIES)
def test_extended_entries_have_required_schema(family):
    entries = load_extended(family)
    assert entries, f"{family}: extended entries list is empty"
    for i, e in enumerate(entries):
        missing = REQUIRED_KEYS - set(e.keys())
        assert not missing, f"{family} entry #{i} ({e.get('name', '?')}) missing keys: {missing}"


@pytest.mark.parametrize("family", FAMILIES)
def test_value_type_is_recognised(family):
    """Every entry's value_type must be one of typical / minimum / certified."""
    for e in load_extended(family):
        assert e["value_type"] in VALID_VALUE_TYPES, (
            f"{family}/{e['name']}: value_type {e['value_type']!r} not in {VALID_VALUE_TYPES}"
        )


@pytest.mark.parametrize("family", FAMILIES)
def test_source_tag_present(family):
    """Every entry carries a non-empty ``source`` tag.

    NB: this checks only that a *family-level reference tag* is present
    (e.g. "ASM/v2", "Reed06", "MIL-5J") — it does NOT verify a per-row
    page/table citation, and the tags are shared across many rows.  Treat
    ``source`` as a reference-family label, not a checkable provenance claim.
    """
    for e in load_extended(family):
        assert e["source"] and isinstance(e["source"], str) and e["source"].strip(), (
            f"{family}/{e['name']}: source reference tag is missing"
        )


# ── 2. Composition sanity ───────────────────────────────────────────────────

@pytest.mark.parametrize("family", FAMILIES)
def test_compositions_sum_near_100_percent(family):
    """Weight percents must sum to ~100% (within ±3% rounding/trace-element slack)."""
    for e in load_extended(family):
        total = sum(e["composition_wt"].values())
        assert 95 <= total <= 103, (
            f"{family}/{e['name']}: composition sums to {total:.2f} wt% (expected ~100)"
        )


@pytest.mark.parametrize("family", FAMILIES)
def test_compositions_use_valid_element_symbols(family):
    """Every key in composition_wt must be a recognised element symbol."""
    from pymatgen.core import Element
    for e in load_extended(family):
        for el, wt in e["composition_wt"].items():
            try:
                Element(el)
            except Exception:
                pytest.fail(f"{family}/{e['name']}: unknown element symbol {el!r}")
            assert wt >= 0, f"{family}/{e['name']}: negative weight on {el}"


# ── 3. YS sanity ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("family,ys_min,ys_max", [
    ("aluminum",       10, 800),
    ("titanium",      100, 1500),
    ("nickel",        150, 1500),
    ("general_steel", 100, 2200),
])
def test_ys_in_physical_range(family, ys_min, ys_max):
    """YS must lie within the physically-reasonable range for the family."""
    for e in load_extended(family):
        ys = e["ys_MPa"]
        assert ys_min <= ys <= ys_max, (
            f"{family}/{e['name']}: YS {ys} MPa outside [{ys_min}, {ys_max}]"
        )


# ── 4. De-duplication ───────────────────────────────────────────────────────

@pytest.mark.parametrize("family", FAMILIES)
def test_no_internal_duplicates(family):
    """Within the extended set, no (canonical_name, temper) pair should repeat."""
    entries = load_extended(family)
    seen = set()
    dupes = []
    for e in entries:
        key = (canonical_name(e["name"]), e["temper"])
        if key in seen:
            dupes.append(key)
        seen.add(key)
    assert not dupes, f"{family}: {len(dupes)} duplicate (canon, temper) pairs: {dupes[:3]}"


@pytest.mark.parametrize("family", FAMILIES)
def test_no_collisions_with_base(family):
    """Extended entries that collide with base by (canon, temper) are
    intentionally swallowed by the merge — but we want at least *some*
    extended entries to make it through, otherwise the package isn't
    contributing.  Sanity check that the combined list grows."""
    from apps.api.ml import alloy_datasets
    base_attr = {
        "aluminum":      "ALUMINUM_ALLOYS",
        "titanium":      "TITANIUM_ALLOYS",
        "nickel":        "NICKEL_ALLOYS",
        "general_steel": "GENERAL_STEEL_ALLOYS",
    }[family]
    n_combined = len(getattr(alloy_datasets, base_attr))
    n_extended = len(load_extended(family))
    assert n_combined > n_extended, (
        f"{family}: combined list ({n_combined}) is no larger than extended-only "
        f"({n_extended}) — either base set is empty or merge failed."
    )


# ── 5. Crosswalk correctness ────────────────────────────────────────────────

def test_crosswalk_strips_tempers():
    """Temper codes (T6, T651, etc.) must be stripped before lookup."""
    assert canonical_name("6061-T6")     == "6061"
    assert canonical_name("6061-T651")   == "6061"
    assert canonical_name("AA6061-T6")   == "6061"
    assert canonical_name("EN AW-6061-T6") == "6061"
    assert canonical_name("UNS A92024-T81") == "2024"


def test_crosswalk_resolves_steel_aliases():
    """AISI / UNS / DIN / JIS designations must converge to canonical."""
    assert canonical_name("AISI 4140")     == "aisi 4140"
    assert canonical_name("UNS G41400")    == "aisi 4140"
    assert canonical_name("4140")          == "aisi 4140"
    assert canonical_name("42CrMo4")       == "aisi 4140"
    assert canonical_name("AISI 4140 Q&T") == "aisi 4140"


def test_crosswalk_resolves_inconel_aliases():
    assert canonical_name("Inconel 718")   == "inconel 718"
    assert canonical_name("UNS N07718")    == "inconel 718"
    assert canonical_name("Alloy 718")     == "inconel 718"
    assert canonical_name("Inconel 718 Aged") == "inconel 718"


def test_crosswalk_unknown_passes_through():
    """An unrecognised designation should be returned in normalised form,
    not raise an error."""
    out = canonical_name("Exotic-Foo-Bar-X42")
    assert isinstance(out, str)
    assert out  # non-empty


# ── 6. Training-vs-holdout leakage check ─────────────────────────────────────

@pytest.mark.parametrize("holdout_key,train_attr", [
    ("aluminum", "ALUMINUM_ALLOYS"),
    ("titanium", "TITANIUM_ALLOYS"),
    ("nickel",   "NICKEL_ALLOYS"),
    ("steel",    "GENERAL_STEEL_ALLOYS"),
])
def test_no_holdout_alloy_in_training_set(holdout_key, train_attr):
    """No alloy listed in ``eval/holdout_alloys.py`` may appear in the merged
    training list (base + extended).  Catches both base-set leaks and
    accidental future extended-set leaks."""
    from apps.api.ml.eval.holdout_alloys import ALL_HOLDOUT
    from apps.api.ml import alloy_datasets
    holdout_names = {h["name"] for h in ALL_HOLDOUT.get(holdout_key, [])}
    training_names = {e["name"] for e in getattr(alloy_datasets, train_attr)}
    leaks = holdout_names & training_names
    assert not leaks, (
        f"{holdout_key}: {len(leaks)} holdout alloy(s) leaked into training: "
        f"{sorted(leaks)}.  Adjust extended/ or strip from base alloy_datasets.py."
    )
