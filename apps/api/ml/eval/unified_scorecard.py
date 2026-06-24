"""
Unified validation scorecard for LeilMat.

Aggregates every sprint's runner into a single Markdown document at
``docs/SCORECARD.md`` (or stdout with ``--out -``).  Cache-based: each
section reads its sibling ``_cache/<key>.json`` so consecutive runs of
the unified scorecard are fast (~200 ms).  ``--refresh KEY[,KEY,...]``
or ``--refresh all`` re-executes the runner(s) and overwrites the
cache.  Missing caches are filled on demand the first time the section
is requested.

The unified scorecard exists so the README, the docs site, and CI all
read the same source of truth for sprint-by-sprint acceptance numbers
— ``SCIENTIFIC_ROADMAP.md`` cites the per-sprint headlines, but those
numbers live here and are regenerated from the actual runners.

Section taxonomy
----------------
Each ``SectionSpec`` declares: which sprint it covers, the cache key,
the Python entrypoint to call when refreshing, the Markdown renderer
that converts the runner's dict into a section body, and whether it is
``slow`` (Scheil, LOO, Taichi — multi-minute) so CI can skip those by
default.  Deferred sprints (3.5, 9) are rendered statically.

Usage
-----
    python -m apps.api.ml.eval.unified_scorecard
    python -m apps.api.ml.eval.unified_scorecard --refresh all
    python -m apps.api.ml.eval.unified_scorecard --refresh sprint1_calphad,sprint8_cost
    python -m apps.api.ml.eval.unified_scorecard --include-slow
    python -m apps.api.ml.eval.unified_scorecard --out -            # stdout
    python -m apps.api.ml.eval.unified_scorecard --list             # show sections
"""
from __future__ import annotations

import argparse
import importlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

CACHE_DIR = Path(__file__).parent / "_cache"
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent.parent.parent.parent / "docs" / "SCORECARD.md"
)


# ─────────────────────────────────────────────────────────────────────
# Section spec
# ─────────────────────────────────────────────────────────────────────

@dataclass
class SectionSpec:
    sprint: str                     # display label, e.g. "1" or "2 (Scheil)"
    title: str                      # short title, e.g. "CALPHAD equilibrium"
    cache_key: str                  # filename stem in _cache/, also --refresh key
    runner: Callable[[], Any] | None  # callable that returns the dict to cache
    renderer: Callable[[dict, dict], str]
    is_slow: bool = False
    description: str = ""           # 1-line blurb under the heading


def _format_age(ts_iso: str) -> str:
    """Convert an ISO timestamp into a humanised age string."""
    try:
        t = datetime.fromisoformat(ts_iso)
    except Exception:
        return ts_iso
    age = datetime.now(timezone.utc) - t
    secs = int(age.total_seconds())
    if secs < 90:
        return f"{secs}s ago"
    mins = secs // 60
    if mins < 90:
        return f"{mins}m ago"
    hrs = mins // 60
    if hrs < 36:
        return f"{hrs}h ago"
    return f"{hrs // 24}d ago"


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def _load_cache(key: str) -> dict | None:
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(key: str, payload: dict, elapsed_s: float) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    envelope = {
        "_meta": {
            "key": key,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "elapsed_s": round(elapsed_s, 2),
        },
        "data": payload,
    }
    with open(_cache_path(key), "w") as f:
        json.dump(envelope, f, indent=2, default=str)


def _ensure_cache(spec: SectionSpec, refresh: set[str]) -> dict:
    """Return ``{"_meta": ..., "data": ...}``, either from disk or freshly run."""
    must_refresh = "all" in refresh or spec.cache_key in refresh
    if not must_refresh:
        cached = _load_cache(spec.cache_key)
        if cached is not None:
            return cached
    if spec.runner is None:
        return {"_meta": {"error": "no runner; deferred section"}, "data": {}}
    t0 = time.perf_counter()
    try:
        data = spec.runner()
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        payload = {"error": f"{type(exc).__name__}: {exc}"}
        _save_cache(spec.cache_key, payload, elapsed)
        return {"_meta": {"key": spec.cache_key,
                          "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "elapsed_s": round(elapsed, 2),
                          "error": payload["error"]},
                "data": payload}
    elapsed = time.perf_counter() - t0
    _save_cache(spec.cache_key, data, elapsed)
    return _load_cache(spec.cache_key) or {"_meta": {}, "data": data}


# ─────────────────────────────────────────────────────────────────────
# Section runners — thin wrappers that import lazily
# ─────────────────────────────────────────────────────────────────────

def _run_calphad_equilibrium() -> dict:
    from apps.api.ml.calphad.eval.equilibrium_runner import run_all
    return run_all()


def _run_scheil() -> dict:
    from apps.api.ml.calphad.eval.solidification_runner import run_all
    return run_all()


def _run_ttt() -> dict:
    from apps.api.ml.calphad.eval.ttt_runner import run_all
    return run_all()


def _run_precipitation() -> dict:
    from apps.api.ml.precipitation.eval.precipitation_runner import run_all
    return run_all()


def _run_briefs() -> dict:
    from apps.api.ml.eval.brief_runner import run_all
    return {"briefs": run_all()}


def _run_cost() -> dict:
    from apps.api.ml.cost.eval.cost_runner import run_all
    return run_all()


def _run_holdout() -> dict:
    from apps.api.ml.eval.holdout_runner import run_all as ho
    return ho()


