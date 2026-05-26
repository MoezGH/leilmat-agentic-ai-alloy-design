"""
Audit-grade PDF report generator for LeilMat design sessions.

Exposes ``build_pdf(req: ReportRequest) -> bytes`` which renders a
multi-page PDF including composition, properties + CIs, radar chart,
phase assemblage, microstructure, precipitation kinetics, inverse-
design results, the Global AI design rationale, and a bibliography
that footnotes every numerical claim.

Architecture
────────────
  pdf.py      Top-level builder + section helpers (reportlab.platypus).
  charts.py   Matplotlib chart renderers — return PNG bytes in memory.
  styles.py   Shared paragraph styles, colours, table styles.
"""
