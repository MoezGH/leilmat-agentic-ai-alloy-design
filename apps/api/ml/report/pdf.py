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
    KeepTogether, HRFlowable,
)
from reportlab.pdfgen        import canvas as rl_canvas
from reportlab.graphics.shapes import Drawing, Circle
from reportlab.graphics       import renderPDF

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


def _section_heading(title: str, S) -> list:
    """Return a [thin-gold-rule, heading] pair so each section opens
    with the same visual divider.  Keeps the eye anchored as you scroll
    through a multi-page report."""
    return [
        Spacer(1, 6),
        HRFlowable(
            width="100%", thickness=0.8, color=GOLD,
            spaceBefore=0, spaceAfter=2, hAlign="LEFT",
        ),
        Paragraph(title, S["LeilSection"]),
    ]


def _extract_scalar(val: Any) -> float | None:
    """Normalise a property value to a plain float, or ``None`` if it
    can't be coerced.

    Accepts three shapes the canvas may surface:

      * Plain numeric  ``280.0``                             → 280.0
      * Structured     ``{"value": 280, "source": "RF"}``    → 280.0
      * String         ``"Excellent"``                        → None
      * Anything else (nested dict without ``value``, list, etc.) → None

    Lets the property table + radar gracefully skip qualitative or
    composite scores (corrosion ratings, manufacturability composites)
    that the Zustand store mirrors into ``properties`` but that don't
    belong in a scalar table cell.
    """
    if val is None:
        return None
    if isinstance(val, bool):              # narrow before int — True/False are ints
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, dict):
        inner = val.get("value")
        if isinstance(inner, (int, float)) and not isinstance(inner, bool):
            return float(inner)
        return None
    if isinstance(val, str):
        try:
            return float(val)
        except ValueError:
            return None
    return None


def _extract_interval(val: Any) -> tuple[float, float] | None:
    """Mirror of ``_extract_scalar`` for ±CI pairs.  Accepts
    ``[lo, hi]``, ``(lo, hi)``, or a dict shape ``{"lower": …,
    "upper": …}``; returns ``None`` on anything else."""
    if val is None:
        return None
    if isinstance(val, (list, tuple)) and len(val) == 2:
        try:
            lo = float(val[0])
            hi = float(val[1])
            return (lo, hi)
        except (TypeError, ValueError):
            return None
    if isinstance(val, dict):
        lo = val.get("lower")
        hi = val.get("upper")
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
            return (float(lo), float(hi))
    return None


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

# LeilMat brand mark — matches apps/web/app/icon.svg byte-for-byte
# (same 5 internal dot positions + radii + greys) but re-expressed as
# a ReportLab ``Drawing`` so we can render it at any pt size without
# rasterising an SVG.  Sibling to leil.xyz/favicon.svg: warm-gold moon
# + 3-tone grey constellation.
def leilmat_logo(size_pt: float = 36) -> Drawing:
    """Return a Drawing of the LeilMat mark at ``size_pt × size_pt``."""
    d = Drawing(size_pt, size_pt)
    # The SVG inner content lives in a 462 × 462 box.  Scale to size_pt.
    scale = size_pt / 462.0

    # ── Outer gold moon ────────────────────────────────────────────
    d.add(Circle(
        size_pt / 2, size_pt / 2, size_pt / 2,
        fillColor=GOLD, strokeColor=None,
    ))

    # ── 5 internal grey dots ───────────────────────────────────────
    # Coordinates are the same five (cx, cy, r) triples shipped in
    # apps/web/app/icon.svg.  SVG is y-down, ReportLab is y-up, so we
    # flip via ``y_rl = (462 − y_svg) × scale``.
    grays = {
        "9ca3af": colors.HexColor("#9ca3af"),   # gray-400
        "d1d5db": colors.HexColor("#d1d5db"),   # gray-300
        "6b7280": colors.HexColor("#6b7280"),   # gray-500
    }
    inner = [
        (144.0,   144.0, 43.3, "9ca3af"),   # upper-left, biggest
        (253.0,   253.0, 21.7, "d1d5db"),   # centre
        (180.5,   325.0, 14.4, "9ca3af"),   # lower-left
        (289.0,   108.0, 18.0, "d1d5db"),   # upper-right
        (108.0,   253.0, 10.8, "6b7280"),   # mid-left, deepest grey
    ]
    for cx_svg, cy_svg, r_svg, key in inner:
        d.add(Circle(
            cx_svg * scale,
            (462.0 - cy_svg) * scale,
            r_svg * scale,
            fillColor=grays[key],
            strokeColor=None,
        ))
    return d


