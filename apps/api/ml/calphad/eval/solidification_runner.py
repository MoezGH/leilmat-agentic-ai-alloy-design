"""
Exercises the production scheil_solidification_sync code path against every
canonical casting in canonical_solidification.py.

Usage (CLI)
-----------
    python -m apps.api.ml.calphad.eval.solidification_runner
"""
from __future__ import annotations

import time
from typing import Any

from apps.api.ml.calphad.eval.canonical_solidification import CANONICAL_CASTINGS
from apps.api.ml.calphad.scheil import scheil_solidification_sync


# wt-pct → mole-fraction normalisation (callers may use either; Scheil uses moles)
_AT_MASS = {
    "Al": 26.98, "Si": 28.09, "Mg": 24.31, "Fe": 55.85, "Cu": 63.55,
    "Mn": 54.94, "Zn": 65.38, "Cr": 51.996, "Ni": 58.69, "Ti": 47.87,
    "C": 12.01, "Mo": 95.96, "Co": 58.93, "Nb": 92.91, "V": 50.94,
}


def _wt_to_mol(wt: dict[str, float]) -> dict[str, float]:
    moles = {el: wt_pct / _AT_MASS.get(el, 50.0) for el, wt_pct in wt.items() if wt_pct > 0}
    total = sum(moles.values())
    return {el: m / total for el, m in moles.items()} if total > 0 else {}


def _evaluate(entry: dict) -> dict[str, Any]:
    mole_frac = _wt_to_mol(entry["composition_wt"])
    t0 = time.perf_counter()
    out = scheil_solidification_sync(mole_frac, entry["T_start_K"])
    elapsed = time.perf_counter() - t0

    result: dict[str, Any] = {
        "name": entry["name"],
        "elapsed_s": round(elapsed, 2),
        "source": out.get("source"),
        "tdb": out.get("tdb"),
        "checks": [],
        "predicted": {
            "liquidus_K": out.get("liquidus_K"),
            "solidus_K":  out.get("solidus_K"),
            "mushy_K":    out.get("mushy_zone_K"),
        },
        "active_phases": out.get("active_phases", {}),
        "error": out.get("error"),
    }

    if out.get("error") or out.get("liquidus_K") is None:
        result["outcome"] = "error"
        return result

    # ── Liquidus within ±25 K (Scheil and equilibrium agree here) ─────────
    liq_ok = abs(out["liquidus_K"] - entry["ref_liquidus_K"]) <= 25
    result["checks"].append({
        "check": "liquidus_K",
        "expected": entry["ref_liquidus_K"],
        "actual": out["liquidus_K"],
        "passed": liq_ok,
    })

    # ── Scheil solidus within ±50 K (Scheil-to-Scheil variance across DBs) ──
    sol_ok = abs(out["solidus_K"] - entry["ref_solidus_K"]) <= 50
    result["checks"].append({
        "check": "solidus_K",
        "expected": entry["ref_solidus_K"],
        "actual": out["solidus_K"],
        "passed": sol_ok,
    })

    # ── Mushy zone within ±40 K ───────────────────────────────────────────
    mushy_ok = abs(out["mushy_zone_K"] - entry["ref_mushy_K"]) <= 40
    result["checks"].append({
        "check": "mushy_zone_K",
        "expected": entry["ref_mushy_K"],
        "actual": out["mushy_zone_K"],
        "passed": mushy_ok,
    })

    result["outcome"] = "pass" if all(c["passed"] for c in result["checks"]) else "fail"
    return result


def run_all() -> dict[str, Any]:
    results = [_evaluate(e) for e in CANONICAL_CASTINGS]
    n_pass = sum(1 for r in results if r["outcome"] == "pass")
    return {
        "n_total": len(results),
        "n_pass": n_pass,
        "pass_rate": round(n_pass / len(results), 3) if results else 0.0,
        "total_elapsed_s": round(sum(r["elapsed_s"] for r in results), 1),
        "results": results,
    }


if __name__ == "__main__":
    summary = run_all()
    print(f"\nSolidification runner — {summary['n_total']} castings")
    print(f"  PASS {summary['n_pass']}/{summary['n_total']} "
          f"({summary['pass_rate']:.0%})  ({summary['total_elapsed_s']} s)\n")
    for r in summary["results"]:
        status = "✓" if r["outcome"] == "pass" else "✗"
        print(f"  [{status}] {r['name']}  ({r['elapsed_s']} s)")
        if r["outcome"] == "error":
            print(f"       ERROR: {r['error']}")
        else:
            p = r["predicted"]
            print(f"       liquidus={p['liquidus_K']}, solidus={p['solidus_K']}, mushy={p['mushy_K']} K")
            for c in r["checks"]:
                if not c["passed"]:
                    print(f"       ✗ {c['check']}: expected {c['expected']}, got {c['actual']}")