def _run_strengthening_ablation() -> dict:
    from apps.api.ml.strengthening_ablation import run_ablation
    return {"rows": run_ablation()}


def _run_formation_energy() -> dict:
    """M3GNet section.  Returns an error envelope if matgl isn't installed."""
    try:
        importlib.import_module("matgl")
    except ImportError as exc:
        return {"skipped": True, "reason": f"matgl not installed ({exc})"}
    from apps.api.ml.eval.formation_energy_runner import run_formation_energy
    return run_formation_energy()


def _run_loo() -> dict:
    """Leave-one-out residuals per family.  Slow — re-fits per fold."""
    from apps.api.ml.eval.loo_validation import all_loo
    return all_loo()


def _run_mp_formation_stress() -> dict:
    """Hundreds-scale MP formation-energy stress test.  Needs MP_API_KEY +
    network; returns a skip envelope otherwise.  Records which predictor
    (M3GNet vs Miedema fallback) was actually exercised."""
    from apps.api.ml.eval.mp_formation_benchmark import run_mp_formation_benchmark
    return run_mp_formation_benchmark(n=400)


def _run_mp_formation_quaternary() -> dict:
    """Appendix D: quaternary-only MP stress test.  Same harness as Appendix C
    but restricted to 4-element chemical systems."""
    from apps.api.ml.eval.mp_formation_benchmark import (
        run_mp_formation_benchmark, QUATERNARY_SYSTEMS)
    return run_mp_formation_benchmark(n=200, systems=QUATERNARY_SYSTEMS)


def _run_calorimetry() -> dict:
    """Appendix E: M3GNet vs experimental ΔHf from NIST WebBook / CALPHAD tables.
    No network needed — references are hard-coded.  Needs matgl for M3GNet path."""
    from apps.api.ml.eval.calorimetry_benchmark import run_calorimetry_benchmark
    return run_calorimetry_benchmark()


def _run_ys_ood_external() -> dict:
    """Appendix F: yield-strength prediction on alloys sourced exclusively from
    published commercial datasheets — truly external OOD."""
    from apps.api.ml.eval.holdout_runner import run_ood_external
    return run_ood_external()


def _run_hea_and_consistency() -> dict:
    """Appendix G: HEA formation energy + CALPHAD/M3GNet sign-agreement check."""
    from apps.api.ml.eval.hea_benchmark import run_hea_benchmark, run_consistency_check
    return {
        "hea": run_hea_benchmark(),
        "consistency": run_consistency_check(),
    }


# ─────────────────────────────────────────────────────────────────────
# Renderers — each takes (data, meta) and returns the section body
# ─────────────────────────────────────────────────────────────────────

def _meta_footer(meta: dict) -> str:
    """Common cache-freshness footer."""
    if not meta:
        return ""
    parts = []
    if "generated_at" in meta:
        parts.append(f"_cached {_format_age(meta['generated_at'])}_")
    if "elapsed_s" in meta:
        parts.append(f"_({meta['elapsed_s']:.1f}s to compute)_")
    if "error" in meta:
        parts.append(f"_⚠ {meta['error']}_")
    return "  ".join(parts) + "\n" if parts else ""


def _render_error(data: dict, meta: dict, hint: str = "") -> str:
    err = data.get("error") or meta.get("error") or "no data"
    body = f"⚠ Section failed to run: `{err}`.\n"
    if hint:
        body += f"\n_{hint}_\n"
    return body + _meta_footer(meta)


def _render_calphad_equilibrium(data: dict, meta: dict) -> str:
    if "error" in data:
        return _render_error(data, meta, "Re-run with --refresh sprint1_calphad")
    out = [
        f"**{data['n_pass']} / {data['n_total']} canonical references pass** "
        f"({data['pass_rate']:.0%})  ·  total runtime "
        f"{data['total_elapsed_s']:.1f}s.\n",
        "| Reference | Outcome | Notes |",
        "|-----------|:-------:|-------|",
    ]
    for r in data["results"]:
        icon = {"pass": "✓", "fail": "✗", "error": "E"}.get(r["outcome"], "?")
        phases = r.get("phases_predicted") or {}
        if phases:
            note = ", ".join(f"{p} {f:.2f}" for p, f in list(phases.items())[:3])
        else:
            note = r.get("error", "—")
        out.append(f"| {r['name']} | {icon} | {note} |")
    out.append("")
    out.append(_meta_footer(meta))
    return "\n".join(out)


def _render_scheil(data: dict, meta: dict) -> str:
    if "error" in data:
        return _render_error(data, meta, "Re-run with --refresh sprint2_scheil (slow)")
    out = [
        f"**{data['n_pass']} / {data['n_total']} castings pass** "
        f"({data['pass_rate']:.0%})  ·  total runtime "
        f"{data['total_elapsed_s']:.1f}s.\n",
        "| Casting | Outcome | Liquidus K | Solidus K | Mushy K |",
        "|---------|:-------:|-----------:|----------:|--------:|",
    ]
    for r in data["results"]:
        icon = {"pass": "✓", "fail": "✗", "error": "E"}.get(r["outcome"], "?")
        p = r.get("predicted") or {}
        liq = p.get("liquidus_K", "—")
        sol = p.get("solidus_K", "—")
        mushy = p.get("mushy_K", "—")
        out.append(f"| {r['name']} | {icon} | {liq} | {sol} | {mushy} |")
    out.append("")
    out.append(_meta_footer(meta))
    return "\n".join(out)


