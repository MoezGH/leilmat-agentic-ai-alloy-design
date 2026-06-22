"""Unit tests for the MP formation-energy stress-test core (no network)."""
from __future__ import annotations

from apps.api.ml.eval.mp_formation_benchmark import evaluate


ENTRIES = [
    {"name": "AlCu", "mp_id": "mp-1", "composition": {"Al": 0.5, "Cu": 0.5},
     "ref_eV_per_atom": -0.20, "nelements": 2},
    {"name": "Ni3Al", "mp_id": "mp-2", "composition": {"Ni": 0.75, "Al": 0.25},
     "ref_eV_per_atom": -0.43, "nelements": 2},
    {"name": "AlCuMg", "mp_id": "mp-3", "composition": {"Al": 0.5, "Cu": 0.25, "Mg": 0.25},
     "ref_eV_per_atom": -0.10, "nelements": 3},
]


def _stub(err: float, source: str = "m3gnet", unc: float = 0.0):
    """Predictor that always returns truth shifted by `err` eV/atom."""
    truth = {tuple(sorted(e["composition"])): e["ref_eV_per_atom"] for e in ENTRIES}
    def fn(comp):
        return {"value": truth[tuple(sorted(comp))] + err, "source": source, "uncertainty": unc}
    return fn


def test_perfect_predictor_has_zero_mae():
    r = evaluate(ENTRIES, _stub(0.0))
    assert r["n_evaluated"] == 3
    assert r["mae_meV_per_atom"] == 0.0
    assert r["beats_baseline"] is True
    assert r["predictor_sources"] == {"m3gnet": 3}


def test_mae_is_in_meV_and_correct():
    # constant 50 meV/atom over-prediction → MAE 50 meV
    r = evaluate(ENTRIES, _stub(0.05))
    assert r["mae_meV_per_atom"] == 50.0
    assert r["max_abs_err_meV"] == 50.0


def test_baseline_is_mean_abs_truth_and_can_lose():
    # baseline (predict 0) MAE = mean(|−0.20|,|−0.43|,|−0.10|) = 0.2433 → 243.3 meV
    r = evaluate(ENTRIES, _stub(0.0))
    assert r["baseline_zero_mae_meV"] == 243.3
    # A predictor worse than the baseline must report beats_baseline False.
    r_bad = evaluate(ENTRIES, _stub(0.5))
    assert r_bad["beats_baseline"] is False


def test_source_attribution_and_skips():
    def fn(comp):
        # Miedema can't price the ternary → returns no value (skipped).
        if len(comp) > 2:
            return {"value": None, "source": "miedema_heuristic"}
        return {"value": 0.0, "source": "miedema_heuristic", "uncertainty": 0}
    r = evaluate(ENTRIES, fn)
    assert r["n_evaluated"] == 2
    assert r["n_skipped"] == 1
    assert r["predictor_sources"] == {"miedema_heuristic": 2}


def test_envelope_coverage():
    # err 30 meV, uncertainty 25 meV → 25*1.5=37.5 ≥ 30 → in envelope.
    r = evaluate(ENTRIES, _stub(0.03, unc=0.025))
    assert r["in_envelope_pct"] == 100.0
