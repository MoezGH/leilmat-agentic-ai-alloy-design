"""
Exercises the KWN solver against every canonical reference and returns
a structured outcome dict.

Usage (CLI)
-----------
    python -m apps.api.ml.precipitation.eval.precipitation_runner
"""
from __future__ import annotations

import time
from typing import Any

from apps.api.ml.precipitation.eval.canonical_kinetics import (
    CANONICAL_KINETICS, KNOWN_LIMITATIONS,
)
from apps.api.ml.precipitation.kwn import simulate_precipitation_sync


def _within_factor(predicted: float, reference: float, factor: float) -> bool:
    """True when ``predicted`` is within ``factor`` of ``reference`` (geometric)."""
    if reference <= 0 or predicted <= 0:
        return predicted == reference
    ratio = max(predicted / reference, reference / predicted)
    return ratio <= factor


def _evaluate(entry: dict) -> dict[str, Any]:
    t0 = time.perf_counter()
    out = simulate_precipitation_sync(
        entry["composition_wt"],
        entry["phase"],
        entry["aging_T_C"],
        entry["aging_time_s"],
    )
    elapsed = time.perf_counter() - t0

    result = {
        "name":       entry["name"],
        "phase":      entry["phase"],
        "elapsed_s":  round(elapsed, 2),
        "source":     out.get("source"),
        "predicted":  None,
        "reference":  {"vf": entry["ref_vf"], "r_nm": entry["ref_radius_nm"]},
        "checks":     [],
    }

    if out.get("value") is None:
        result["outcome"] = "error"
        result["error"]   = out.get("error", "no value")
        return result

    v = out["value"]
    result["predicted"] = {
        "vf":   v["volume_fraction"],
        "r_nm": v["mean_radius_nm"],
        "N":    v["number_density_per_m3"],
    }
    tol = entry["factor_tolerance"]
    vf_ok = _within_factor(v["volume_fraction"], entry["ref_vf"], tol)
    r_ok  = _within_factor(v["mean_radius_nm"],  entry["ref_radius_nm"], tol)
    result["checks"].append({
        "check":     "vf_within_factor",
        "factor":    tol,
        "passed":    vf_ok,
        "predicted": v["volume_fraction"],
        "reference": entry["ref_vf"],
        "ratio":     round(max(v["volume_fraction"] / entry["ref_vf"],
                               entry["ref_vf"] / max(v["volume_fraction"], 1e-9)), 2),
    })
    result["checks"].append({
        "check":     "r_within_factor",
        "factor":    tol,
        "passed":    r_ok,
        "predicted": v["mean_radius_nm"],
        "reference": entry["ref_radius_nm"],
        "ratio":     round(max(v["mean_radius_nm"] / entry["ref_radius_nm"],
                               entry["ref_radius_nm"] / max(v["mean_radius_nm"], 1e-9)), 2),
    })
    result["outcome"] = "pass" if all(c["passed"] for c in result["checks"]) else "fail"
    return result


def run_all() -> dict[str, Any]:
    results = [_evaluate(e) for e in CANONICAL_KINETICS]
    n_pass  = sum(1 for r in results if r["outcome"] == "pass")
    n_fail  = sum(1 for r in results if r["outcome"] == "fail")
    n_error = sum(1 for r in results if r["outcome"] == "error")
    return {
        "n_total":   len(results),
        "n_pass":    n_pass,
        "n_fail":    n_fail,
        "n_error":   n_error,
        "pass_rate": round(n_pass / len(results), 3) if results else 0.0,
        "results":   results,
        "known_limitations": KNOWN_LIMITATIONS,
    }


if __name__ == "__main__":
    s = run_all()
    print(f"\nKWN precipitation runner — {s['n_total']} canonical cases")
    print(f"  PASS {s['n_pass']}  FAIL {s['n_fail']}  ERROR {s['n_error']}  ({s['pass_rate']:.0%})\n")
    for r in s["results"]:
        icon = "✓" if r["outcome"] == "pass" else ("✗" if r["outcome"] == "fail" else "E")
        p = r.get("predicted") or {}
        ref = r["reference"]
        print(f"  [{icon}] {r['name']:35s}  "
              f"vf {p.get('vf', '—')!s:>7} (ref {ref['vf']!s:>5}, factor "
              f"{r['checks'][0].get('ratio', '—')!s:>5})  "
              f"r̄ {p.get('r_nm', '—')!s:>7} nm (ref {ref['r_nm']!s:>5}, factor "
              f"{r['checks'][1].get('ratio', '—')!s:>5})")
        if r["outcome"] == "error":
            print(f"         ERROR: {r.get('error', '?')}")
    print()
    if s["known_limitations"]:
        print("Known limitations (deliberately out of scope):")
        for L in s["known_limitations"]:
            print(f"  - {L['name']}: {L['reason']}")