def _render_ttt(data: dict, meta: dict) -> str:
    if "error" in data:
        return _render_error(data, meta, "Re-run with --refresh sprint2_ttt")
    out = [
        f"**{data['n_pass']} / {data['n_total']} steels pass** "
        f"({data['pass_rate']:.0%}).\n",
        "| Steel | Outcome | Pearlite nose | Bainite nose | Ms |",
        "|-------|:-------:|---------------|--------------|----|",
    ]
    for r in data["results"]:
        icon = {"pass": "✓", "fail": "✗", "error": "E"}.get(r["outcome"], "?")
        if r["outcome"] == "error":
            out.append(f"| {r['name']} | E | — | — | — |")
            continue
        p = r.get("predicted", {})
        pn = p.get("pearlite", {}) or {}
        bn = p.get("bainite", {}) or {}
        ms = (r.get("critical_T_C") or {}).get("Ms", "—")
        out.append(
            f"| {r['name']} | {icon} | "
            f"{pn.get('T_nose_C', '—')}°C / {pn.get('t_nose_s', '—')}s | "
            f"{bn.get('T_nose_C', '—')}°C / {bn.get('t_nose_s', '—')}s | "
            f"{ms}°C |"
        )
    out.append("")
    out.append(_meta_footer(meta))
    return "\n".join(out)


def _render_microstructure_static(data: dict, meta: dict) -> str:
    """Sprint 2.5 + 2.6 have no aggregate runner — they're per-test fixtures.
    Render a static summary pointing at the test counts and docs."""
    return (
        "Microstructure simulators (FiPy schematic + full Taichi anisotropic "
        "KWC dendrite) ship with **16 regression tests** "
        "(8 fast smoke + 8 slow simulation) across the two sprints.  No "
        "aggregate scorecard — each test asserts a specific morphological "
        "or physical invariant (six-arm dendrite, monotone growth, "
        "latent-heat suppression near seed, Karma-Rappel tip-velocity band).\n\n"
        "Validation artifacts: `docs/sprint_2_6/dendrite_morphology.png`, "
        "`tip_velocity.png`, `local_validation.png`.\n\n"
        "_(Static section — no JSON cache.)_\n"
    )


def _render_ys_holdout(data: dict, meta: dict) -> str:
    if "error" in data:
        return _render_error(data, meta, "Re-run with --refresh sprint346_ys_holdout")
    out = [
        "Held-out canonical alloys per family — production model on alloys "
        "never seen during training.  ``In CI`` is the fraction of in-domain "
        "alloys whose literature YS fell inside the 90% conformal interval.\n",
        "| Family | n hold-out | n in-domain | In-dom. MAE (MPa) | In CI (target ≥85%) | OOD correct | False-pos. |",
        "|--------|-----------:|------------:|------------------:|--------------------:|------------:|-----------:|",
    ]
    for fam in ("aluminum", "titanium", "nickel", "steel"):
        h = data.get(fam, {})
        if not h:
            continue
        n_in = len(h.get("predictions", []))
        n_ref = len(h.get("refusals", []))
        mae = h.get("mae")
        mae_s = f"{mae:.0f}" if mae is not None else "—"
        cov = h.get("ci_coverage_pct")
        cov_s = f"{cov:.0f}%" if cov is not None else "—"
        out.append(
            f"| {fam:<8} | {n_in + n_ref:>10} | {n_in:>11} | {mae_s:>17} | "
            f"{cov_s:>19} | {h.get('n_correct_refuse', 0):>11} | "
            f"{h.get('n_unexpected_predict', 0):>10} |"
        )
    out.append("")
    out.append(_meta_footer(meta))
    return "\n".join(out)


def _render_strengthening_ablation(data: dict, meta: dict) -> str:
    if "error" in data:
        return _render_error(data, meta, "Re-run with --refresh sprint6_ablation (slow)")
    rows = data.get("rows", [])
    out = [
        "Per-family CV MAE at four feature levels: L1 composition only · "
        "L2 +temper · L3 +physics · L4 all.  Lower is better.\n",
        "| Family | n | L1 comp | L2 +temper | L3 +physics | L4 all | Δ temper | Δ physics on top |",
        "|--------|--:|--------:|-----------:|------------:|-------:|---------:|-----------------:|",
    ]
    for r in rows:
        out.append(
            f"| {r['family']:<13} | {r['n_samples']:>2} | "
            f"{r.get('L1_comp_mae', '—'):>7} | "
            f"{r.get('L2_comp_temper_mae', '—'):>10} | "
            f"{r.get('L3_comp_physics_mae', '—'):>11} | "
            f"{r.get('L4_comp_temp_phys_mae', '—'):>6} | "
            f"{r.get('delta_L2_vs_L1', '—'):>+7} | "
            f"{r.get('delta_L4_vs_L2', '—'):>+15} |"
        )
    out.append("")
    out.append(_meta_footer(meta))
    return "\n".join(out)


