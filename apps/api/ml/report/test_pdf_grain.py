"""Tests for the grain section + Hall-Petch surfacing in the PDF report.

Dependency-free: we introspect the ReportLab flowables (``Paragraph.text``)
rather than parsing rendered PDF bytes, and assert ``build_pdf`` still emits a
valid ``%PDF`` document end-to-end.
"""
from __future__ import annotations

from reportlab.platypus import Paragraph

from apps.api.ml.report.pdf import (
    build_pdf,
    _build_grain_section,
    _build_properties_section,
    _image_from_base64,
    _styles,
)

# 1×1 PNG — enough to exercise the base64 → Image embed path.
_PNG_1x1 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGA"
    "hKmMIQAAAABJRU5ErkJggg=="
)


def _texts(flowables) -> str:
    """Concatenate the markup text of every Paragraph flowable (recursing
    into KeepTogether) so tests can assert on rendered copy."""
    out = []
    for f in flowables:
        if isinstance(f, Paragraph):
            out.append(f.text)
        sub = getattr(f, "_content", None) or getattr(f, "_flowables", None)
        if sub:
            out.append(_texts(sub))
    return " ".join(out)


def _grain_payload():
    return {
        "alloy_name": "t",
        "composition": {"Al": 97.0, "Mg": 1.0, "Si": 0.6, "Fe": 0.9, "Cu": 0.3, "Cr": 0.2},
        "properties": {
            "yield_strength_MPa": 337.4, "density_g_cm3": 2.70, "hardness_HV": 113,
            "melting_point_K": 920,
            "_details": {"yield_strength_MPa": {"value": 337.4, "hall_petch": {
                "delta_MPa": 9.4, "grain_size_um": 10.0, "d_ref_um": 30.0,
                "k_y_MPa_sqrt_um": 70.0, "family": "Al",
                "calibration": "literature-correlation"}}},
        },
        "simulation_results": {
            "grain_structure": {"result": {
                "grain_count": 100, "morpho": "voronoi", "mean_grain_size_um": 26.0,
                "astm_grain_number": 7.5, "calibration": "deterministic-geometry",
                "png_base64": _PNG_1x1, "warnings": ["Neper is a geometry engine."]},
                "interpretation": {"interpretation": "A 100-grain Voronoi polycrystal.",
                    "regime_call": "fine equiaxed",
                    "honest_limitations": ["Dimensionless unless a domain is set."]}},
            "grain_growth": {"result": {
                "grain_count": 56, "n_sweeps": 150, "grid": [32, 32, 32],
                "mean_grain_size_voxels": 8.1, "calibration": "qualitative",
                "png_base64": _PNG_1x1, "warnings": ["MC sweeps are not physical time."]},
                "interpretation": {"interpretation": "Intermediate coarsening after 150 sweeps.",
                    "regime_call": "intermediate coarsening",
                    "honest_limitations": ["MC sweeps are not physical time."]}},
        },
    }


def test_grain_section_renders_both_sims_with_ai():
    S = _styles()
    txt = _texts(_build_grain_section(_grain_payload(), S))
    assert "Neper" in txt and "Potts" in txt
    assert "AI analysis" in txt
    assert "intermediate coarsening" in txt          # regime label carried through
    assert "150 MC sweeps" in txt and "ASTM" in txt   # honest stats
    # Calibration honesty tags surfaced verbatim.
    assert "deterministic-geometry" in txt and "qualitative" in txt
    # MC-time caveat present.
    assert "not physical time" in txt


def test_grain_section_empty_without_data():
    assert _build_grain_section({"simulation_results": {}}, _styles()) == []
    assert _build_grain_section({}, _styles()) == []


def test_hall_petch_surfaced_in_properties():
    txt = _texts(_build_properties_section(_grain_payload(), _styles()))
    assert "Hall-Petch" in txt
    assert "10.0 µm" in txt or "10 µm" in txt
    assert "literature-correlation" in txt


def test_properties_no_hall_petch_line_without_overlay():
    payload = _grain_payload()
    payload["properties"]["_details"]["yield_strength_MPa"].pop("hall_petch")
    txt = _texts(_build_properties_section(payload, _styles()))
    assert "Hall-Petch" not in txt


def test_image_from_base64():
    assert _image_from_base64(_PNG_1x1) is not None
    assert _image_from_base64("not-valid-base64!!") is None
    assert _image_from_base64(None) is None


def test_build_pdf_end_to_end_with_grains():
    pdf = build_pdf(_grain_payload())
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 5000