# ─── Unicode font registration ────────────────────────────────────────
# ReportLab's built-in Helvetica is Latin-1 only — it renders a .notdef
# box (■) for en-dashes, subscripts, the macron in "r̄", arrows (→),
# ≈/≤, etc., which the LLM-generated rationale uses heavily.  Embed
# DejaVu Sans (a full-Unicode TTF that matplotlib already bundles, so no
# new dependency) so every glyph renders.  Falls back to Helvetica if
# the TTFs can't be located — the report still builds, just with the
# old glyph limitation.
def _register_unicode_font() -> tuple[str, str, str]:
    """Register DejaVu Sans + Bold + Oblique; return the resolved
    (regular, bold, oblique) font names.  Idempotent."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.pdfmetrics import registerFontFamily

    try:
        import os
        import matplotlib
        ttf_dir = os.path.join(
            os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf",
        )
        faces = {
            "LeilSans":          "DejaVuSans.ttf",
            "LeilSans-Bold":     "DejaVuSans-Bold.ttf",
            "LeilSans-Oblique":  "DejaVuSans-Oblique.ttf",
        }
        # Register each only if not already present (import-time safe to
        # call more than once across requests).
        registered = set(pdfmetrics.getRegisteredFontNames())
        for name, fname in faces.items():
            if name in registered:
                continue
            path = os.path.join(ttf_dir, fname)
            if not os.path.exists(path):
                raise FileNotFoundError(path)
            pdfmetrics.registerFont(TTFont(name, path))
        # Map the family so inline <b>/<i> markup resolves to the right
        # face inside Paragraphs.
        registerFontFamily(
            "LeilSans",
            normal="LeilSans", bold="LeilSans-Bold",
            italic="LeilSans-Oblique", boldItalic="LeilSans-Bold",
        )
        return ("LeilSans", "LeilSans-Bold", "LeilSans-Oblique")
    except Exception:                                                  # noqa: BLE001
        # Any failure → keep the built-in Helvetica family.
        return ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique")


FONT_BODY, FONT_BOLD, FONT_OBLIQUE = _register_unicode_font()


def _styles():
    """Build LeilMat's shared paragraph style sheet (cached per call)."""
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(
        name="LeilTitle", parent=base["Title"],
        fontName=FONT_BOLD, fontSize=28, leading=32,
        textColor=INK, alignment=0, spaceAfter=4,
    ))
    base.add(ParagraphStyle(
        name="LeilSubtitle", parent=base["Normal"],
        fontName=FONT_BODY, fontSize=11, leading=15,
        textColor=INK_SOFT, alignment=0, spaceAfter=10,
    ))
    base.add(ParagraphStyle(
        name="LeilSection", parent=base["Heading1"],
        fontName=FONT_BOLD, fontSize=14, leading=18,
        textColor=INK, alignment=0, spaceBefore=10, spaceAfter=8,
    ))
    base.add(ParagraphStyle(
        name="LeilEyebrow", parent=base["Normal"],
        fontName=FONT_BOLD, fontSize=8, leading=10,
        textColor=GOLD, alignment=0,
        spaceAfter=4,
    ))
    base.add(ParagraphStyle(
        name="LeilBody", parent=base["Normal"],
        fontName=FONT_BODY, fontSize=9.5, leading=14,
        textColor=INK, alignment=0, spaceAfter=6,
    ))
    base.add(ParagraphStyle(
        name="LeilCaption", parent=base["Normal"],
        fontName=FONT_OBLIQUE, fontSize=8, leading=11,
        textColor=INK_FAINT, alignment=0, spaceAfter=2,
    ))
    base.add(ParagraphStyle(
        name="LeilQuote", parent=base["Normal"],
        fontName=FONT_BODY, fontSize=9, leading=13,
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
        ("FONT",        (0, 0), (-1, -1), FONT_BODY, 9),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
        ("BACKGROUND",  (0, 0), (-1, header_rows - 1), INK),
        ("FONT",        (0, 0), (-1, header_rows - 1), FONT_BOLD, 9),
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

    # ── Top header strip ──────────────────────────────────────────
    # Thin gold rule across the top.
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.8)
    canvas.line(25 * mm, A4[1] - 12 * mm, A4[0] - 25 * mm, A4[1] - 12 * mm)

    # LeilMat brand mark + wordmark, top-left.  The Drawing is
    # rendered at 12 pt square; vertically aligned to sit with the
    # baseline of the wordmark.
    logo_pt = 12
    logo_x  = 25 * mm
    logo_y  = A4[1] - 18 * mm - 2  # 2 pt nudge so it kisses the baseline
    renderPDF.draw(leilmat_logo(logo_pt), canvas, logo_x, logo_y)

    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(INK)
    canvas.drawString(logo_x + logo_pt + 5, A4[1] - 18 * mm, "LeilMat")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(INK_SOFT)
    canvas.drawString(logo_x + logo_pt + 5 + 32, A4[1] - 18 * mm,
                      "alloy design report")

    # Top-right page marker.
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(INK_SOFT)
    canvas.drawRightString(A4[0] - 25 * mm, A4[1] - 18 * mm,
                           f"Page {doc.page}")

    # ── Bottom footer ─────────────────────────────────────────────
    # Hairline rule above the footer for visual closure.
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.4)
    canvas.line(25 * mm, 17 * mm, A4[0] - 25 * mm, 17 * mm)

    # Left half: validation disclaimer.
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(INK_FAINT)
    canvas.drawString(
        25 * mm, 12 * mm,
        "Predictions carry source + uncertainty.  "
        "Validate against experiment before production.",
    )

    # Right half: "Generated by Leil AI" + domain.  Use the same gold
    # accent on the wordmark so the attribution lines up with the
    # rest of the brand family.
    domain_text = "app.example.org"
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(INK_FAINT)
    gen_label = "Generated by "
    leil_word = "Leil AI"
    gen_x = A4[0] - 25 * mm - canvas.stringWidth(domain_text, "Helvetica", 7.5) \
                            - canvas.stringWidth(" · ",  "Helvetica", 7.5) \
                            - canvas.stringWidth(gen_label,   "Helvetica", 7.5) \
                            - canvas.stringWidth(leil_word,   "Helvetica-Bold", 7.5)

    canvas.drawString(gen_x, 12 * mm, gen_label)
    gen_x += canvas.stringWidth(gen_label, "Helvetica", 7.5)
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.setFillColor(GOLD)
    canvas.drawString(gen_x, 12 * mm, leil_word)
    gen_x += canvas.stringWidth(leil_word, "Helvetica-Bold", 7.5)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(INK_FAINT)
    canvas.drawString(gen_x, 12 * mm, " · ")
    gen_x += canvas.stringWidth(" · ", "Helvetica", 7.5)
    canvas.drawString(gen_x, 12 * mm, domain_text)

    canvas.restoreState()


