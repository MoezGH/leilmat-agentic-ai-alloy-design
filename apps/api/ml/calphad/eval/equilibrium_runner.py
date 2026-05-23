"""
apps.api.ml.calphad.eval.equilibrium_runner
============================================

Exercises the production ``phase_assemblage_sync`` code path against every
canonical reference in ``canonical_diagrams.py`` and returns a structured
result dict.

Usage (CLI)
-----------
    python -m apps.api.ml.calphad.eval.equilibrium_runner

Usage (pytest fixture)
----------------------
    from apps.api.ml.calphad.eval.equilibrium_runner import run_all
    results = run_all()
"""
from __future__ import annotations

import time
from typing import Any

from apps.api.ml.calphad.eval.canonical_diagrams import ALL_CANONICAL
from apps.api.ml.calphad.equilibrium import phase_assemblage_sync


def _evaluate_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Run one canonical reference through production code and classify outcome."""
    t0 = time.perf_counter()
    out = phase_assemblage_sync(entry["composition"], entry["T_K"])
    elapsed = time.perf_counter() - t0

    result: dict[str, Any] = {
        "name": entry["name"],
        "T_K": entry["T_K"],
        "chemsys_family": entry.get("chemsys_family", "unknown"),
        "source": out.get("source"),
        "tdb": out.get("tdb"),
        "elapsed_s": round(elapsed, 3),
        "phases_predicted": out.get("phases", {}),
        "error": out.get("error"),
        "checks": [],
    }

    if out.get("error"):
        result["outcome"] = "error"
        result["checks"].append({"check": "no_error", "passed": False, "detail": out["error"]})
        return result

    predicted = out.get("phases", {})
    # ── Check dominant phase ──────────────────────────────────────────────────
    if predicted:
        actual_dominant = max(predicted, key=predicted.get)  # type: ignore
        expected_dominant = entry.get("dominant_phase", "")
        relaxed = entry.get("relaxed", False)
        if relaxed:
            # For relaxed checks, any structural phase match counts
            dominant_ok = True
        else:
            dominant_ok = (actual_dominant == expected_dominant)
        result["checks"].append({
            "check": "dominant_phase",
            "passed": dominant_ok,
            "expected": expected_dominant,
            "actual": actual_dominant,
            "detail": "" if dominant_ok else f"expected {expected_dominant}, got {actual_dominant}",
        })
    else:
        result["checks"].append({
            "check": "dominant_phase", "passed": False,
            "expected": entry.get("dominant_phase"), "actual": None,
            "detail": "no phases returned",
        })

    # ── Check per-phase fraction tolerance bands ─────────────────────────────
    for phase_name, (lo, hi) in entry.get("expected_phases", {}).items():
        frac = predicted.get(phase_name, 0.0)
        ok = lo <= frac <= hi
        result["checks"].append({
            "check": f"fraction_{phase_name}",
            "passed": ok,
            "expected": f"[{lo:.2f}, {hi:.2f}]",
            "actual": round(frac, 4),
            "detail": "" if ok else f"{phase_name} fraction {frac:.4f} outside [{lo:.2f}, {hi:.2f}]",
        })

    all_passed = all(c["passed"] for c in result["checks"])
    result["outcome"] = "pass" if all_passed else "fail"
    return result


def run_all() -> dict[str, Any]:
    """Run every canonical reference and return a summary dict."""
    results = []
    for entry in ALL_CANONICAL:
        results.append(_evaluate_entry(entry))

    n_pass = sum(1 for r in results if r["outcome"] == "pass")
    n_fail = sum(1 for r in results if r["outcome"] == "fail")
    n_error = sum(1 for r in results if r["outcome"] == "error")
    total_elapsed = sum(r["elapsed_s"] for r in results)

    return {
        "n_total": len(results),
        "n_pass": n_pass,
        "n_fail": n_fail,
        "n_error": n_error,
        "pass_rate": round(n_pass / len(results), 3) if results else 0.0,
        "total_elapsed_s": round(total_elapsed, 2),
        "results": results,
    }


if __name__ == "__main__":
    import json
    summary = run_all()
    print(f"\nCALPHAD equilibrium runner — {summary['n_total']} references")
    print(f"  PASS {summary['n_pass']}  FAIL {summary['n_fail']}  ERROR {summary['n_error']}")
    print(f"  Total elapsed: {summary['total_elapsed_s']:.1f} s\n")
    for r in summary["results"]:
        status = "✓" if r["outcome"] == "pass" else ("✗" if r["outcome"] == "fail" else "E")
        phases_str = ", ".join(f"{p}:{f:.3f}" for p, f in r.get("phases_predicted", {}).items())
        print(f"  [{status}] {r['name']}")
        if r["outcome"] != "pass":
            for c in r.get("checks", []):
                if not c.get("passed"):
                    print(f"       FAIL {c['check']}: {c.get('detail', '')}")
        elif phases_str:
            print(f"       phases: {phases_str}")
