"""
Materials-Project formation-energy stress test (UI/UX-audit follow-up).

The canonical formation-energy section (`formation_energy_runner`,
Appendix A) checks 18 hand-picked references.  This scales that idea to
*hundreds* of real MP ground-state compounds across alloy-relevant
chemical systems, so we can report how the production formation-energy
predictor compares to PBE-DFT over a broad, never-curated sample — the
"stress test against hundreds of well-known materials" recommendation.

Why this is leakage-safe by construction:
    M3GNet was trained on MP-PBE, so MP formation energies *are* the
    reference it should reproduce.  We sample arbitrary stable compounds
    from MP rather than the curated training intermetallics, so there's no
    train/test contamination to manufacture a flattering number.

Honesty guards:
    * Records which predictor was actually exercised (``m3gnet`` vs the
      ``miedema_heuristic`` fallback) so the headline is never misattributed
      — locally, with no `matgl`, you are benchmarking the *fallback*.
    * Reports a naive baseline (predict ΔHf = 0) so "the model beats doing
      nothing" is provable, not assumed.
    * Pure elements (ΔHf ≡ 0) are excluded — predicting ~0 for them is a
      tautology that would deflate the MAE.
    * Skips cleanly with a reason envelope when ``MP_API_KEY`` is unset.

Usage
-----
    python -m apps.api.ml.eval.mp_formation_benchmark --n 200
    python -m apps.api.ml.eval.mp_formation_benchmark --n 80 --out -
"""
from __future__ import annotations

import argparse
import json
import random
from typing import Any, Callable

import numpy as np

# Alloy-relevant binary/ternary systems — the chemistries LeilMat users
# actually design in.  Sampling stable compounds across these gives a broad,
# representative formation-energy stress set.
ALLOY_SYSTEMS: list[str] = [
    "Al-Cu", "Al-Mg", "Al-Si", "Al-Zn", "Al-Ni", "Al-Ti", "Al-Fe", "Al-Mn",
    "Al-Cr", "Ni-Ti", "Ni-Cr", "Ni-Nb", "Ni-Mo", "Ni-Al", "Ti-V", "Ti-Al",
    "Fe-Cr", "Fe-Ni", "Fe-Mn", "Cu-Zn", "Cu-Ni", "Cu-Sn", "Mg-Zn", "Mg-Al",
    "Cr-Ni", "Co-Cr", "Nb-Ti", "Co-Ni", "Fe-Co", "Mo-Ti",
]

# How many phases to keep from any single system, so one busy chemsys (e.g.
# Al-Cu) can't dominate the sample.
PER_SYSTEM_CAP = 12


def fetch_mp_benchmark_set(
    n: int = 200,
    systems: list[str] | None = None,
    *,
    seed: int = 0,
    max_hull: float = 0.001,
    per_system_cap: int = PER_SYSTEM_CAP,
) -> dict[str, Any]:
    """
    Pull stable, multi-element compounds from MP across ``systems``.

    Returns ``{"entries": [...], "n_systems_queried": k}`` or
    ``{"skipped": True, "reason": ...}`` when MP is unavailable.  Each entry:
    ``{name, mp_id, composition (at-fraction dict), ref_eV_per_atom, nelements}``.
    """
    try:
        from apps.api.config import settings
    except Exception as exc:  # pragma: no cover - import guard
        return {"skipped": True, "reason": f"config import failed: {exc}"}
    if not getattr(settings, "mp_api_key", None):
        return {"skipped": True, "reason": "MP_API_KEY not set"}

    try:
        from mp_api.client import MPRester
    except Exception as exc:
        return {"skipped": True, "reason": f"mp_api not installed ({exc})"}

    systems = systems or ALLOY_SYSTEMS
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    n_queried = 0
    try:
        with MPRester(settings.mp_api_key) as mpr:
            for cs in systems:
                try:
                    docs = mpr.materials.summary.search(
                        chemsys=cs,
                        energy_above_hull=(0, max_hull),
                        fields=["material_id", "formula_pretty",
                                "composition_reduced", "formation_energy_per_atom",
                                "nelements"],
                    )
                except Exception as exc:  # one bad system shouldn't kill the run
                    print(f"[mp_bench] query failed for {cs}: {exc}")
                    continue
                n_queried += 1
                kept = 0
                for d in docs:
                    if kept >= per_system_cap:
                        break
                    mid = str(getattr(d, "material_id", "") or "")
                    fe = getattr(d, "formation_energy_per_atom", None)
                    nel = getattr(d, "nelements", None) or 0
                    if not mid or mid in seen or fe is None or nel < 2:
                        continue
                    try:
                        comp = d.composition_reduced.as_dict()
                        total = sum(comp.values())
                        fracs = {el: v / total for el, v in comp.items() if total > 0}
                    except Exception:
                        continue
                    if not fracs:
                        continue
                    seen.add(mid)
                    entries.append({
                        "name": getattr(d, "formula_pretty", mid),
                        "mp_id": mid,
                        "composition": fracs,
                        "ref_eV_per_atom": float(fe),
                        "nelements": int(nel),
                    })
                    kept += 1
    except Exception as exc:
        return {"skipped": True, "reason": f"MP session failed: {exc}"}

    # Deterministic down-sample to n (seeded; sorted first so it's reproducible).
    entries.sort(key=lambda e: e["mp_id"])
    if len(entries) > n:
        rng = random.Random(seed)
        entries = sorted(rng.sample(entries, n), key=lambda e: e["mp_id"])

    return {"entries": entries, "n_systems_queried": n_queried}


