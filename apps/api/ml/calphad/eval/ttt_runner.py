"""
Exercises the Kirkaldy-Venugopalan TTT model against canonical Fe-C-X steels.

Usage (CLI)
-----------
    python -m apps.api.ml.calphad.eval.ttt_runner
"""
from __future__ import annotations

from typing import Any

from apps.api.ml.calphad.eval.canonical_ttt import CANONICAL_TTT
from apps.api.ml.calphad.ttt import ttt_diagram


def _evaluate(entry: dict) -> dict[str, Any]:
    out = ttt_diagram(entry["composition_wt"], austenite_grain_um=15.0)
    result: dict[str, Any] = {
        "name": entry["name"],
        "source": out.get("source"),
        "predicted": out.get("noses_ttt"),
        "critical_T_C": out.get("critical_T_C"),
        "checks": [],
        "error": out.get("error"),
    }
    if out.get("error") or out["value"] is None:
        result["outcome"] = "error"
        return result

    p = out["noses_ttt"]["pearlite"]
    b = out["noses_ttt"]["bainite"]
    Ms_pred = out["critical_T_C"]["Ms"]

    # Pearlite nose T within ±70 °C
    p_T_ok = abs(p["T_nose_C"] - entry["ref_pearlite_T_C"]) <= 70
    result["checks"].append({"check": "pearlite_T", "expected": entry["ref_pearlite_T_C"],
                             "actual": p["T_nose_C"], "passed": p_T_ok})

    # Pearlite nose t within factor of 5
    t_ratio = max(p["t_nose_s"], 0.01) / max(entry["ref_pearlite_t_s"], 0.01)
    p_t_ok = 0.2 <= t_ratio <= 5.0
    result["checks"].append({"check": "pearlite_t", "expected": entry["ref_pearlite_t_s"],
                             "actual": p["t_nose_s"], "passed": p_t_ok,
                             "ratio": round(t_ratio, 2)})

    # Upper-bainite nose T within ±70 °C
    b_T_ok = abs(b["T_nose_C"] - entry["ref_bainite_T_C"]) <= 70
    result["checks"].append({"check": "bainite_T", "expected": entry["ref_bainite_T_C"],
                             "actual": b["T_nose_C"], "passed": b_T_ok})

    # Bainite nose t within factor of 5
    b_t_ratio = max(b["t_nose_s"], 0.01) / max(entry["ref_bainite_t_s"], 0.01)
    b_t_ok = 0.2 <= b_t_ratio <= 5.0
    result["checks"].append({"check": "bainite_t", "expected": entry["ref_bainite_t_s"],
                             "actual": b["t_nose_s"], "passed": b_t_ok,
                             "ratio": round(b_t_ratio, 2)})

    # Ms within ±30 °C (Andrews)
    Ms_ok = abs(Ms_pred - entry["ref_Ms_C"]) <= 30
    result["checks"].append({"check": "Ms", "expected": entry["ref_Ms_C"],
                             "actual": Ms_pred, "passed": Ms_ok})

    result["outcome"] = "pass" if all(c["passed"] for c in result["checks"]) else "fail"
    return result


def run_all() -> dict[str, Any]:
    results = [_evaluate(e) for e in CANONICAL_TTT]
    n_pass = sum(1 for r in results if r["outcome"] == "pass")
    return {
        "n_total": len(results),
        "n_pass": n_pass,
        "pass_rate": round(n_pass / len(results), 3) if results else 0.0,
        "results": results,
    }


if __name__ == "__main__":
    summary = run_all()
    print(f"\nTTT runner — {summary['n_total']} steels")
    print(f"  PASS {summary['n_pass']}/{summary['n_total']} ({summary['pass_rate']:.0%})\n")
    for r in summary["results"]:
        status = "✓" if r["outcome"] == "pass" else ("✗" if r["outcome"] == "fail" else "E")
        print(f"  [{status}] {r['name']}")
        if r["outcome"] == "error":
            print(f"       ERROR: {r['error']}")
            continue
        p = r["predicted"]["pearlite"]
        b = r["predicted"]["bainite"]
        Ms = r["critical_T_C"]["Ms"]
        print(f"       pearlite nose ({p['T_nose_C']}°C, {p['t_nose_s']}s)  "
              f"bainite ({b['T_nose_C']}°C, {b['t_nose_s']}s)  Ms={Ms}°C")
        for c in r["checks"]:
            if not c["passed"]:
                print(f"       ✗ {c['check']}: expected {c['expected']}, got {c['actual']}")
