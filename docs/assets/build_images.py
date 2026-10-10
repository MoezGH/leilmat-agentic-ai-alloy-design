#!/usr/bin/env python3
"""
Rebuild the README banner and the GitHub social-preview image.

    python docs/assets/build_images.py

Writes (next to this script):
    banner.svg / banner.png                 README header   (1280x360, PNG rendered at 2x)
    social-preview.svg / social-preview.png GitHub "Social preview" (1280x640)

The artwork is a procedurally generated polycrystal: a Voronoi tessellation read as a grain
map, fading into the page background.  It is DECORATION, not data — nothing in it is a result,
a measurement, or a benchmark number.  It is deterministic (fixed seed), so rebuilding yields
identical output.  The brand mark is the project's own logo (apps/web/public/leil-mat-logo.svg).

PNG output needs `rsvg-convert` (brew install librsvg); without it only the SVGs are written.
GitHub's social preview must be uploaded by hand: Settings -> General -> Social preview.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import Voronoi

HERE = Path(__file__).resolve().parent
LOGO = HERE.parents[1] / "apps" / "web" / "public" / "leil-mat-logo.svg"

BG0, BG1 = "#0a0b0f", "#12151d"            # page background (matches the web app)
GOLD = "#f5a534"                            # brand accent (matches the logo)
GRAINS = ["#161c28", "#1b2332", "#202a3c", "#26324a", "#1a212e", "#2b3a58", "#1e2738"]
FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"

TAGLINE = "AI-native alloy design with honest uncertainty"
SUBLINE = "CALPHAD  ·  Scheil  ·  precipitation  ·  yield strength  ·  cost  ·  inverse design"
CHIPS = ["Conformal uncertainty", "Source provenance", "Refuses instead of extrapolating"]


def grain_field(x0: float, width: int, height: int, spacing: float, seed: int) -> str:
    """SVG polygons for a Voronoi grain map covering x in [x0, width]."""
    rng = np.random.default_rng(seed)
    pts = []
    margin = 2 * spacing
    nx = int((width - x0 + 2 * margin) / spacing) + 1
    ny = int((height + 2 * margin) / spacing) + 1
    for i in range(nx):
        for j in range(ny):
            # staggered rows + jitter reads as equiaxed grains rather than a lattice
            px = x0 - margin + (i + (0.5 if j % 2 else 0.0)) * spacing + rng.uniform(-0.38, 0.38) * spacing
            py = -margin + j * spacing + rng.uniform(-0.38, 0.38) * spacing
            pts.append((px, py))
    pts = np.array(pts)
    vor = Voronoi(pts)

    out = []
    for idx, region_idx in enumerate(vor.point_region):
        region = vor.regions[region_idx]
        if not region or -1 in region:
            continue
        poly = vor.vertices[region]
        cx, cy = poly.mean(axis=0)
        if cx < x0 - spacing or cx > width + spacing or cy < -spacing or cy > height + spacing:
            continue
        u = rng.random()
        if u < 0.035:                                  # a few warm "precipitate" grains
            fill, op = GOLD, 0.80
        elif u < 0.07:
            fill, op = "#7aa2d6", 0.22
        else:
            fill, op = GRAINS[rng.integers(len(GRAINS))], 1.0
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in poly) + " Z"
        out.append(f'<path d="{d}" fill="{fill}" fill-opacity="{op}"/>')
    return "\n    ".join(out)


def logo_inner() -> str:
    s = LOGO.read_text()
    s = re.sub(r"^\s*<svg[^>]*>", "", s, count=1)
    return re.sub(r"</svg>\s*$", "", s)


def chip(x: float, y: float, text: str, fs: int) -> tuple[str, float]:
    w = len(text) * fs * 0.56 + fs * 1.9
    h = fs * 2.15
    svg = (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{h / 2:.1f}" '
           f'fill="{GOLD}" fill-opacity="0.07" stroke="{GOLD}" stroke-opacity="0.55"/>'
           f'<text x="{x + w / 2:.1f}" y="{y + h / 2 + fs * 0.34:.1f}" text-anchor="middle" '
           f'font-family="{FONT}" font-size="{fs}" fill="#f3d9ab">{text}</text>')
    return svg, w


def build(width: int, height: int, *, logo_w: int, title_y: int, tag_fs: int, sub_fs: int,
          chip_fs: int, field_x: float, spacing: float, left: int, seed: int) -> str:
    s = logo_w / 313.0
    logo_h = 98 * s
    # lockup: logo ("moon + Leil") then "Mat" set beside it on the same baseline
    mat_fs = 122 * s
    mat = (f'<text x="{left + 307 * s:.1f}" y="{title_y + 92.77 * s:.1f}" font-family="{FONT}" '
           f'font-size="{mat_fs:.1f}" font-weight="500" fill="#e6e9ef">Mat</text>')
    ty = title_y + logo_h + tag_fs * 1.45
    chips, cx = [], float(left)
    cy = ty + sub_fs * 2.9 + 2
    for c in CHIPS:
        svg, w = chip(cx, cy, c, chip_fs)
        chips.append(svg)
        cx += w + chip_fs * 0.9
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <title>LeilMat — {TAGLINE}</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{BG0}"/><stop offset="1" stop-color="{BG1}"/>
    </linearGradient>
    <linearGradient id="fadeGrad" x1="{field_x - 0.05 * width:.0f}" y1="0" x2="{field_x + 0.30 * width:.0f}" y2="0" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#000"/><stop offset="1" stop-color="#fff"/>
    </linearGradient>
    <mask id="fade"><rect width="{width}" height="{height}" fill="url(#fadeGrad)"/></mask>
    <radialGradient id="glow" cx="0.80" cy="0.55" r="0.55">
      <stop offset="0" stop-color="{GOLD}" stop-opacity="0.10"/><stop offset="1" stop-color="{GOLD}" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="frame"><rect width="{width}" height="{height}"/></clipPath>
  </defs>
  <rect width="{width}" height="{height}" fill="url(#bg)"/>
  <rect width="{width}" height="{height}" fill="url(#glow)"/>
  <g clip-path="url(#frame)"><g mask="url(#fade)" stroke="#9fb3d1" stroke-opacity="0.13" stroke-width="1">
    {grain_field(field_x - 0.12 * width, width, height, spacing, seed)}
  </g></g>
  <svg x="{left}" y="{title_y}" width="{logo_w}" height="{logo_h:.1f}" viewBox="0 0 313 98">{logo_inner()}</svg>
  {mat}
  <text x="{left}" y="{ty:.1f}" font-family="{FONT}" font-size="{tag_fs}" fill="#e2e8f0">{TAGLINE}</text>
  <text x="{left}" y="{ty + sub_fs * 1.9:.1f}" font-family="{FONT}" font-size="{sub_fs}" fill="#8b97ab">{SUBLINE}</text>
  {''.join(chips)}
</svg>
'''


def main() -> int:
    specs = {
        "banner": dict(width=1280, height=360, logo_w=250, title_y=86, tag_fs=26, sub_fs=14,
                       chip_fs=12, field_x=720, spacing=30, left=56, seed=7),
        "social-preview": dict(width=1280, height=640, logo_w=420, title_y=174, tag_fs=40, sub_fs=20,
                               chip_fs=17, field_x=760, spacing=44, left=80, seed=11),
    }
    rsvg = shutil.which("rsvg-convert")
    for name, kw in specs.items():
        svg = build(**kw)
        (HERE / f"{name}.svg").write_text(svg)
        if rsvg:
            scale = 2 if name == "banner" else 1
            subprocess.run([rsvg, "-w", str(kw["width"] * scale), "-o", str(HERE / f"{name}.png"),
                            str(HERE / f"{name}.svg")], check=True)
        print(f"wrote {name}.svg" + (f" + {name}.png" if rsvg else "  (no rsvg-convert: PNG skipped)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
