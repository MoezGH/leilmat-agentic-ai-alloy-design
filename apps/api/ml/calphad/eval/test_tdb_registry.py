"""
Contract tests for the CALPHAD database registry (databases.py).

Background — why these exist
----------------------------
Found while preparing the open-source release (2026-10).  Three independent
defects combined to produce a confident, wrong answer for stainless steel:

1. ``mc_fecocrnbti_steels.tdb`` is a trimmed test extract that models only
   Fe, Cr, Co, Nb and Ti — yet the registry claimed 17 elements, so twelve
   (Ni, Mo, Si, C, Mn, Al, W, V, Cu, B, N, O) were advertised with no
   thermodynamic data behind them.
2. ``cost507_al_alloys.tdb`` is an *aluminium*-alloy assessment, but its long
   element list let Fe-Cr-Ni steels route to it.  AISI 304/316 at 1100 C came
   back as 99.8% ordered BCC_B2; the real answer is FCC austenite.
3. The 304 SS scorecard row used ``relaxed=True`` plus (0.0, 1.0) bounds, so
   it could not fail, and it counted as a pass.

These tests pin the contracts that would have caught each of them.
"""
from __future__ import annotations

import pytest

from apps.api.ml.calphad import databases as D
from apps.api.ml.alloy_datasets import weight_to_atomic

pycalphad = pytest.importorskip("pycalphad")


def _modelled_elements(path) -> set[str]:
    """Elements that appear in at least one PARAMETER of the TDB."""
    from pycalphad import Database
    dbf = Database(str(path))
    els: set[str] = set()
    for p in dbf._parameters.all():
        for sub in p["constituent_array"]:
            for sp in sub:
                els.update(c.upper() for c in sp.constituents.keys())
    return {e for e in els if e not in ("VA", "/-")}


# ── 1. A registry may only claim elements its file actually models ──────────

@pytest.mark.parametrize("entry", D._BUNDLED, ids=lambda e: e.path.name)
def test_tdb_registry_matches_file_contents(entry):
    """Every element a registry entry claims must carry >= 1 parameter in the file.

    Declaring an ELEMENT in a TDB is not the same as modelling it: a component
    with no PARAMETERs is silently treated as zero-energy, which gives plausible
    looking but meaningless equilibria.
    """
    if not entry.path.exists():
        pytest.skip(f"{entry.path.name} not present")
    claimed = {e for e in entry.elements if e != "VA"}
    modelled = _modelled_elements(entry.path)
    overclaimed = sorted(claimed - modelled)
    assert not overclaimed, (
        f"{entry.path.name} registers {overclaimed} but the file has no "
        f"parameters for them — remove them from the registry entry."
    )


# ── 2. Fe/Ni/Co-based alloys must not be answered from the Al-alloy database ─

STAINLESS_304 = {"Fe": 71.0, "C": 0.05, "Cr": 18.5, "Ni": 9.0, "Mn": 1.5, "Si": 0.5}
STAINLESS_316 = {"Fe": 67.0, "C": 0.05, "Cr": 17.0, "Ni": 12.0, "Mo": 2.5,
                 "Mn": 1.5, "Si": 0.5}
INCONEL_718_LIKE = {"Ni": 53.0, "Fe": 18.5, "Cr": 19.0, "Nb": 5.1, "Mo": 3.0,
                    "Ti": 0.9, "Al": 0.5}


@pytest.mark.parametrize("name,wt", [
    ("AISI 304", STAINLESS_304),
    ("AISI 316", STAINLESS_316),
    ("Inconel 718-like", INCONEL_718_LIKE),
])
def test_iron_and_nickel_based_alloys_are_refused_not_misrouted(name, wt):
    """No bundled open database models Fe-Cr-Ni steels or multicomponent Ni-base
    alloys, so lookup must return None (an honest refusal) — never COST507."""
    path = D.lookup_tdb(weight_to_atomic(wt))
    assert path is None, (
        f"{name} was routed to {path.name if path else None}; no bundled "
        f"database is validated for it, so the engine should refuse."
    )


# ── 3. ...but aluminium alloys, including ones with minor Fe/Ni, still work ──

@pytest.mark.parametrize("name,wt", [
    ("6061", {"Al": 97.9, "Mg": 1.0, "Si": 0.6, "Cu": 0.28, "Cr": 0.2}),
    ("7075", {"Al": 90.0, "Zn": 5.6, "Mg": 2.5, "Cu": 1.6, "Cr": 0.23}),
    ("Al-Fe-Si casting (Fe minor)", {"Al": 96.0, "Fe": 1.0, "Si": 3.0}),
    ("2618 (Fe+Ni minor)", {"Al": 93.7, "Cu": 2.3, "Mg": 1.6, "Fe": 1.1, "Ni": 1.0}),
])
def test_aluminium_alloys_still_route_to_cost507(name, wt):
    path = D.lookup_tdb(weight_to_atomic(wt))
    assert path is not None and path.name == "cost507_al_alloys.tdb", (
        f"{name} should still use the Al-alloy database, got {path}"
    )