def _render_precipitation(data: dict, meta: dict) -> str:
    if "error" in data:
        return _render_error(data, meta, "Re-run with --refresh sprint5_precipitation")
    out = [
        f"**{data['n_pass']} / {data['n_total']} canonical cases pass** "
        f"({data['pass_rate']:.0%})  ·  factor-of-2-to-4 tolerance on (vf, r̄).\n",
        "| Case | Phase | vf pred / ref / factor | r̄ pred / ref (nm) / factor | Outcome |",
        "|------|-------|------------------------|----------------------------|:-------:|",
    ]
    for r in data["results"]:
        icon = {"pass": "✓", "fail": "✗", "error": "E"}.get(r["outcome"], "?")
        if r["outcome"] == "error":
            out.append(f"| {r['name']} | — | — | — | E |")
            continue
        p = r.get("predicted", {}) or {}
        ref = r.get("reference", {}) or {}
        checks = r.get("checks") or []
        vf_factor = checks[0].get("ratio", "—") if checks else "—"
        r_factor = checks[1].get("ratio", "—") if len(checks) > 1 else "—"
        out.append(
            f"| {r['name']} | {r.get('phase', '—')} | "
            f"{p.get('vf', '—')} / {ref.get('vf', '—')} / {vf_factor}× | "
            f"{p.get('r_nm', '—')} / {ref.get('r_nm', '—')} / {r_factor}× | "
            f"{icon} |"
        )
    out.append("")
    limits = data.get("known_limitations") or []
    if limits:
        out.append("**Known limitations (deliberately out of scope):**\n")
        for L in limits:
            out.append(f"- `{L['name']}`: {L['reason']}")
        out.append("")
    out.append(_meta_footer(meta))
    return "\n".join(out)


def _render_briefs(data: dict, meta: dict) -> str:
    if "error" in data:
        return _render_error(data, meta, "Re-run with --refresh sprint7_briefs")
    briefs = data.get("briefs", [])
    out = [
        "Inverse-design canonical briefs — BoTorch qEHVI wrapped in the "
        "hard-constraint feasibility layer.\n",
        "| Brief | feasible / total | family match | top YS (MPa) | elapsed (s) |",
        "|-------|------------------|--------------|-------------:|------------:|",
    ]
    for r in briefs:
        match = r.get("family_match_rate")
        out.append(
            f"| {r['name']} | {r.get('n_feasible', '?')}/{r.get('n_total', '?')} | "
            f"{match} | {r.get('top_ys', '—')} | {r.get('elapsed_s', '—')} |"
        )
    out.append("")
    out.append(_meta_footer(meta))
    return "\n".join(out)


def _render_cost(data: dict, meta: dict) -> str:
    if "error" in data:
        return _render_error(data, meta, "Re-run with --refresh sprint8_cost")
    out = [
        f"**{data['n_within_2x']} / {data['n_total']} quotes within factor-of-2** "
        f"({data['pass_rate_2x']:.0%})  ·  "
        f"{data['n_within_50pct']}/{data['n_total']} within ±50% "
        f"({data['pass_rate_50pct']:.0%})  ·  "
        f"{data['n_within_25pct']}/{data['n_total']} within ±25% "
        f"({data['pass_rate_25pct']:.0%}).\n",
        "| Alloy | Family | Pred $ | Ref $ | Ratio | ±25% | ±50% |",
        "|-------|--------|------:|------:|------:|:----:|:----:|",
    ]
    for r in data["results"]:
        if r.get("outcome") == "error":
            out.append(f"| {r['name']} | — | — | ${r.get('reference', '—')} | E | — | — |")
            continue
        m25 = "✓" if r.get("within_25pct") else "—"
        m50 = "✓" if r.get("within_50pct") else "—"
        out.append(
            f"| {r['name']} | {r.get('family', '—')} | "
            f"${r.get('predicted', '—'):.2f} | ${r.get('reference', '—'):.2f} | "
            f"{r.get('ratio', '—'):.2f}× | {m25} | {m50} |"
        )
    out.append("")
    out.append(_meta_footer(meta))
    return "\n".join(out)


def _render_formation_energy(data: dict, meta: dict) -> str:
    if data.get("skipped"):
        return (
            f"⚠ **Section skipped** — {data.get('reason', 'matgl not installed')}.\n\n"
            "Install with `pip install matgl` to enable the M3GNet "
            "formation-energy section.\n\n" + _meta_footer(meta)
        )
    if "error" in data:
        return _render_error(data, meta, "Re-run with --refresh m3gnet (slow)")
    out = [
        f"Overall MAE **{data['mae_eV_per_atom']*1000:.0f} meV/atom** over "
        f"{data['n_predicted']} references  ·  envelope coverage "
        f"{data.get('in_envelope_pct', '—')}%.\n",
        "| Class | n | MAE (meV/at) | Median | Max |",
        "|-------|--:|-------------:|-------:|----:|",
    ]
    for cls, stats in (data.get("by_class") or {}).items():
        label = "Pure elements" if cls == "pure_element" else "Intermetallics"
        out.append(
            f"| {label} | {stats['n']} | "
            f"{stats['mae_eV_per_atom']*1000:.0f} | "
            f"{stats['median_abs_err']*1000:.0f} | "
            f"{stats['max_abs_err']*1000:.0f} |"
        )
    out.append("")
    out.append(_meta_footer(meta))
    return "\n".join(out)


