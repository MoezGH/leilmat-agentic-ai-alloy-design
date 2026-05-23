"""
Exercises every canonical brief and returns a structured outcome.

Usage:
    python -m apps.api.ml.eval.brief_runner
"""
from __future__ import annotations

import time
from typing import Any

from apps.api.ml.eval.canonical_briefs import (
    CANONICAL_BRIEFS, EXPECTED_RESULT_FAMILIES,
)
from apps.api.ml.inverse_briefs import run_brief


def _detect_family(comp: dict) -> str | None:
    total = sum(comp.values())
    if total <= 0:
        return None
    fracs = {el: v / total for el, v in comp.items()}
    if (fracs.get("Fe") or 0) >= 0.5: return "general_steel"
    if (fracs.get("Al") or 0) >= 0.8: return "aluminum"
    if (fracs.get("Ti") or 0) >= 0.5: return "titanium"
    if (fracs.get("Ni") or 0) >= 0.4: return "nickel"
    return None


def _evaluate(brief, top_n: int = 5) -> dict[str, Any]:
    t0 = time.perf_counter()
    candidates = run_brief(brief)
    elapsed = time.perf_counter() - t0

    expected = EXPECTED_RESULT_FAMILIES.get(brief.name, {})
    top = candidates[:top_n]
    feasible_top = [c for c in top if c.is_feasible]

    # Family match: do top-N candidates land in the expected family?
    expected_family = expected.get("family")
    family_match = (
        sum(_detect_family(c.composition) == expected_family for c in top) / max(top_n, 1)
        if expected_family else None
    )

    # YS sanity: top feasible candidate's YS should be above the expected min
    ys_min = expected.get("expected_ys_min")
    top_feasible = feasible_top[0] if feasible_top else None
    top_ys = (
        top_feasible.properties.get("_details", {})
            .get("yield_strength_MPa", {}).get("value")
        if top_feasible else None
    )
    ys_ok = (ys_min is None) or (top_ys is not None and top_ys >= ys_min - 50)

    result = {
        "name":              brief.name,
        "elapsed_s":         round(elapsed, 2),
        "n_total":           len(candidates),
        "n_feasible":        sum(c.is_feasible for c in candidates),
        "top_n":             top_n,
        "family_match_rate": family_match,
        "expected_family":   expected_family,
        "top_ys":            top_ys,
        "ys_min":            ys_min,
        "ys_ok":             ys_ok,
        "candidates": [
            {
                "rank": i + 1,
                "composition": c.composition,
                "family_detected": _detect_family(c.composition),
                "is_feasible": c.is_feasible,
                "violations": c.feasibility_violations,
                "aggregate_score": round(c.aggregate_score, 3),
                "ys_MPa": c.properties.get("_details", {})
                              .get("yield_strength_MPa", {}).get("value"),
                "density_g_cm3": c.properties.get("density_g_cm3"),
            }
            for i, c in enumerate(top)
        ],
    }
    return result


def run_all(briefs=None, top_n: int = 5) -> list[dict]:
    briefs = briefs or CANONICAL_BRIEFS
    return [_evaluate(b, top_n=top_n) for b in briefs]


if __name__ == "__main__":
    print("Sprint 7 — canonical-brief runner\n")
    for r in run_all():
        print(f"### {r['name']}  ({r['elapsed_s']} s)")
        print(f"  total={r['n_total']}  feasible={r['n_feasible']}/{r['n_total']}  "
              f"family_match={r['family_match_rate']!r}  top_ys={r['top_ys']}  "
              f"ys_ok={r['ys_ok']}")
        for c in r["candidates"]:
            comp = ", ".join(f"{el}:{v:.1f}" for el, v in c["composition"].items() if v >= 1)
            feas = "✓" if c["is_feasible"] else "✗"
            print(f"    {feas} #{c['rank']:>2} [{c['family_detected'] or 'OOD':<14}]  {comp:<55}  "
                  f"YS={c['ys_MPa']}  ρ={c['density_g_cm3']}  score={c['aggregate_score']}")
        print()