# ─── Section builders ─────────────────────────────────────────────────

def _build_cover(req: ReportPayload, S) -> list:
    """Cover page — big logo, alloy name, designer, date, top-line
    composition, and an optional LLM-generated executive summary."""
    alloy_name = req.get("alloy_name") or "Designed Alloy"
    designer   = req.get("designer")   or "LeilMat session"
    session_id = req.get("session_id") or "—"
    today      = dt.date.today().isoformat()
    exec_summary = req.get("executive_summary")

    # Headline composition (one-line, sorted by descending wt %).
    comp = req.get("composition") or {}
    if comp:
        comp_pairs = sorted(comp.items(), key=lambda kv: -float(kv[1] or 0))
        comp_str   = "-".join(f"{el}{round(float(v), 1)}" for el, v in comp_pairs)
    else:
        comp_str = "no composition"

    out: list = []

    # ── Big brand mark up top ─────────────────────────────────────
    # The Drawing flowable centres on its parent's left edge; nudge
    # via a small Spacer pair so it sits ~70 pt below the page top.
    out.append(Spacer(1, 28))
    out.append(leilmat_logo(56))
    out.append(Spacer(1, 28))

    out.append(Paragraph("ALLOY DESIGN REPORT", S["LeilEyebrow"]))
    out.append(Paragraph(alloy_name, S["LeilTitle"]))
    out.append(Paragraph(comp_str, S["LeilSubtitle"]))

    # Gold accent rule under the headline cluster — visually closes the
    # top zone before the metadata table.
    out.append(Spacer(1, 6))
    out.append(HRFlowable(
        width="60%", thickness=1.4, color=GOLD,
        spaceBefore=0, spaceAfter=0, hAlign="LEFT",
    ))
    out.append(Spacer(1, 22))

    # ── Metadata table ───────────────────────────────────────────
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

    # ── Executive summary (LLM-generated, optional) ──────────────
    # Drops in when the report endpoint successfully called the
    # ``executive_summary`` helper.  Absent when the budget was
    # exhausted, the model failed, or the endpoint was called with
    # ``with_summary=False``.
    if exec_summary:
        out.append(Spacer(1, 24))
        out.append(Paragraph("EXECUTIVE SUMMARY", S["LeilEyebrow"]))
        # Mark this block as LLM-authored prose so a reader never mistakes
        # its (potentially reworded / rounded) numbers for the computed,
        # uncertainty-carrying values in the Predicted Properties table.
        out.append(Paragraph(
            "AI-generated narrative — verify every figure against the computed "
            "Predicted Properties table before relying on it.",
            S["LeilCaption"],
        ))
        out.append(Spacer(1, 4))
        # The summary is short markdown prose — render bold / italics
        # properly rather than dumping raw ** markers.
        out.extend(_markdown_to_flowables(exec_summary.strip(), S))

    out.append(Spacer(1, 28))
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
    out.extend(_section_heading("Composition", S))
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
    """Property table with values + CI + method, plus a radar chart.

    The incoming ``properties`` dict may carry plain scalars, structured
    ``{value, source, …}`` dicts, qualitative strings, or even composition
    echoes — see ``_extract_scalar`` for the normalisation contract.  We
    silently skip rows that can't be reduced to a scalar so a single bad
    field doesn't blank out the whole table.
    """
    raw_props = req.get("properties") or {}

    # First pass: normalise to a flat ``{key: float}`` map.  Drop anything
    # that doesn't have a usable scalar (composition echo, "Excellent"
    # strings, manufacturability composites).
    props: dict[str, float] = {}
    for key, val in raw_props.items():
        s = _extract_scalar(val)
        if s is not None:
            props[key] = s

    if not props:
        return []

    raw_intervals = req.get("property_intervals") or {}
    out = []
    out.extend(_section_heading("Predicted properties", S))

    rows = [["Property", "Value", "± 95 % CI", "Method"]]
    for key, val in props.items():
        label, unit, method = _PROP_LABELS.get(key, (key, "", "—"))
        interval = _extract_interval(raw_intervals.get(key))
        ci_str = (
            f"± {abs(interval[1] - interval[0]) / 2:.2g}"
            if interval is not None else "—"
        )
        rows.append([
            Paragraph(f"<b>{label}</b>", S["LeilBody"]),
            f"{val:.3g} {unit}".strip(),
            ci_str,
            method,
        ])
    out.append(Table(
        rows,
        colWidths=[55 * mm, 35 * mm, 28 * mm, 35 * mm],
        style=_data_table_style(),
    ))

    # Radar chart — only if ≥ 3 numeric properties to plot.  Pass the
    # already-normalised dict so the chart doesn't have to redo the
    # scalar coercion.
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


