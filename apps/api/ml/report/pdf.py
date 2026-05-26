"""
PDF report builder for LeilMat design sessions.

Top-level entry: ``build_pdf(req)`` returns the rendered bytes.

The builder is split into per-section helpers (``_build_cover``,
``_build_composition_section``, …) that each return a list of
ReportLab flowables.  The top-level routine concatenates them with
``PageBreak()`` markers and runs ``doc.build()``.

Design choices
──────────────
  * Pure ReportLab — no HTML/CSS, no headless-Chromium.  Every layout
    decision is explicit, fully Pythonic, and survives Docker rebuilds
    without system deps.
  * Charts rendered by ``ml/report/charts.py`` (matplotlib Agg backend)
    are embedded as PNG flowables.
  * Brand-gold accent (#f7af41) mirrors the LeilMat header / favicon /
    landing page, so the PDF reads as a member of the same product
    family.
  * Provenance: every numerical value in the Properties table carries
    a ``method`` annotation (RF / VRH / ROM / Magpie / CALPHAD / KWN /
    BoTorch) so the report is audit-grade out of the box.
"""
from __future__ import annotations

import io
import datetime as dt
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles    import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units     import mm
from reportlab.lib           import colors
from reportlab.platypus      import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
    KeepTogether,
)
from reportlab.pdfgen        import canvas as rl_canvas

from apps.api.ml.report.charts import (
    render_property_radar, render_phase_bar, render_pareto, render_kwn_kinetics,
    ACCENT_GOLD,
)


# ─── Pydantic-friendly request shape ──────────────────────────────────
# Caller passes a flat dict; we extract with .get() so missing fields
# degrade gracefully (a section is just omitted).

ReportPayload = dict[str, Any]


# ─── Atomic masses (g/mol) — used for wt% → at% conversion ────────────
ATOMIC_MASS: dict[str, float] = {
    "H":  1.008,  "He": 4.003,  "Li": 6.94,   "Be": 9.012, "B":  10.81,
    "C":  12.011, "N":  14.007, "O":  15.999, "F":  18.998, "Ne": 20.180,
    "Na": 22.990, "Mg": 24.305, "Al": 26.982, "Si": 28.085, "P":  30.974,
    "S":  32.06,  "Cl": 35.45,  "K":  39.098, "Ca": 40.078, "Sc": 44.956,
    "Ti": 47.867, "V":  50.942, "Cr": 51.996, "Mn": 54.938, "Fe": 55.845,
    "Co": 58.933, "Ni": 58.693, "Cu": 63.546, "Zn": 65.38,  "Ga": 69.723,
    "Ge": 72.630, "As": 74.922, "Se": 78.971, "Br": 79.904, "Y":  88.906,
    "Zr": 91.224, "Nb": 92.906, "Mo": 95.95,  "Ru": 101.07, "Rh": 102.906,
    "Pd": 106.42, "Ag": 107.868, "Cd": 112.414, "In": 114.818, "Sn": 118.710,
    "Sb": 121.760, "Te": 127.60, "I":  126.904, "Cs": 132.905, "Ba": 137.327,
    "Hf": 178.49, "Ta": 180.948, "W":  183.84, "Re": 186.207, "Os": 190.23,
    "Ir": 192.217, "Pt": 195.084, "Au": 196.967, "Hg": 200.592, "Tl": 204.38,
    "Pb": 207.2,   "Bi": 208.980, "U":  238.029,
}


def _wt_to_atomic(composition_wt: dict[str, float]) -> dict[str, float]:
    """Convert weight-% to atomic-% — only for elements in ATOMIC_MASS."""
    moles = {}
    for el, pct in composition_wt.items():
        m = ATOMIC_MASS.get(el)
        if m is None or pct is None:
            continue
        moles[el] = float(pct) / m
    total = sum(moles.values())
    if total <= 0:
        return {el: 0.0 for el in composition_wt}
    return {el: round(100.0 * v / total, 2) for el, v in moles.items()}