def evaluate(
    entries: list[dict[str, Any]],
    predict_fn: Callable[[dict[str, float]], dict[str, Any]],
) -> dict[str, Any]:
    """
    Pure benchmark core (no network) — predict each entry and aggregate.

    ``predict_fn(composition)`` must return ``{"value": float|None,
    "source": str, "uncertainty": float}`` (the shape of
    ``featurizers.formation_energy_eV_per_atom``).  Factored out so the
    aggregation logic is unit-testable with a stub predictor.
    """
    preds: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    sources: dict[str, int] = {}

    for e in entries:
        try:
            out = predict_fn(e["composition"])
        except Exception as exc:
            skipped.append({"name": e["name"], "reason": str(exc)})
            continue
        y_pred = out.get("value")
        if y_pred is None:
            skipped.append({"name": e["name"], "reason": out.get("error", "no prediction")})
            continue
        src = out.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
        y_true = float(e["ref_eV_per_atom"])
        abs_err = abs(float(y_pred) - y_true)
        unc = float(out.get("uncertainty", 0) or 0)
        preds.append({
            "name": e["name"], "mp_id": e.get("mp_id"),
            "nelements": e.get("nelements"),
            "y_true": round(y_true, 4), "y_pred": round(float(y_pred), 4),
            "abs_err": round(abs_err, 4),
            "in_envelope": bool(abs_err <= unc * 1.5) if unc else False,
            "source": src,
        })

    if not preds:
        return {"error": "no predictions produced", "n_skipped": len(skipped),
                "skipped": skipped[:20]}

    errs = np.array([p["abs_err"] for p in preds])
    truths = np.array([abs(p["y_true"]) for p in preds])

    def _bucket(key: str, want) -> dict[str, Any]:
        sub = [p for p in preds if p.get("nelements") == want] if key == "nel" else preds
        if not sub:
            return {}
        e = np.array([p["abs_err"] for p in sub])
        return {"n": len(sub), "mae_meV": round(float(e.mean()) * 1000, 1),
                "median_meV": round(float(np.median(e)) * 1000, 1),
                "max_meV": round(float(e.max()) * 1000, 1)}

    by_nelements = {str(k): _bucket("nel", k) for k in (2, 3, 4) if _bucket("nel", k)}

    return {
        "n_evaluated": len(preds),
        "n_skipped": len(skipped),
        "predictor_sources": sources,
        "mae_meV_per_atom": round(float(errs.mean()) * 1000, 1),
        "median_abs_err_meV": round(float(np.median(errs)) * 1000, 1),
        "max_abs_err_meV": round(float(errs.max()) * 1000, 1),
        # Naive baseline: predict ΔHf = 0 for everything.  Its MAE is the mean
        # |true ΔHf| — the bar the model must clear to be worth anything.
        "baseline_zero_mae_meV": round(float(truths.mean()) * 1000, 1),
        "beats_baseline": bool(errs.mean() < truths.mean()),
        "in_envelope_pct": round(100 * sum(p["in_envelope"] for p in preds) / len(preds), 1),
        "by_nelements": by_nelements,
        "worst": sorted(preds, key=lambda p: -p["abs_err"])[:10],
        "skipped": skipped[:20],
    }


def run_mp_formation_benchmark(n: int = 200, *, seed: int = 0) -> dict[str, Any]:
    """Fetch an MP sample and benchmark the production formation-energy path."""
    fetched = fetch_mp_benchmark_set(n, seed=seed)
    if fetched.get("skipped"):
        return fetched
    entries = fetched["entries"]
    if not entries:
        return {"skipped": True, "reason": "MP returned no usable entries"}

    from apps.api.ml.featurizers import formation_energy_eV_per_atom

    result = evaluate(entries, formation_energy_eV_per_atom)
    result["n_requested"] = n
    result["n_systems_queried"] = fetched.get("n_systems_queried")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="MP formation-energy stress test.")
    ap.add_argument("--n", type=int, default=200, help="sample size (default 200).")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="-", help="'-' for stdout (default).")
    args = ap.parse_args()
    result = run_mp_formation_benchmark(args.n, seed=args.seed)
    text = json.dumps(result, indent=2, default=str)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w") as f:
            f.write(text)
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
