"""
apps.api.ml.calphad.eval.scorecard
====================================

Scorecard section for CALPHAD equilibrium validation.

Called automatically by ``python -m apps.api.ml.eval.scorecard`` when it
discovers this module.  Can also be run standalone:

    python -m apps.api.ml.calphad.eval.scorecard
"""
from __future__ import annotations

import textwrap
from typing import Any


def build_section() -> str:
    """Return a Markdown string to append to the main scorecard report."""
    try:
        from apps.api.ml.calphad.eval.equilibrium_runner import run_all
        from apps.api.ml.calphad.databases import list_coverage
    except ImportError as exc:
        return f"## CALPHAD verification\n\n> ⚠️  Could not import runner: {exc}\n\n"

    summary = run_all()
    coverage = list_coverage()

    lines: list[str] = []
    lines.append("## CALPHAD verification  (Sprint 1)")
    lines.append("")
    lines.append(
        f"**Pass rate:** {summary['n_pass']}/{summary['n_total']} "
        f"({summary['pass_rate']:.0%})  |  "
        f"**Total evaluation time:** {summary['total_elapsed_s']:.1f} s"
    )
    lines.append("")

    # ── Per-family sub-tables ────────────────────────────────────────────────
    families = {"binary": [], "al_alloy": [], "steel": [], "ni_base": []}
    for r in summary["results"]:
        fam = r.get("chemsys_family", "binary")
        families.setdefault(fam, []).append(r)

    family_titles = {
        "binary":   "### Binary reference points",
        "al_alloy": "### Al-alloy reference points",
        "steel":    "### Steel / Fe-alloy reference points",
        "ni_base":  "### Ni-base superalloy reference points",
    }

    for fam, title in family_titles.items():
        rows = families.get(fam, [])
        if not rows:
            continue
        lines.append(title)
        lines.append("")
        lines.append("| Reference | T (K) | Dominant phase (pred) | Outcome | Elapsed (s) |")
        lines.append("|---|---|---|---|---|")
        for r in rows:
            dom = max(r["phases_predicted"], key=r["phases_predicted"].get) if r["phases_predicted"] else "—"
            icon = "✓" if r["outcome"] == "pass" else ("✗" if r["outcome"] == "fail" else "E")
            lines.append(
                f"| {r['name']} | {r['T_K']:.0f} | {dom} | {icon} | {r['elapsed_s']:.2f} |"
            )
        lines.append("")

    # ── TDB coverage matrix ─────────────────────────────────────────────────
    lines.append("### TDB coverage matrix")
    lines.append("")
    lines.append("| TDB file | Elements | n_elements | Available | Source |")
    lines.append("|---|---|---|---|---|")
    for row in coverage:
        els = ", ".join(row["elements"][:12])
        if len(row["elements"]) > 12:
            els += ", …"
        avail = "✓" if row["available"] else "✗ missing"
        lines.append(
            f"| `{row['file']}` | {els} | {row['n_elements']} | {avail} | {row['source']} |"
        )
    lines.append("")

    # ── Failure details ──────────────────────────────────────────────────────
    failures = [r for r in summary["results"] if r["outcome"] != "pass"]
    if failures:
        lines.append("### Failures / errors")
        lines.append("")
        for r in failures:
            lines.append(f"**{r['name']}** ({r['outcome']})")
            for c in r.get("checks", []):
                if not c.get("passed"):
                    lines.append(f"- {c['check']}: {c.get('detail', '')}")
            if r.get("error"):
                lines.append(f"- error: {r['error']}")
            lines.append("")

    return "\n".join(lines) + "\n"


def build_scheil_section() -> str:
    """Sprint 2 — Scheil-Gulliver solidification scorecard section."""
    try:
        from apps.api.ml.calphad.eval.solidification_runner import run_all as scheil_run
    except ImportError as exc:
        return f"## Scheil-Gulliver solidification\n\n> ⚠️  Import failed: {exc}\n\n"

    s = scheil_run()
    lines = [
        "## Scheil-Gulliver solidification  (Sprint 2)",
        "",
        f"**Pass rate:** {s['n_pass']}/{s['n_total']} ({s['pass_rate']:.0%})  |  "
        f"**Total time:** {s['total_elapsed_s']} s",
        "",
        "### Canonical castings",
        "",
        "| Alloy | Liquidus (K) | Solidus (K) | Mushy (K) | Outcome | Elapsed (s) |",
        "|---|---|---|---|---|---|",
    ]
    for r in s["results"]:
        p = r["predicted"]
        icon = "✓" if r["outcome"] == "pass" else "✗"
        lines.append(
            f"| {r['name']} | {p.get('liquidus_K', '—')} | "
            f"{p.get('solidus_K', '—')} | {p.get('mushy_K', '—')} | "
            f"{icon} | {r['elapsed_s']} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def build_ttt_section() -> str:
    """Sprint 2 — Fe-C TTT scorecard section (Kirkaldy-Venugopalan + Andrews Ms)."""
    try:
        from apps.api.ml.calphad.eval.ttt_runner import run_all as ttt_run
    except ImportError as exc:
        return f"## Fe-C TTT diagrams\n\n> ⚠️  Import failed: {exc}\n\n"

    t = ttt_run()
    lines = [
        "## Fe-C TTT diagrams  (Sprint 2)",
        "",
        f"**Pass rate:** {t['n_pass']}/{t['n_total']} ({t['pass_rate']:.0%})  |  "
        "**Model:** Kirkaldy-Venugopalan + Andrews Ms",
        "",
        "### TTT nose temperatures and times",
        "",
        "| Steel | Pearlite nose | Bainite nose | Ms (°C) | Outcome |",
        "|---|---|---|---|---|",
    ]
    for r in t["results"]:
        if r["outcome"] == "error":
            lines.append(f"| {r['name']} | — | — | — | E |")
            continue
        p = r["predicted"]["pearlite"]
        b = r["predicted"]["bainite"]
        Ms = r["critical_T_C"]["Ms"]
        icon = "✓" if r["outcome"] == "pass" else "✗"
        lines.append(
            f"| {r['name']} | {p['T_nose_C']}°C / {p['t_nose_s']}s | "
            f"{b['T_nose_C']}°C / {b['t_nose_s']}s | {Ms} | {icon} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(build_section())
    print(build_ttt_section())
    print(build_scheil_section())