# ─── Styles ───────────────────────────────────────────────────────────

INK         = colors.HexColor("#15171d")
INK_SOFT    = colors.HexColor("#5b6473")
INK_FAINT   = colors.HexColor("#9098a8")
GOLD        = colors.HexColor(ACCENT_GOLD)
GOLD_FAINT  = colors.HexColor("#fff5e3")
SURFACE     = colors.HexColor("#f6f7fb")
LINE        = colors.HexColor("#dde0e8")


def _styles():
    """Build LeilMat's shared paragraph style sheet (cached per call)."""
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(
        name="LeilTitle", parent=base["Title"],
        fontName="Helvetica-Bold", fontSize=28, leading=32,
        textColor=INK, alignment=0, spaceAfter=4,
    ))
    base.add(ParagraphStyle(
        name="LeilSubtitle", parent=base["Normal"],
        fontName="Helvetica", fontSize=11, leading=15,
        textColor=INK_SOFT, alignment=0, spaceAfter=10,
    ))
    base.add(ParagraphStyle(
        name="LeilSection", parent=base["Heading1"],
        fontName="Helvetica-Bold", fontSize=14, leading=18,
        textColor=INK, alignment=0, spaceBefore=18, spaceAfter=8,
    ))
    base.add(ParagraphStyle(
        name="LeilEyebrow", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=8, leading=10,
        textColor=GOLD, alignment=0,
        spaceAfter=4,
    ))
    base.add(ParagraphStyle(
        name="LeilBody", parent=base["Normal"],
        fontName="Helvetica", fontSize=9.5, leading=14,
        textColor=INK, alignment=0, spaceAfter=6,
    ))
    base.add(ParagraphStyle(
        name="LeilCaption", parent=base["Normal"],
        fontName="Helvetica-Oblique", fontSize=8, leading=11,
        textColor=INK_FAINT, alignment=0, spaceAfter=2,
    ))
    base.add(ParagraphStyle(
        name="LeilQuote", parent=base["Normal"],
        fontName="Helvetica", fontSize=9, leading=13,
        textColor=INK_SOFT, alignment=0,
        leftIndent=10, spaceBefore=2, spaceAfter=4,
        borderColor=GOLD, borderPadding=4,
    ))
    return base


