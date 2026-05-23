"""
Print a markdown scorecard for the yield-strength prediction models.

Combines:
  - Held-out canonical alloy predictions (production model, out-of-training)
  - Leave-one-out CV stats (re-fit per fold, in-training honest residuals)
  - Stored CV MAE from training-time 5-fold CV

Run:
    python -m apps.api.ml.eval.scorecard
    python -m apps.api.ml.eval.scorecard --no-loo   # skip the slow LOO step
"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path
from typing import Any

from apps.api.ml.eval.holdout_runner import run_all as run_holdout_all
from apps.api.ml.eval.loo_validation import all_loo

MODELS_DIR = Path(__file__).parent.parent.parent.parent.parent / "models"

_FAMILY_TO_PKL = {
    "aluminum": "aluminum_ys_rf.pkl",
    "titanium": "titanium_ys_rf.pkl",
    "nickel":   "nickel_ys_rf.pkl",
    "steel":    "yield_strength_rf.pkl",
}


def _stored_cv_mae(family: str) -> dict[str, Any] | None:
    path = MODELS_DIR / _FAMILY_TO_PKL[family]
    if not path.exists():
        return None
    with open(path, "rb") as f:
        bundle = pickle.load(f)
    return {
        "cv_mae_MPa": bundle.get("cv_mae_MPa"),
        "n_samples":  bundle.get("n_samples"),
        "y_range":    f"{bundle.get('y_min', 0):.0f}–{bundle.get('y_max', 0):.0f}",
    }


def print_scorecard(skip_loo: bool = False) -> None:
    holdout = run_holdout_all()
    loo     = {} if skip_loo else all_loo()

    print("# LeilMat — Yield-Strength Validation Scorecard\n")

    # ── Top-line summary table ──────────────────────────────────────────
    print("## Summary\n")
    print("| Family   | n train | CV MAE | LOO MAE | In-dom. MAE | OOD correct | OOD missed | False-positive |")
    print("|----------|--------:|-------:|--------:|------------:|------------:|-----------:|---------------:|")

    for family in ("aluminum", "titanium", "nickel", "steel"):
        stored = _stored_cv_mae(family) or {}
        h = holdout.get(family, {})
        l = loo.get(family, {}) if not skip_loo else {}

        n_train = stored.get("n_samples", "?")
        cv_mae  = f"{stored.get('cv_mae_MPa', 0):.0f}" if stored.get("cv_mae_MPa") else "n/a"
        loo_mae = f"{l.get('loo_mae', 0):.0f}" if l.get("loo_mae") is not None else "—"
        h_mae   = f"{h.get('mae', 0):.0f}" if h.get("mae") is not None else "—"
        ood_ok   = h.get('n_correct_refuse', 0)
        ood_miss = h.get('n_unexpected_refuse', 0)
        fp       = h.get('n_unexpected_predict', 0)

        print(f"| {family:<8} | {n_train:>7} | {cv_mae:>6} | {loo_mae:>7} | {h_mae:>11} | {ood_ok:>11} | {ood_miss:>10} | {fp:>14} |")

    print()
    print("> **CV MAE** = stored 5-fold cross-val MAE (MPa).")
    print("> **LOO MAE** = leave-one-out CV (MPa). Not run for steels — too slow.")
    print("> **In-dom. MAE** = production-model error on hold-out alloys flagged `expected_in_domain=True` (MPa).")
    print("> **OOD correct** = held-out alloys correctly refused by the OOD gate.")
    print("> **OOD missed** = in-domain alloys the gate over-aggressively refused (false-negative).")
    print("> **False-positive** = OOD alloys the gate let through (most dangerous — would return wrong predictions).\n")

    # ── Held-out alloy detail per family ────────────────────────────────
    for family in ("aluminum", "titanium", "nickel", "steel"):
        h = holdout.get(family, {})
        if not h.get("predictions") and not h.get("refusals"):
            continue
        print(f"## Held-out — {family.capitalize()}\n")
        if h.get("predictions"):
            print("### Predictions\n")
            print("| Alloy | YS lit. | YS pred. | Abs. err | Unc. (±) | OOD ratio | Outcome |")
            print("|-------|--------:|---------:|---------:|---------:|----------:|---------|")
            for p in h["predictions"]:
                marker = "✓" if p.get("in_envelope") else "⚠"
                outcome = "✓ predict" if p["outcome"] == "correct_predict" else "✗ FALSE-POSITIVE"
                ratio_txt = f"{p.get('ood_ratio'):.2f}" if p.get('ood_ratio') is not None else "—"
                print(f"| {p['name']} | {p['y_true']:.0f} | {p['y_pred']:.0f} | {p['abs_err']:.0f} {marker} | {p['uncertainty']:.0f} | {ratio_txt} | {outcome} |")
            print()
        if h.get("refusals"):
            print("### Refusals (OOD-gated)\n")
            print("| Alloy | YS lit. | OOD ratio | Outcome |")
            print("|-------|--------:|----------:|---------|")
            for r in h["refusals"]:
                ratio_txt = f"{r.get('ood_ratio'):.2f}" if r.get('ood_ratio') is not None else "—"
                outcome = "✓ correct OOD refusal" if r["outcome"] == "correct_refuse" else "⚠ over-cautious refusal"
                print(f"| {r['name']} | {r['y_true']:.0f} | {ratio_txt} | {outcome} |")
            print()

    # ── LOO worst cases per family ──────────────────────────────────────
    if not skip_loo:
        print("## Leave-one-out worst cases (Al / Ti / Ni)\n")
        for family in ("aluminum", "titanium", "nickel"):
            l = loo.get(family, {})
            if not l.get("residuals"):
                continue
            worst = l["residuals"][:5]
            print(f"### {family.capitalize()} — top 5 abs-error\n")
            print("| Alloy | Truth | LOO pred | Abs. error |")
            print("|-------|------:|---------:|-----------:|")
            for r in worst:
                print(f"| {r['name']} | {r['y_true']:.0f} | {r['y_pred']:.0f} | {r['abs_err']:.0f} |")
            print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Print yield-strength validation scorecard")
    parser.add_argument("--no-loo", action="store_true", help="skip leave-one-out CV (faster)")
    args = parser.parse_args()
    print_scorecard(skip_loo=args.no_loo)


if __name__ == "__main__":
    main()