def test_matrix_exclusion_boundary():
    """The exclusion is about what the alloy is BUILT ON, not what it contains."""
    entry = next(e for e in D._BUNDLED if e.path.name == "cost507_al_alloys.tdb")
    assert entry.valid_for({"AL": 0.60, "FE": 0.40}) is True     # Fe-bearing Al alloy
    assert entry.valid_for({"AL": 0.40, "FE": 0.60}) is False    # Fe-based alloy
    assert entry.valid_for({"AL": 0.30, "NI": 0.35, "CO": 0.35}) is False
    assert entry.valid_for({"AL": 1.0}) is True


def test_systems_only_the_removed_files_covered_are_refused_not_guessed():
    """The Al-Co-Cr-Ni, Al-Cr-Ni, Al-Ni, Al-Zn and C-Fe files were removed (no licence that permits shipping them).
    What only they covered must now be REFUSED; Al-rich Al-Zn is still answered by COST 507."""
    assert D.lookup_tdb({"NI": 0.75, "AL": 0.25}) is None        # Ni-based: COST 507 refuses, nothing else covers
    assert D.lookup_tdb({"FE": 0.99, "C": 0.01}) is None         # Fe-C: mc_fecocrnbti has no C parameters
    assert D.lookup_tdb({"AL": 0.5, "CO": 0.2, "CR": 0.2, "NI": 0.1}) is None
    assert D.lookup_tdb({"AL": 0.9, "ZN": 0.1}).name == "cost507_al_alloys.tdb"


def test_the_removed_files_are_not_registered_or_present():
    removed = {"alcocrni_nibase.tdb", "alcrni_nibase.tdb", "alni_binary.tdb", "alzn_binary.tdb", "cfe_binary.tdb"}
    assert removed.isdisjoint({row["file"] for row in D.list_coverage()})
    assert removed.isdisjoint({p.name for p in D._TDB_DIR.glob("*.tdb")})


# ── 4. The canonical references must be able to fail ────────────────────────

def _all_canonical():
    from apps.api.ml.calphad.eval.equilibrium_runner import ALL_CANONICAL
    return ALL_CANONICAL


def test_no_canonical_reference_is_unfalsifiable():
    """A reference that cannot fail is not a test.  Every row needs at least one
    non-vacuous check: a fraction bound tighter than (0, 1), or a strict /
    allow-listed dominant phase."""
    vacuous = []
    for e in _all_canonical():
        bounds = e.get("expected_phases", {}).values()
        has_real_bound = any(lo > 0.0 or hi < 1.0 for lo, hi in bounds)
        relaxed_without_allowlist = e.get("relaxed") and not e.get("acceptable_dominant")
        if not has_real_bound and (e.get("relaxed") or not e.get("dominant_phase")):
            vacuous.append(e["name"])
        if relaxed_without_allowlist and not has_real_bound:
            vacuous.append(e["name"])
    assert not vacuous, f"unfalsifiable canonical references: {sorted(set(vacuous))}"


def test_stainless_reference_is_austenite_dominant_and_strict():
    ref = next(e for e in _all_canonical() if e["name"].startswith("304 SS"))
    assert ref["dominant_phase"] == "FCC_A1"
    assert not ref.get("relaxed"), "the 304 row must not use the relaxed escape hatch"
    lo, hi = ref["expected_phases"]["FCC_A1"]
    assert lo >= 0.5, "austenite must be required to dominate"


def test_relaxed_means_allow_list_not_skip(monkeypatch):
    """Behavioural regression for the runner.  'relaxed' used to make the
    dominant-phase check pass unconditionally.  Feed it the exact wrong answer
    the engine once gave for 304 SS and require that it FAILS."""
    from apps.api.ml.calphad.eval import equilibrium_runner as R

    monkeypatch.setattr(
        R, "phase_assemblage_sync",
        lambda comp, T: {"phases": {"BCC_B2": 0.998, "GRAPHITE": 0.002},
                         "source": "stub", "tdb": "stub.tdb", "error": None},
    )
    base = {"name": "stub", "composition": {"Fe": 1.0}, "T_K": 1000.0,
            "dominant_phase": "FCC_A1", "relaxed": True,
            "expected_phases": {"FCC_A1": (0.0, 1.0)}}   # vacuous bound, as before

    # relaxed, no allow-list  => strict equality => must FAIL
    assert R._evaluate_entry(dict(base))["outcome"] == "fail"

    # relaxed WITH an allow-list that names the returned phase => passes
    ok = dict(base, acceptable_dominant=["FCC_A1", "BCC_B2"])
    assert R._evaluate_entry(ok)["outcome"] == "pass"

    # relaxed with an allow-list that does NOT name it => fails
    bad = dict(base, acceptable_dominant=["FCC_A1", "BCC_A2"])
    assert R._evaluate_entry(bad)["outcome"] == "fail"