# Common table style for the property + composition tables.
def _data_table_style(header_rows: int = 1) -> TableStyle:
    # NB: ReportLab's LINE-family commands take ``(thickness, color)`` in
    # that order — passing them as (color, thickness) raises
    # ``ValueError: Unknown color 0.4`` because ReportLab tries to coerce
    # the float thickness into a colour object.  Always thickness first.
    return TableStyle([
        ("FONT",        (0, 0), (-1, -1), "Helvetica", 9),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
        ("BACKGROUND",  (0, 0), (-1, header_rows - 1), INK),
        ("FONT",        (0, 0), (-1, header_rows - 1), "Helvetica-Bold", 9),
        ("ROWBACKGROUNDS", (0, header_rows), (-1, -1), [colors.white, SURFACE]),
        ("LINEBELOW",   (0, 0), (-1, 0),               1.0, GOLD),
        ("LINEABOVE",   (0, header_rows), (-1, header_rows), 0.5, LINE),
        ("BOX",         (0, 0), (-1, -1),              0.5, LINE),
        ("ALIGN",       (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ])


# ─── Page decorators (header + footer on every page) ──────────────────

def _header_footer(canvas: rl_canvas.Canvas, doc: SimpleDocTemplate) -> None:
    canvas.saveState()
    # Top thin gold rule.
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.8)
    canvas.line(25 * mm, A4[1] - 12 * mm, A4[0] - 25 * mm, A4[1] - 12 * mm)

    # Top-left wordmark.
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(INK)
    canvas.drawString(25 * mm, A4[1] - 18 * mm, "LeilMat")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(INK_SOFT)
    canvas.drawString(25 * mm + 18 * mm, A4[1] - 18 * mm,
                      "alloy design report")

    # Top-right page-marker.
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(INK_SOFT)
    canvas.drawRightString(A4[0] - 25 * mm, A4[1] - 18 * mm,
                           f"Page {doc.page}")

    # Bottom footer.
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(INK_FAINT)
    canvas.drawString(25 * mm, 12 * mm,
                      "Predictions carry source + uncertainty. "
                      "Validate against experiment before production.")
    canvas.drawRightString(A4[0] - 25 * mm, 12 * mm, "app.example.org")
    canvas.restoreState()


# ─── Section builders ─────────────────────────────────────────────────

def _build_cover(req: ReportPayload, S) -> list:
    """Cover page — alloy name, designer, date, top-line composition."""
    alloy_name = req.get("alloy_name") or "Designed Alloy"
    designer   = req.get("designer")   or "LeilMat session"
    session_id = req.get("session_id") or "—"
    today      = dt.date.today().isoformat()

    # Headline composition (one-line, sorted by descending wt %).
    comp = req.get("composition") or {}
    if comp:
        comp_pairs = sorted(comp.items(), key=lambda kv: -float(kv[1] or 0))
        comp_str   = "-".join(f"{el}{round(float(v), 1)}" for el, v in comp_pairs)
    else:
        comp_str = "no composition"

    out = []
    out.append(Spacer(1, 60))
    out.append(Paragraph("ALLOY DESIGN REPORT", S["LeilEyebrow"]))
    out.append(Paragraph(alloy_name, S["LeilTitle"]))
    out.append(Paragraph(comp_str, S["LeilSubtitle"]))
    out.append(Spacer(1, 24))

    out.append(Table([
        ["Designer",   designer],
        ["Generated",  today],
        ["Session ID", session_id],
        ["Tool",       "LeilMat 0.1 — app.example.org"],
    ],
        colWidths=[35 * mm, 110 * mm],
        style=TableStyle([
            ("FONT",       (0, 0), (-1, -1), "Helvetica", 9),
            ("TEXTCOLOR",  (0, 0), (0, -1),  INK_SOFT),
            ("TEXTCOLOR",  (1, 0), (1, -1),  INK),
            ("LINEBELOW",  (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",(0, 0), (-1, -1), 0),
            ("RIGHTPADDING",(0,0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ]),
    ))
    out.append(Spacer(1, 60))
    out.append(Paragraph(
        "This report is generated from a LeilMat design session.  Every "
        "numerical claim carries its computational method and uncertainty.  "
        "Sections are omitted when the underlying simulation has not been run.",
        S["LeilCaption"],
    ))
    return out


def _build_composition_section(req: ReportPayload, S) -> list:
    """Composition table: wt% + at%."""
    comp = req.get("composition") or {}
    if not comp:
        return []
    out = []
    out.append(Paragraph("Composition", S["LeilSection"]))
    at = _wt_to_atomic(comp)
    rows = [["Element", "wt %", "at %"]]
    for el in sorted(comp, key=lambda k: -float(comp[k] or 0)):
        rows.append([
            f"<b>{el}</b>",
            f"{float(comp[el]):.2f}",
            f"{at.get(el, 0):.2f}" if at.get(el) is not None else "—",
        ])
    # Wrap element symbols in Paragraphs so the <b> markup renders.
    body = [
        [Paragraph(c, S["LeilBody"]) if isinstance(c, str) and "<b>" in c else c
         for c in r]
        for r in rows
    ]
    out.append(Table(body, colWidths=[40 * mm, 50 * mm, 50 * mm],
                     style=_data_table_style()))
    temper = req.get("temper")
    if temper:
        out.append(Spacer(1, 4))
        out.append(Paragraph(f"<b>Temper / heat treatment:</b> {temper}",
                             S["LeilBody"]))
    return out


# Per-property display config.  Anything not listed is shown with no unit
# and method "—" so the table still degrades gracefully.
_PROP_LABELS = {
    "yield_strength_MPa":        ("Yield strength",     "MPa", "RF + conformal"),
    "ultimate_strength_MPa":     ("Ultimate strength",  "MPa", "RF + conformal"),
    "elongation_pct":            ("Elongation",         "%",   "RF"),
    "density_g_cm3":             ("Density",            "g/cm³", "ROM"),
    "thermal_conductivity_W_mK": ("Thermal conductivity", "W/m·K", "Magpie"),
    "electrical_resistivity":    ("Electrical resistivity", "nΩ·m", "Magpie"),
    "hardness_HV":               ("Hardness",           "HV", "RF"),
    "youngs_modulus_GPa":        ("Young's modulus",    "GPa", "VRH"),
    "melting_point_K":           ("Melting point",      "K", "Magpie"),
    "cost_per_kg_usd":           ("Cost",               "USD/kg", "Hierarchical"),
}


def _build_properties_section(req: ReportPayload, S) -> list:
    """Property table with values + CI + method, plus a radar chart."""
    props = req.get("properties") or {}
    if not props:
        return []

    intervals = req.get("property_intervals") or {}
    out = []
    out.append(Paragraph("Predicted properties", S["LeilSection"]))

    rows = [["Property", "Value", "± 95 % CI", "Method"]]
    for key, val in props.items():
        if val is None:
            continue
        label, unit, method = _PROP_LABELS.get(key, (key, "", "—"))
        ci = intervals.get(key)
        ci_str = f"± {abs(float(ci[1]) - float(ci[0])) / 2:.2g}" if (ci and len(ci) == 2) else "—"
        rows.append([
            Paragraph(f"<b>{label}</b>", S["LeilBody"]),
            f"{float(val):.3g} {unit}".strip(),
            ci_str,
            method,
        ])
    out.append(Table(
        rows,
        colWidths=[55 * mm, 35 * mm, 28 * mm, 35 * mm],
        style=_data_table_style(),
    ))

    # Radar chart — only if ≥ 3 numeric properties to plot.
    radar = render_property_radar(props)
    if radar is not None:
        out.append(Spacer(1, 8))
        out.append(Image(radar, width=110 * mm, height=110 * mm))
        out.append(Paragraph(
            "Radar axes are normalised so further from centre = better.  "
            "Density and cost are inverted (lower = better).",
            S["LeilCaption"],
        ))
    return out


def _build_phase_section(req: ReportPayload, S) -> list:
    """Stable phases (CALPHAD or MP-hull) + bar chart."""
    sim = req.get("simulation_results") or {}
    phases = sim.get("phase", {}).get("result", {}).get("phases") \
        or req.get("stable_phases") \
        or []
    if not phases:
        return []
    out = []
    out.append(Paragraph("Phase assemblage", S["LeilSection"]))
    rows = [["Formula", "Formation energy (eV/atom)"]]
    for p in sorted(phases, key=lambda r: float(r.get("formation_energy", 0)))[:12]:
        rows.append([
            Paragraph(f"<b>{p.get('formula', '?')}</b>", S["LeilBody"]),
            f"{float(p.get('formation_energy', 0)):+.4f}",
        ])
    out.append(Table(rows, colWidths=[80 * mm, 70 * mm],
                     style=_data_table_style()))
    bar = render_phase_bar(phases)
    if bar is not None:
        out.append(Spacer(1, 6))
        out.append(Image(bar, width=160 * mm,
                         height=min(110 * mm, 12 * mm * len(phases) + 12 * mm)))
    return out


def _build_kwn_section(req: ReportPayload, S) -> list:
    """KWN precipitation kinetics — three stacked curves."""
    sim = req.get("simulation_results") or {}
    series = (sim.get("precipitation", {}).get("result", {}) or {}).get("time_series")
    if not series:
        return []
    out = []
    out.append(Paragraph("Precipitation kinetics (KWN)", S["LeilSection"]))
    chart = render_kwn_kinetics(series)
    if chart is not None:
        out.append(Image(chart, width=160 * mm, height=130 * mm))
    out.append(Paragraph(
        "Mean radius, number density, and volume fraction evolve through "
        "nucleation → growth → Ostwald-ripening regimes.  Hardening correlates "
        "with √(volume fraction) × √(radius) at the dispersed-precipitate stage.",
        S["LeilCaption"],
    ))
    return out


def _build_inverse_section(req: ReportPayload, S) -> list:
    """Inverse-design candidates — Pareto front + top-N table."""
    sim = req.get("simulation_results") or {}
    candidates = (sim.get("inverse", {}).get("result", {}) or {}).get("candidates")
    if not candidates:
        return []
    out = []
    out.append(Paragraph("Inverse-design candidates", S["LeilSection"]))
    pareto = render_pareto(
        candidates,
        x_field="density_g_cm3", y_field="yield_strength_MPa",
        x_label="Density (g/cm³)", y_label="Yield strength (MPa)",
    )
    if pareto is not None:
        out.append(Image(pareto, width=160 * mm, height=110 * mm))

    # Top-5 by composite score (if scored) or by yield strength.
    top = sorted(
        candidates,
        key=lambda c: -(c.get("score") or c.get("yield_strength_MPa") or 0),
    )[:5]
    rows = [["Composition", "Density", "YS (MPa)", "Score"]]
    for c in top:
        comp = c.get("composition", {})
        comp_str = "-".join(f"{el}{round(v, 1)}"
                            for el, v in sorted(comp.items(),
                                                key=lambda kv: -kv[1]))
        rows.append([
            comp_str or "—",
            f"{c.get('density_g_cm3', 0):.3f}",
            f"{c.get('yield_strength_MPa', 0):.0f}",
            f"{c.get('score', 0):.2f}" if c.get("score") is not None else "—",
        ])
    out.append(Spacer(1, 6))
    out.append(Table(rows, colWidths=[60 * mm, 30 * mm, 30 * mm, 30 * mm],
                     style=_data_table_style()))
    return out


def _build_ai_section(req: ReportPayload, S) -> list:
    """Global AI design rationale — compact transcript of the session
    messages with applied action pills surfaced inline.
    """
    messages = req.get("messages") or []
    # Only Global AI messages, in chronological order.
    msgs = [m for m in messages if m.get("contextType") == "global"]
    if not msgs:
        return []
    out = []
    out.append(Paragraph("AI design rationale", S["LeilSection"]))
    out.append(Paragraph(
        "Transcript of the Global AI conversation that shaped this design.  "
        "Applied actions are flagged inline.",
        S["LeilCaption"],
    ))
    out.append(Spacer(1, 4))
    for m in msgs:
        role = m.get("role", "?")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        # Soft truncate to keep the PDF reasonable.
        if len(content) > 1200:
            content = content[:1180].rsplit(" ", 1)[0] + "…"
        if role == "user":
            out.append(Paragraph(f"<b>You</b>", S["LeilEyebrow"]))
        else:
            out.append(Paragraph(f"<b>LeilMat AI</b>", S["LeilEyebrow"]))
        out.append(Paragraph(_escape(content), S["LeilBody"]))

        # Applied actions, if any.
        applied = m.get("appliedActionIdx") or []
        actions = m.get("actions") or []
        if applied and actions:
            applied_labels = [
                actions[i].get("label", actions[i].get("action", {}).get("op", "?"))
                for i in applied if i < len(actions)
            ]
            if applied_labels:
                out.append(Paragraph(
                    "<i>Applied:</i> " + " · ".join(applied_labels),
                    S["LeilCaption"],
                ))
        out.append(Spacer(1, 4))
    return out


def _build_bibliography_section(req: ReportPayload, S) -> list:
    """Provenance — list of sources cited or relied upon by the report."""
    out = []
    out.append(Paragraph("Provenance &amp; bibliography", S["LeilSection"]))

    items: list[str] = []
    props = req.get("properties") or {}
    intervals = req.get("property_intervals") or {}
    has_ml = any(_PROP_LABELS.get(k, ("", "", ""))[2] == "RF + conformal"
                 for k in props if props[k] is not None)
    if has_ml:
        items.append(
            "<b>ML property predictions</b> — Random-Forest models trained on the "
            "LeilMat Al/Ti/Ni/Steel handbook-grade dataset (Sprint 3).  Mean "
            "absolute error and 95 % confidence intervals via conformal "
            "calibration on held-out folds (Sprint 4)."
        )
    sim = req.get("simulation_results") or {}
    if sim.get("phase"):
        items.append(
            "<b>Phase assemblage</b> — pycalphad equilibrium solver on bundled "
            "BSD-licensed TDB files (COST507, mc_fecocrnbti, alcrni, alni, "
            "alzn, alcocrni; Sprint 1).  Single-phase identification "
            "validated to ±10 K on 10 canonical binaries."
        )
    if sim.get("scheil"):
        items.append(
            "<b>Solidification</b> — Scheil-Gulliver model via pycalphad "
            "(Sprint 2); 5/6 castings within reference tolerance."
        )
    if sim.get("precipitation"):
        items.append(
            "<b>Precipitation kinetics</b> — Kampmann-Wagner numerical model "
            "(Sprint 5); 6/6 canonical (vf, r̄) within factor-of-2-to-4 of "
            "literature."
        )
    if sim.get("microstructure"):
        items.append(
            "<b>Microstructure</b> — Anisotropic KWC phase-field, "
            "Taichi-JIT solver (Sprint 2.6).  Six-arm dendrite at 400² in "
            "~3.6 min on CPU."
        )
    if sim.get("inverse"):
        items.append(
            "<b>Inverse design</b> — BoTorch multi-objective Bayesian "
            "optimisation with conformal-CI-aware acquisition (Sprint 7)."
        )
    if not items:
        items.append(
            "No simulations have been run yet on this composition.  Add "
            "predictions, run a phase calculation, or trigger an inverse-"
            "design loop and re-export the report."
        )

    for src in items:
        out.append(Paragraph("• " + src, S["LeilBody"]))
        out.append(Spacer(1, 2))

    # Closing line.
    out.append(Spacer(1, 8))
    out.append(Paragraph(
        "Full per-prediction provenance JSON is available via the LeilMat "
        "API at <font color='#5b6473'>GET /api/design/{session_id}/provenance</font>.",
        S["LeilCaption"],
    ))
    return out


# ─── Helpers ──────────────────────────────────────────────────────────

def _escape(text: str) -> str:
    """Minimal HTML escape for body text inside ReportLab paragraphs."""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br/>"))


# ─── Public entry point ───────────────────────────────────────────────

def build_pdf(req: ReportPayload) -> bytes:
    """Render the full report and return the PDF bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=25 * mm, rightMargin=25 * mm,
        topMargin=25 * mm, bottomMargin=20 * mm,
        title="LeilMat alloy design report",
        author="LeilMat", subject=req.get("alloy_name") or "Designed Alloy",
        creator="LeilMat",
    )
    S = _styles()
    flowables: list = []

    # Cover lives on page 1; remaining sections start on page 2.
    flowables.extend(_build_cover(req, S))
    flowables.append(PageBreak())

    # Material sections — each one is skipped silently if its inputs
    # are missing.  No "this section intentionally blank" placeholder.
    sections = [
        _build_composition_section(req, S),
        _build_properties_section (req, S),
        _build_phase_section      (req, S),
        _build_kwn_section        (req, S),
        _build_inverse_section    (req, S),
        _build_ai_section         (req, S),
        _build_bibliography_section(req, S),
    ]
    for section in sections:
        if section:
            flowables.extend(section)
            flowables.append(Spacer(1, 8))

    doc.build(
        flowables,
        onFirstPage=_header_footer,
        onLaterPages=_header_footer,
    )
    return buf.getvalue()