def _render_mp_formation(data: dict, meta: dict) -> str:
    if data.get("skipped"):
        return (
            f"⚠ **Section skipped** — {data.get('reason', 'MP unavailable')}.\n\n"
            "Needs `MP_API_KEY` + network (and `matgl` for the M3GNet path; "
            "without it the runner benchmarks the Miedema fallback).  Run "
            "`--refresh mp_formation_stress`.\n\n" + _meta_footer(meta)
        )
    if "error" in data:
        return _render_error(data, meta, "Re-run with --refresh mp_formation_stress")
    srcs = ", ".join(f"{k} ×{v}" for k, v in (data.get("predictor_sources") or {}).items())
    beats = "✓ beats" if data.get("beats_baseline") else "✗ does NOT beat"
    out = [
        f"Stress test over **{data['n_evaluated']} stable MP compounds** "
        f"(sampled from {data.get('n_systems_queried', '—')} alloy systems).  "
        f"Predictor exercised: **{srcs}**.\n",
        f"- **MAE {data['mae_meV_per_atom']:.0f} meV/atom** "
        f"(median {data['median_abs_err_meV']:.0f}, max {data['max_abs_err_meV']:.0f}).",
        f"- Naive predict-zero baseline: {data['baseline_zero_mae_meV']:.0f} meV/atom "
        f"→ model **{beats}** the baseline.",
        f"- Conformal-envelope coverage: {data['in_envelope_pct']:.0f}%.",
        "",
        "| n-elements | n | MAE (meV/at) | Median | Max |",
        "|-----------:|--:|-------------:|-------:|----:|",
    ]
    for nel, s in (data.get("by_nelements") or {}).items():
        out.append(f"| {nel} | {s['n']} | {s['mae_meV']:.0f} | {s['median_meV']:.0f} | {s['max_meV']:.0f} |")
    out.append("")
    out.append(
        "_M3GNet was trained on MP-PBE, so MP is the reference it should "
        "reproduce; sampling arbitrary stable compounds (not the curated "
        "training set) keeps this leakage-free._\n"
    )
    out.append(_meta_footer(meta))
    return "\n".join(out)


def _render_loo(data: dict, meta: dict) -> str:
    if "error" in data:
        return _render_error(data, meta, "Re-run with --refresh ys_loo (slow)")
    out = [
        "Leave-one-out residuals per family — re-fits the RF for every "
        "alloy removed, gives an honest per-prediction error estimate.\n",
    ]
    for fam in ("aluminum", "titanium", "nickel"):
        l = data.get(fam, {})
        if not l.get("residuals"):
            continue
        worst = l["residuals"][:5]
        out.append(f"**{fam.capitalize()} — top 5 worst LOO predictions:**\n")
        out.append("| Alloy | Truth | LOO pred | Abs. err |")
        out.append("|-------|------:|---------:|---------:|")
        for r in worst:
            out.append(f"| {r['name']} | {r['y_true']:.0f} | {r['y_pred']:.0f} | {r['abs_err']:.0f} |")
        out.append("")
    out.append(_meta_footer(meta))
    return "\n".join(out)


def _render_mp_formation_quaternary(data: dict, meta: dict) -> str:
    if data.get("skipped"):
        return (
            f"⚠ **Section skipped** — {data.get('reason', 'MP unavailable')}.\n\n"
            "Needs `MP_API_KEY` + network.  Run `--refresh mp_formation_quaternary`.\n\n"
            + _meta_footer(meta)
        )
    if "error" in data:
        return _render_error(data, meta, "Re-run with --refresh mp_formation_quaternary")
    srcs = ", ".join(f"{k} ×{v}" for k, v in (data.get("predictor_sources") or {}).items())
    beats = "✓ beats" if data.get("beats_baseline") else "✗ does NOT beat"
    out = [
        f"Quaternary-only stress test: **{data['n_evaluated']} compounds** from "
        f"{data.get('n_systems_queried', '—')} 4-element alloy systems "
        f"(Ni-Cr-Al-Ti, Al-Cu-Mg-Zn, Fe-Cr-Ni-Mo, …).  Predictor: **{srcs}**.\n",
        f"- **MAE {data['mae_meV_per_atom']:.0f} meV/atom** "
        f"(median {data['median_abs_err_meV']:.0f}, max {data['max_abs_err_meV']:.0f}).",
        f"- Naive predict-zero baseline: {data['baseline_zero_mae_meV']:.0f} meV/atom "
        f"→ model **{beats}** the baseline.",
        f"- Conformal-envelope coverage: {data['in_envelope_pct']:.0f}%.",
        "",
        "| n-elements | n | MAE (meV/at) | Median | Max |",
        "|-----------:|--:|-------------:|-------:|----:|",
    ]
    for nel, s in (data.get("by_nelements") or {}).items():
        out.append(f"| {nel} | {s['n']} | {s['mae_meV']:.0f} | {s['median_meV']:.0f} | {s['max_meV']:.0f} |")
    out.append("")
    out.append(_meta_footer(meta))
    return "\n".join(out)


def _render_calorimetry(data: dict, meta: dict) -> str:
    if data.get("skipped"):
        return (
            f"⚠ **Section skipped** — {data.get('reason', 'predictor unavailable')}.\n\n"
            + _meta_footer(meta)
        )
    if "error" in data:
        return _render_error(data, meta, "Re-run with --refresh calorimetry_m3gnet")
    srcs = ", ".join(f"{k} ×{v}" for k, v in (data.get("predictor_sources") or {}).items())
    beats = "✓ beats" if data.get("beats_baseline") else "✗ does NOT beat"
    out = [
        f"**{data['n_evaluated']} intermetallics** benchmarked against experimental "
        f"ΔHf from NIST WebBook / CALPHAD assessments (not MP-PBE).  "
        f"Predictor: **{srcs}**.\n",
        f"- **MAE {data['mae_meV_per_atom']:.0f} meV/atom** vs experiment "
        f"(median {data['median_abs_err_meV']:.0f}, max {data['max_abs_err_meV']:.0f}).",
        f"- Naive predict-zero baseline: {data['baseline_zero_mae_meV']:.0f} meV/atom "
        f"→ model **{beats}** the baseline.",
        f"- Conformal-envelope coverage: {data['in_envelope_pct']:.0f}%.",
        "",
        "_Higher MAE vs experiment than vs MP-PBE is expected: DFT errors "
        "compound with GNN errors.  This section quantifies the combined gap._\n",
    ]
    out.append(_meta_footer(meta))
    return "\n".join(out)


