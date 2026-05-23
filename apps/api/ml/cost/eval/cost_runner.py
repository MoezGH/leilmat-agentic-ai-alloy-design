"""
Exercises the Sprint 8 cost model against every canonical quote.

Usage:
    python -m apps.api.ml.cost.eval.cost_runner
"""
from __future__ import annotations

from typing import Any

from apps.api.ml.cost import compute_cost
from apps.api.ml.cost.eval.canonical_quotes import CANONICAL_QUOTES


def _evaluate(entry: dict) -> dict[str, Any]:
    out = compute_cost(
        composition=entry["composition_wt"],
        form=entry["form"],
        cert=entry["cert"],
        ht=entry["ht"],
        lot_kg=entry["lot_kg"],
    )
    pred = out["USD_per_kg"]
    ref  = entry["quoted_USD_per_kg"]
    if pred is None:
        return {"name": entry["name"], "outcome": "error",
                "predicted": None, "reference": ref}
    ratio = max(pred / ref, ref / pred) if ref > 0 else float("inf")
    return {
        "name":         entry["name"],
        "predicted":    pred,
        "reference":    ref,
        "ratio":        round(ratio, 2),
        "within_25pct": (1.0 / 1.25) <= (pred / ref) <= 1.25,
        "within_50pct": (1.0 / 1.5)  <= (pred / ref) <= 1.5,
        "within_2x":    ratio <= 2.0,
        "outcome":      "pass" if (1.0 / 1.5) <= (pred / ref) <= 1.5 else "fail",
        "family":       out["family"],
        "breakdown":    out["breakdown"],
        "source":       entry["source"],
    }


def run_all() -> dict[str, Any]:
    results = [_evaluate(e) for e in CANONICAL_QUOTES]
    n_total = len(results)
    n_25 = sum(1 for r in results if r.get("within_25pct"))
    n_50 = sum(1 for r in results if r.get("within_50pct"))
    n_2x = sum(1 for r in results if r.get("within_2x"))
    return {
        "n_total":          n_total,
        "n_within_25pct":   n_25,
        "n_within_50pct":   n_50,
        "n_within_2x":      n_2x,
        "pass_rate_25pct":  round(n_25 / n_total, 3) if n_total else 0,
        "pass_rate_50pct":  round(n_50 / n_total, 3) if n_total else 0,
        "pass_rate_2x":     round(n_2x / n_total, 3) if n_total else 0,
        "results":          results,
    }


if __name__ == "__main__":
    s = run_all()
    print(f"\nSprint 8 cost runner — {s['n_total']} canonical quotes")
    print(f"  within ±25 %  : {s['n_within_25pct']:>2}/{s['n_total']}  ({s['pass_rate_25pct']:.0%})")
    print(f"  within ±50 %  : {s['n_within_50pct']:>2}/{s['n_total']}  ({s['pass_rate_50pct']:.0%})")
    print(f"  within factor 2: {s['n_within_2x']:>2}/{s['n_total']}  ({s['pass_rate_2x']:.0%})\n")
    print(f"  {'alloy':<35} {'family':<22} {'pred':>7} {'ref':>7} {'ratio':>6}  ±25%  ±50%")
    for r in s["results"]:
        if r["outcome"] == "error":
            print(f"  [E] {r['name']:<35} reference=${r['reference']}")
            continue
        mark = "✓" if r["within_25pct"] else (" " if r["within_50pct"] else "✗")
        m50  = "✓" if r["within_50pct"] else "✗"
        print(f"  [{mark}] {r['name']:<35} {r['family']:<22} ${r['predicted']:>5.2f} "
              f"${r['reference']:>5.2f} {r['ratio']:>5.2f}×  "
              f"{'✓' if r['within_25pct'] else '✗':>5} {m50:>5}")