def _normalise_phases(raw: Any) -> list[dict[str, Any]]:
    """Coerce a phases payload into ``[{formula, formation_energy}]``.

    The phase data reaches the report in several shapes depending on
    which card produced it:
      * list of dicts   ``[{"formula": "Mg2Si", "formation_energy": -0.3}]``
      * list of strings ``["FCC_A1", "Mg2Si"]``  (CALPHAD phase names —
        no per-phase energy; was crashing the builder with
        ``'str' object has no attribute 'get'``)
      * dict keyed by phase name ``{"FCC_A1": 0.71, "Mg2Si": 0.02}``
      * anything else   → []

    Items without an energy get 0.0 so the table still renders the
    formula; the bar chart treats 0.0 as "unknown" gracefully.
    """
    if isinstance(raw, dict):
        return [
            {"formula": str(k),
             "formation_energy": float(v) if isinstance(v, (int, float)) else 0.0}
            for k, v in raw.items()
        ]
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            out.append({"formula": item, "formation_energy": 0.0})
        elif isinstance(item, dict):
            fe = item.get("formation_energy")
            out.append({
                "formula": str(item.get("formula", item.get("name", "?"))),
                "formation_energy": float(fe) if isinstance(fe, (int, float)) else 0.0,
            })
        # non-str / non-dict items are silently skipped
    return out