def _render_ys_ood_external(data: dict, meta: dict) -> str:
    if "error" in data:
        return _render_error(data, meta, "Re-run with --refresh ys_ood_external")
    out = [
        "Yield-strength prediction on alloys sourced exclusively from published "
        "commercial datasheets — **truly external OOD** (not in training set).\n",
    ]
    for fam in ("aluminum", "titanium", "nickel"):
        r = data.get(fam, {})
        if not r:
            continue
        out.append(f"**{fam.capitalize()}** — {r.get('n_total', 0)} alloys")
        mae = r.get("mae")
        env = r.get("in_envelope_pct")
        if mae is not None:
            out.append(
                f"  MAE {mae:.0f} MPa · envelope coverage {env:.0f}% · "
                f"{r.get('n_predictions', 0)} predicted / {r.get('n_refusals', 0)} refused"
            )
        out.append("")
    out.append(_meta_footer(meta))
    return "\n".join(out)


def _render_hea_and_consistency(data: dict, meta: dict) -> str:
    hea = data.get("hea", {})
    con = data.get("consistency", {})
    out = []
    # --- HEA sub-section ---
    if hea.get("skipped") or "error" in hea:
        out.append("**G1 — HEA formation energy**: skipped or errored.\n")
    else:
        srcs = ", ".join(f"{k} ×{v}" for k, v in (hea.get("predictor_sources") or {}).items())
        beats = "✓ beats" if hea.get("beats_baseline") else "✗ does NOT beat"
        out += [
            f"**G1 — HEA formation energy** — {hea['n_evaluated']} near-equimolar "
            f"multi-principal-element alloys.  Predictor: **{srcs}**.\n",
            f"- **MAE {hea['mae_meV_per_atom']:.0f} meV/atom** "
            f"(median {hea['median_abs_err_meV']:.0f}, max {hea['max_abs_err_meV']:.0f}).",
            f"- Naive predict-zero baseline: {hea['baseline_zero_mae_meV']:.0f} meV/atom "
            f"→ model **{beats}** the baseline.",
            f"- Conformal-envelope coverage: {hea['in_envelope_pct']:.0f}%.",
            "",
        ]
    # --- consistency sub-section ---
    if not con:
        out.append("**G2 — Cross-module consistency**: not computed.\n")
    else:
        pct = con.get("consistency_pct", 0)
        n = con.get("n_total", 0)
        n_ok = con.get("n_consistent", 0)
        out += [
            f"**G2 — CALPHAD / M3GNet sign agreement** — {n_ok}/{n} canonical phases "
            f"have consistent stability sign (**{pct:.0f}%**).\n",
        ]
        bad = con.get("inconsistent", [])
        if bad:
            out.append("| Phase | M3GNet ΔHf (eV/at) | Source |")
            out.append("|-------|-------------------:|--------|")
            for r in bad:
                out.append(
                    f"| {r['name']} | {r.get('m3gnet_dHf') or '—'} | {r.get('source', '—')} |"
                )
            out.append("")
        else:
            out.append("_All canonical phases consistent — no sign disagreements._\n")
    out.append(_meta_footer(meta))
    return "\n".join(out)


def _render_deferred_3_5(data: dict, meta: dict) -> str:
    return (
        "❌ **Deferred** — Sprint 3.5 (NIMS / MMPDS / ASM Alloy Digest ingest) "
        "is blocked on data access, not on engineering.  Closing the Ti CV-MAE "
        "gap (101 MPa actual vs ≤80 MPa target) needs ~50-100 NIMS or "
        "MMPDS-08 entries.  See `SCIENTIFIC_ROADMAP.md` for the re-entry checklist.\n"
    )


def _render_deferred_9(data: dict, meta: dict) -> str:
    return (
        "❌ **Deferred** — Sprint 9 (Literature RAG + citation enforcement) "
        "is blocked on a redistributable authoritative corpus (ASM Handbook, "
        "Donachie, Boyer, Reed, Polmear are all paywalled).  Auto-fetched "
        "arXiv + NIST + OSTI alternative was judged insufficient.  See the "
        "re-entry checklist in `SCIENTIFIC_ROADMAP.md` and the auto-fetch "
        "implementation sketch preserved in this plan file's git history.\n"
    )


# ─────────────────────────────────────────────────────────────────────
# Section registry — order is the order they appear in the scorecard
# ─────────────────────────────────────────────────────────────────────

SECTIONS: list[SectionSpec] = [
    SectionSpec(
        sprint="1",
        title="CALPHAD equilibrium phase fractions",
        cache_key="sprint1_calphad",
        runner=_run_calphad_equilibrium,
        renderer=_render_calphad_equilibrium,
        description="pycalphad equilibrium against 15 canonical reference points "
                    "across Al / Fe / Ni / Ti / Cu (Massalski + ternary).",
    ),
    SectionSpec(
        sprint="2 (Scheil)",
        title="Scheil-Gulliver solidification",
        cache_key="sprint2_scheil",
        runner=_run_scheil,
        renderer=_render_scheil,
        is_slow=True,
        description="Non-equilibrium freezing curves on canonical castings — "
                    "mushy zone, hot-tearing tendency.",
    ),
    SectionSpec(
        sprint="2 (TTT)",
        title="Fe-C TTT diagrams (Kirkaldy-Venugopalan)",
        cache_key="sprint2_ttt",
        runner=_run_ttt,
        renderer=_render_ttt,
        description="Pearlite / bainite nose temperatures + Andrews Ms / Bs "
                    "on AISI 1045 / 4140 / 4340 / IN 718 austenitisation.",
    ),
    SectionSpec(
        sprint="2.5 + 2.6",
        title="Microstructure rendering (FiPy + Taichi KWC)",
        cache_key="sprint2_5_2_6_microstructure",
        runner=None,
        renderer=_render_microstructure_static,
        description="Per-test invariants; no aggregate runner.",
    ),
    SectionSpec(
        sprint="3 + 4 + 6 (YS)",
        title="Yield-strength holdout on canonical alloys",
        cache_key="sprint346_ys_holdout",
        runner=_run_holdout,
        renderer=_render_ys_holdout,
        description="Per-family RF + temper + physics features on alloys "
                    "guaranteed not to leak into training (defence-in-depth filter).",
    ),
    SectionSpec(
        sprint="3.5",
        title="NIMS / MMPDS / ASM Alloy Digest ingest",
        cache_key="sprint3_5_deferred",
        runner=None,
        renderer=_render_deferred_3_5,
        description="Deferred — blocked on data access.",
    ),
    SectionSpec(
        sprint="5",
        title="KWN precipitation kinetics",
        cache_key="sprint5_precipitation",
        runner=_run_precipitation,
        renderer=_render_precipitation,
        description="Kampmann-Wagner numerical: CNT nucleation + Zener growth "
                    "+ LSW coarsening across 6 canonical TEM/SAXS reference points.",
    ),
    SectionSpec(
        sprint="6",
        title="Strengthening feature ablation",
        cache_key="sprint6_ablation",
        runner=_run_strengthening_ablation,
        renderer=_render_strengthening_ablation,
        is_slow=True,
        description="5-fold CV MAE at L1/L2/L3/L4 feature levels — shows where "
                    "temper one-hot and engineered physics features pay rent.",
    ),
    SectionSpec(
        sprint="7",
        title="Inverse-design canonical briefs",
        cache_key="sprint7_briefs",
        runner=_run_briefs,
        renderer=_render_briefs,
        description="5 engineering briefs (Al wing skin, Ti implant, Ni turbine, "
                    "steel, Marine Al) through the qEHVI + feasibility-filter stack.",
    ),
    SectionSpec(
        sprint="8",
        title="Hierarchical cost model",
        cache_key="sprint8_cost",
        runner=_run_cost,
        renderer=_render_cost,
        description="17 canonical supplier quotes — spot price × form × cert × "
                    "heat-treatment × supplier-minimum overhead.",
    ),
    SectionSpec(
        sprint="9",
        title="Literature RAG with citation enforcement",
        cache_key="sprint9_deferred",
        runner=None,
        renderer=_render_deferred_9,
        description="Deferred — blocked on redistributable corpus.",
    ),
    SectionSpec(
        sprint="Appendix A",
        title="M3GNet formation energy (optional)",
        cache_key="m3gnet",
        runner=_run_formation_energy,
        renderer=_render_formation_energy,
        description="Random-substitution supercell vs MP-PBE reference values.  "
                    "Skipped automatically if `matgl` is not installed.",
    ),
    SectionSpec(
        sprint="Appendix B",
        title="Leave-one-out YS residuals",
        cache_key="ys_loo",
        runner=_run_loo,
        renderer=_render_loo,
        is_slow=True,
        description="Worst-case LOO residuals per family — re-fits the RF per "
                    "held-out alloy.",
    ),
    SectionSpec(
        sprint="Appendix C",
        title="MP formation-energy stress test (hundreds-scale)",
        cache_key="mp_formation_stress",
        runner=_run_mp_formation_stress,
        renderer=_render_mp_formation,
        is_slow=True,
        description="Production formation-energy predictor vs PBE-DFT over "
                    "hundreds of stable MP compounds across alloy systems — "
                    "with a predict-zero baseline.  Records which predictor "
                    "(M3GNet vs Miedema fallback) ran.  Needs MP_API_KEY.",
    ),
    SectionSpec(
        sprint="Appendix D",
        title="MP formation-energy stress test — quaternary systems",
        cache_key="mp_formation_quaternary",
        runner=_run_mp_formation_quaternary,
        renderer=_render_mp_formation_quaternary,
        is_slow=True,
        description="Same MP stress-test harness restricted to 4-element alloy "
                    "chemical systems (Ni-Cr-Al-Ti, Al-Cu-Mg-Zn, Fe-Cr-Ni-Mo, …).  "
                    "First quantitative quaternary data point for M3GNet.  Needs MP_API_KEY.",
    ),
    SectionSpec(
        sprint="Appendix E",
        title="M3GNet vs experimental ΔHf (calorimetry)",
        cache_key="calorimetry_m3gnet",
        runner=_run_calorimetry,
        renderer=_render_calorimetry,
        is_slow=False,
        description="M3GNet formation energy benchmarked against experimental "
                    "calorimetry values (NIST WebBook, CALPHAD tables) — not MP-PBE.  "
                    "Closes the DFT-error gap; no network needed.",
    ),
    SectionSpec(
        sprint="Appendix F",
        title="Yield strength — external OOD validation",
        cache_key="ys_ood_external",
        runner=_run_ys_ood_external,
        renderer=_render_ys_ood_external,
        is_slow=False,
        description="Yield-strength predictions on alloys from published commercial "
                    "datasheets (MatWeb, ASM Alloy Digest) — truly OOD, not in training. "
                    "Tests conformal interval coverage on unseen alloy families.",
    ),
    SectionSpec(
        sprint="Appendix G",
        title="HEA formation energy + cross-module consistency",
        cache_key="hea_consistency",
        runner=_run_hea_and_consistency,
        renderer=_render_hea_and_consistency,
        is_slow=False,
        description="Two sub-tests: (G1) M3GNet on near-equimolar HEA compositions "
                    "(Cantor, AlCoCrFeNi, …); (G2) sign-agreement between CALPHAD "
                    "stable-phase predictions and M3GNet ΔHf for 18 canonical phases.",
    ),
]