def _build_phase_section(req: ReportPayload, S) -> list:
    """Stable phases (CALPHAD or MP-hull) + bar chart."""
    sim = req.get("simulation_results") or {}
    phase_bucket = sim.get("phase") if isinstance(sim.get("phase"), dict) else {}
    result = phase_bucket.get("result") if isinstance(phase_bucket.get("result"), dict) else {}
    raw_phases = result.get("phases") or req.get("stable_phases") or []

    phases = _normalise_phases(raw_phases)
    if not phases:
        return []

    out = []
    out.extend(_section_heading("Phase assemblage", S))
    rows = [["Formula", "Formation energy (eV/atom)"]]
    for p in sorted(phases, key=lambda r: r["formation_energy"])[:12]:
        fe = p["formation_energy"]
        rows.append([
            Paragraph(f"<b>{p['formula']}</b>", S["LeilBody"]),
            f"{fe:+.4f}" if fe != 0.0 else "—",
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
    out.extend(_section_heading("Precipitation kinetics (KWN)", S))
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
    inv_bucket = sim.get("inverse") if isinstance(sim.get("inverse"), dict) else {}
    inv_result = inv_bucket.get("result") if isinstance(inv_bucket.get("result"), dict) else {}
    raw_candidates = inv_result.get("candidates") or []
    # Defensive: only keep dict-shaped candidates — a malformed payload
    # with bare strings/numbers would otherwise crash ``c.get`` below.
    candidates = [c for c in raw_candidates if isinstance(c, dict)]
    if not candidates:
        return []
    out = []
    out.extend(_section_heading("Inverse-design candidates", S))
    pareto = render_pareto(
        candidates,
        x_field="density_g_cm3", y_field="yield_strength_MPa",
        x_label="Density (g/cm³)", y_label="Yield strength (MPa)",
    )
    if pareto is not None:
        out.append(Image(pareto, width=160 * mm, height=110 * mm))

    # Top-5 by composite score (if scored) or by yield strength.
    def _num(c: dict, *keys: str) -> float:
        for k in keys:
            v = c.get(k)
            if isinstance(v, (int, float)):
                return float(v)
        return 0.0

    top = sorted(candidates, key=lambda c: -_num(c, "score", "yield_strength_MPa"))[:5]
    rows = [["Composition", "Density", "YS (MPa)", "Score"]]
    for c in top:
        comp = c.get("composition") if isinstance(c.get("composition"), dict) else {}
        comp_pairs = [(el, v) for el, v in comp.items() if isinstance(v, (int, float))]
        comp_str = "-".join(f"{el}{round(v, 1)}"
                            for el, v in sorted(comp_pairs, key=lambda kv: -kv[1]))
        has_score = isinstance(c.get("score"), (int, float))
        rows.append([
            comp_str or "—",
            f"{_num(c, 'density_g_cm3'):.3f}",
            f"{_num(c, 'yield_strength_MPa'):.0f}",
            f"{_num(c, 'score'):.2f}" if has_score else "—",
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
    # Only dict-shaped Global AI messages, in chronological order.
    # (Filter non-dicts defensively — a malformed messages payload with
    # bare strings would otherwise crash ``m.get`` here.)
    msgs = [m for m in messages
            if isinstance(m, dict) and m.get("contextType") == "global"]
    if not msgs:
        return []
    out = []
    out.extend(_section_heading("AI design rationale", S))
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
            out.append(Paragraph("<b>You</b>", S["LeilEyebrow"]))
            # User turns are plain typed prose — escape, don't markdown.
            out.append(Paragraph(_escape(content), S["LeilBody"]))
        else:
            out.append(Paragraph("<b>LeilMat AI</b>", S["LeilEyebrow"]))
            # Assistant turns are markdown — render headings / bold /
            # lists / tables as real flowables instead of raw asterisks.
            out.extend(_markdown_to_flowables(content, S))

        # Applied actions, if any.
        applied = m.get("appliedActionIdx") or []
        actions = m.get("actions") or []
        if applied and isinstance(actions, list):
            applied_labels = []
            for i in applied:
                if not isinstance(i, int) or i >= len(actions):
                    continue
                a = actions[i]
                if not isinstance(a, dict):
                    continue
                act = a.get("action") if isinstance(a.get("action"), dict) else {}
                applied_labels.append(a.get("label") or act.get("op") or "?")
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
    out.extend(_section_heading("Provenance &amp; bibliography", S))

    items: list[str] = []
    props = req.get("properties") or {}
    intervals = req.get("property_intervals") or {}
    has_ml = any(_PROP_LABELS.get(k, ("", "", ""))[2] == "RF + conformal"
                 for k in props if props[k] is not None)
    if has_ml:
        items.append(
            "<b>ML property predictions</b> — Random-Forest models trained on the "
            "LeilMat Al/Ti/Ni/Steel handbook-grade dataset.  Mean "
            "absolute error and 95 % confidence intervals via conformal "
            "calibration on held-out folds."
        )
    sim = req.get("simulation_results") or {}
    if sim.get("phase"):
        items.append(
            "<b>Phase assemblage</b> — pycalphad equilibrium solver on bundled "
            "BSD-licensed TDB files (COST507, mc_fecocrnbti, alcrni, alni, "
            "alzn, alcocrni).  Single-phase identification "
            "validated to ±10 K on 10 canonical binaries."
        )
    if sim.get("scheil"):
        items.append(
            "<b>Solidification</b> — Scheil-Gulliver model via pycalphad; "
            "5/6 castings within reference tolerance."
        )
    if sim.get("precipitation"):
        items.append(
            "<b>Precipitation kinetics</b> — Kampmann-Wagner numerical model; "
            "6/6 canonical (vf, r̄) within factor-of-2-to-4 of "
            "literature."
        )
    if sim.get("microstructure"):
        items.append(
            "<b>Microstructure</b> — Anisotropic KWC phase-field, "
            "Taichi-JIT solver.  Six-arm dendrite at 400² in "
            "~3.6 min on CPU."
        )
    if sim.get("inverse"):
        items.append(
            "<b>Inverse design</b> — BoTorch multi-objective Bayesian "
            "optimisation with conformal-CI-aware acquisition."
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


def _escape_plain(text: str) -> str:
    """HTML-escape WITHOUT converting newlines — for inline-markdown runs
    where we manage line breaks ourselves."""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


# Inline-markdown → ReportLab mini-markup.  Applied AFTER HTML-escaping
# so the escape doesn't mangle our generated tags.  Order matters:
# bold (**/__) before italic (*/_) so "**x**" doesn't get eaten as two
# italic markers.
import re as _re

_MD_BOLD   = _re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_MD_ITALIC = _re.compile(r"(?<![\*_])\*(?!\*)(.+?)(?<!\*)\*(?!\*)|(?<![\*_])_(?!_)(.+?)_(?!_)")
_MD_CODE   = _re.compile(r"`([^`]+?)`")
_MD_LINK   = _re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")


def _inline_md(text: str) -> str:
    """Convert a single line of inline markdown to ReportLab markup."""
    s = _escape_plain(text)
    s = _MD_CODE.sub(
        lambda m: f'<font face="Courier" size="8.5">{m.group(1)}</font>', s)
    s = _MD_BOLD.sub(lambda m: f"<b>{m.group(1) or m.group(2)}</b>", s)
    s = _MD_ITALIC.sub(lambda m: f"<i>{m.group(1) or m.group(2)}</i>", s)
    s = _MD_LINK.sub(
        lambda m: f'<link href="{m.group(2)}" color="#0369a1">{m.group(1)}</link>', s)
    return s


# Markdown block patterns.
_RE_HEADING = _re.compile(r"^(#{1,6})\s+(.*)$")
_RE_BULLET  = _re.compile(r"^\s*[-*+]\s+(.*)$")
_RE_NUMBER  = _re.compile(r"^\s*(\d+)\.\s+(.*)$")
_RE_TABLE   = _re.compile(r"^\s*\|.*\|\s*$")
_RE_TSEP    = _re.compile(r"^\s*\|?[\s:\-|]+\|?\s*$")   # |---|:--:|


def _markdown_to_flowables(md: str, S) -> list:
    """Convert an LLM markdown string into ReportLab flowables.

    Handles the shapes the design copilot actually emits: ATX headings,
    bold/italic/code/links inline, ``-``/``*`` bullets, ``1.`` numbered
    lists, and GFM pipe tables.  Everything else falls through to a
    paragraph.  Deliberately small — not a full CommonMark parser, just
    enough that the rationale reads as formatted prose instead of raw
    asterisks and pipes.
    """
    out: list = []
    lines = md.replace("\r\n", "\n").split("\n")
    i = 0
    n = len(lines)

    # Lazily-built styles for list items (indented body).
    bullet_style = ParagraphStyle("md_bullet", parent=S["LeilBody"],
                                  leftIndent=12, bulletIndent=2, spaceAfter=2)
    num_style    = ParagraphStyle("md_num", parent=S["LeilBody"],
                                  leftIndent=14, spaceAfter=2)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Blank line → spacing.
        if not stripped:
            out.append(Spacer(1, 4))
            i += 1
            continue

        # GFM table — collect consecutive pipe rows.
        if _RE_TABLE.match(line):
            rows: list[list[str]] = []
            while i < n and _RE_TABLE.match(lines[i]):
                raw = lines[i].strip().strip("|")
                if _RE_TSEP.match(lines[i]):     # separator row → skip
                    i += 1
                    continue
                cells = [c.strip() for c in raw.split("|")]
                rows.append(cells)
                i += 1
            if rows:
                out.append(_md_table(rows, S))
                out.append(Spacer(1, 4))
            continue

        # Heading.
        mh = _RE_HEADING.match(line)
        if mh:
            level = len(mh.group(1))
            txt = _inline_md(mh.group(2).strip())
            style = S["LeilSection"] if level <= 2 else S["LeilEyebrow"]
            out.append(Paragraph(txt, style))
            i += 1
            continue

        # Bullet list item.
        mb = _RE_BULLET.match(line)
        if mb:
            out.append(Paragraph("• " + _inline_md(mb.group(1)), bullet_style))
            i += 1
            continue

        # Numbered list item.
        mn = _RE_NUMBER.match(line)
        if mn:
            out.append(Paragraph(f"{mn.group(1)}. " + _inline_md(mn.group(2)), num_style))
            i += 1
            continue

        # Plain paragraph — gather until a blank line or a block marker.
        para_lines = [stripped]
        i += 1
        while i < n:
            nxt = lines[i]
            if (not nxt.strip()
                    or _RE_HEADING.match(nxt) or _RE_BULLET.match(nxt)
                    or _RE_NUMBER.match(nxt) or _RE_TABLE.match(nxt)):
                break
            para_lines.append(nxt.strip())
            i += 1
        out.append(Paragraph(_inline_md(" ".join(para_lines)), S["LeilBody"]))

    return out


def _md_table(rows: list[list[str]], S) -> Table:
    """Build a ReportLab Table from parsed markdown rows (first = header).
    Cells render inline markdown + wrap via Paragraph."""
    cell_style = ParagraphStyle("md_cell", parent=S["LeilBody"],
                                fontSize=8.5, leading=11, spaceAfter=0)
    head_style = ParagraphStyle("md_cell_h", parent=cell_style,
                                fontName=FONT_BOLD, textColor=colors.white)
    n_cols = max(len(r) for r in rows)
    data = []
    for ri, r in enumerate(rows):
        padded = r + [""] * (n_cols - len(r))
        st = head_style if ri == 0 else cell_style
        data.append([Paragraph(_inline_md(c), st) for c in padded])
    # Even column widths across the content area (~160 mm).
    col_w = (160 * mm) / n_cols
    return Table(data, colWidths=[col_w] * n_cols, style=_data_table_style())


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