# ─────────────────────────────────────────────────────────────────────
# Top-level orchestration
# ─────────────────────────────────────────────────────────────────────

def render_scorecard(refresh: set[str], include_slow: bool) -> str:
    """Render the full scorecard as a single Markdown string."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "# LeilMat — Unified Validation Scorecard",
        "",
        f"_Generated {now}_  ·  source-of-truth for SCIENTIFIC_ROADMAP.md "
        "and README.md sprint headlines.  Regenerate with "
        "`python -m apps.api.ml.eval.unified_scorecard --refresh all`.",
        "",
        "Each section reads from a JSON cache at "
        "`apps/api/ml/eval/_cache/<key>.json`.  Slow sections (Scheil, "
        "Taichi KWC, LOO) are not refreshed unless `--include-slow` or an "
        "explicit `--refresh <key>` is passed; nightly CI runs the slow set.",
        "",
        "---",
        "",
    ]

    for spec in SECTIONS:
        anchor = f"sprint-{spec.cache_key}"
        lines.append(f"## Sprint {spec.sprint} — {spec.title}")
        lines.append("")
        if spec.description:
            lines.append(f"_{spec.description}_")
            lines.append("")

        # Determine whether to skip the runner this round
        forced = ("all" in refresh) or (spec.cache_key in refresh)
        if spec.is_slow and not include_slow and not forced:
            cached = _load_cache(spec.cache_key)
            if cached is None:
                lines.append(
                    f"_Section is slow ({spec.cache_key}); skipped on the "
                    f"fast path.  Run `--refresh {spec.cache_key}` or "
                    "`--include-slow` to populate._\n"
                )
                lines.append("---\n")
                continue
            envelope = cached
        else:
            envelope = _ensure_cache(spec, refresh)

        meta = envelope.get("_meta", {})
        data = envelope.get("data", {})
        try:
            body = spec.renderer(data, meta)
        except Exception as exc:
            body = (
                f"⚠ Renderer raised `{type(exc).__name__}: {exc}` — the cache "
                "is probably stale.  Re-run with `--refresh "
                f"{spec.cache_key}`.\n"
            )
        lines.append(body)
        lines.append("---\n")

    lines.extend([
        "",
        "## How to regenerate",
        "",
        "```bash",
        "# fast refresh (CALPHAD, TTT, precipitation, briefs, cost, holdout)",
        "python -m apps.api.ml.eval.unified_scorecard --refresh all",
        "",
        "# include the slow runners too (Scheil, LOO, ablation — multi-minute)",
        "python -m apps.api.ml.eval.unified_scorecard --refresh all --include-slow",
        "",
        "# selective — only one or two sections",
        "python -m apps.api.ml.eval.unified_scorecard --refresh sprint5_precipitation",
        "",
        "# emit to stdout instead of docs/SCORECARD.md",
        "python -m apps.api.ml.eval.unified_scorecard --out -",
        "```",
        "",
    ])

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────

def _parse_refresh(value: str | None) -> set[str]:
    if not value:
        return set()
    return {x.strip() for x in value.split(",") if x.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LeilMat unified validation scorecard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--refresh", default="",
        help="comma-separated cache keys to re-run, or 'all'.  "
             "Default: read existing caches, fill missing ones on demand.",
    )
    parser.add_argument(
        "--include-slow", action="store_true",
        help="also auto-fill slow sections (Scheil, LOO, ablation).  "
             "Off by default to keep the CLI under ~30 s.",
    )
    parser.add_argument(
        "--out", default=str(DEFAULT_OUTPUT),
        help=f"Output path, or '-' for stdout.  Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="list section cache keys + their slow/fast status and exit.",
    )
    args = parser.parse_args()

    if args.list:
        print(f"{'cache key':<32} {'slow':<5} title")
        print(f"{'-'*32} {'-'*5} {'-'*40}")
        for s in SECTIONS:
            print(f"{s.cache_key:<32} {'yes' if s.is_slow else 'no':<5} {s.title}")
        return

    refresh = _parse_refresh(args.refresh)
    text = render_scorecard(refresh=refresh, include_slow=args.include_slow)

    if args.out == "-":
        print(text)
        return

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    print(f"Wrote {out_path}  ({len(text):,} bytes, {len(SECTIONS)} sections)")


if __name__ == "__main__":
    main()
