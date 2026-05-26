"""
Matplotlib chart renderers for the PDF report.

Each helper takes a structured input (dicts / lists from the session
payload) and returns a ``BytesIO`` PNG.  We use the non-interactive
``Agg`` backend so the api container doesn't need a display server.

Charts are sized for A4 portrait pages (page width ≈ 170 mm content
area at 25 mm margins).  At 150 dpi a 6-inch-wide chart prints sharp
at full page width.
"""
from __future__ import annotations

import io
from typing import Iterable

import matplotlib
matplotlib.use("Agg")            # noqa: E402  — must precede pyplot
import matplotlib.pyplot as plt  # noqa: E402

import numpy as np


# Brand-accent colour shared with the LeilMat header / landing page.
ACCENT_GOLD    = "#f7af41"
ACCENT_GOLD_BG = "#f7af411a"     # 10 % alpha for fill regions
INK            = "#15171d"
INK_SOFT       = "#5b6473"


def _common_style() -> None:
    """Apply LeilMat house style to the current pyplot.rcParams."""
    plt.rcParams.update({
        "font.family":     "DejaVu Sans",
        "font.size":        9,
        "axes.edgecolor":   "#c7ccd6",
        "axes.linewidth":   0.6,
        "axes.labelcolor":  INK_SOFT,
        "axes.titlesize":   10,
        "axes.titleweight": "bold",
        "xtick.color":      INK_SOFT,
        "ytick.color":      INK_SOFT,
        "xtick.labelsize":  8,
        "ytick.labelsize":  8,
        "grid.color":       "#e6e8ee",
        "grid.linewidth":   0.5,
    })


def _to_png(fig: "matplotlib.figure.Figure") -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf


# ─── Property radar ────────────────────────────────────────────────────

# Per-property nominal "max for normalisation" — chosen so a typical
# engineering alloy sits in the 0.5-0.9 range.  Used to map raw values
# onto a 0-1 radar axis.
RADAR_NORM = {
    "yield_strength_MPa":        700.0,
    "ultimate_strength_MPa":     900.0,
    "elongation_pct":            40.0,
    "density_g_cm3":             10.0,    # inverse direction: lower is better
    "thermal_conductivity_W_mK": 250.0,
    "electrical_resistivity":    100.0,
    "hardness_HV":               400.0,
    "youngs_modulus_GPa":        300.0,
    "melting_point_K":           2500.0,
    "cost_per_kg_usd":           50.0,    # inverse: lower is better
}

# Human labels for the radar wedges (kept short to fit the axis).
RADAR_LABEL = {
    "yield_strength_MPa":        "σy",
    "ultimate_strength_MPa":     "UTS",
    "elongation_pct":            "Elong.",
    "density_g_cm3":             "ρ",
    "thermal_conductivity_W_mK": "λ_th",
    "electrical_resistivity":    "ρ_e",
    "hardness_HV":               "HV",
    "youngs_modulus_GPa":        "E",
    "melting_point_K":           "Tm",
    "cost_per_kg_usd":           "Cost",
}

# Properties where "lower is better" — invert the normalised value.
_INVERSE_PROPS = {"density_g_cm3", "cost_per_kg_usd"}


def render_property_radar(properties: dict) -> io.BytesIO | None:
    """Render a property radar chart.  Returns None when fewer than 3
    plottable axes are available.

    Values that aren't plain floats (structured ``{value: x}`` dicts,
    qualitative strings, composition echoes) are tolerated by the loop
    via ``isinstance`` + a ``.get("value")`` fallback — so this chart
    works whether the caller has pre-normalised or not.
    """
    pairs: list[tuple[str, float]] = []
    for k, v in properties.items():
        if k not in RADAR_NORM:
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            pairs.append((k, float(v)))
        elif isinstance(v, dict):
            inner = v.get("value")
            if isinstance(inner, (int, float)) and not isinstance(inner, bool):
                pairs.append((k, float(inner)))
    if len(pairs) < 3:
        return None     # < 3 axes is a bar chart, not a radar

    _common_style()

    keys   = [k for k, _ in pairs]
    values = []
    for k, v in pairs:
        norm = float(v) / RADAR_NORM[k]
        # Clamp + invert "lower-is-better" properties so all axes mean
        # "further from centre = better."
        if k in _INVERSE_PROPS:
            norm = max(0.0, 1.0 - norm)
        values.append(max(0.0, min(1.0, norm)))

    # Close the polygon by repeating the first point.
    angles = np.linspace(0, 2 * np.pi, len(keys), endpoint=False).tolist()
    angles += angles[:1]
    values += values[:1]

    fig, ax = plt.subplots(figsize=(5.5, 5.5), subplot_kw=dict(polar=True))
    ax.plot(angles, values, color=ACCENT_GOLD, linewidth=1.6)
    ax.fill(angles, values, color=ACCENT_GOLD, alpha=0.18)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([RADAR_LABEL.get(k, k) for k in keys])
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["", "0.5", "", "1.0"])
    ax.set_ylim(0, 1.0)
    ax.set_title("Property profile (normalised, higher = better)",
                 pad=18, color=INK)
    ax.spines["polar"].set_color("#c7ccd6")
    ax.spines["polar"].set_linewidth(0.6)

    return _to_png(fig)


# ─── Phase assemblage bar ──────────────────────────────────────────────

def render_phase_bar(stable_phases: list[dict]) -> io.BytesIO | None:
    """Horizontal bar chart of stable phases by formation energy.

    ``stable_phases`` items have ``formula`` and ``formation_energy`` fields
    (eV/atom).  Lower (more negative) = more thermodynamically stable.
    """
    rows = [(p.get("formula", "?"), float(p.get("formation_energy", 0.0)))
            for p in stable_phases if p.get("formula")]
    if not rows:
        return None
    rows.sort(key=lambda r: r[1])  # most stable first
    rows = rows[:10]
    labels, values = zip(*rows)

    _common_style()
    fig, ax = plt.subplots(figsize=(6.5, max(2.2, 0.32 * len(rows) + 0.8)))
    bars = ax.barh(range(len(rows)), values, color=ACCENT_GOLD, alpha=0.85,
                   edgecolor=ACCENT_GOLD)
    for b, v in zip(bars, values):
        ax.text(b.get_width() - 0.02, b.get_y() + b.get_height() / 2,
                f"{v:+.3f}", ha="right", va="center", fontsize=7.5, color="white")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlabel("Formation energy (eV/atom — lower = more stable)")
    ax.set_title("Stable phases on the convex hull", color=INK)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    return _to_png(fig)


# ─── Pareto front (inverse-design) ────────────────────────────────────

def render_pareto(candidates: list[dict], x_field: str, y_field: str,
                  x_label: str, y_label: str) -> io.BytesIO | None:
    """Scatter of inverse-design candidates on a 2D objective plane."""
    pts = [(c.get(x_field), c.get(y_field)) for c in candidates]
    pts = [p for p in pts if p[0] is not None and p[1] is not None]
    if len(pts) < 2:
        return None
    xs, ys = zip(*pts)

    _common_style()
    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    ax.scatter(xs, ys, color=ACCENT_GOLD, s=44, edgecolor="white",
               linewidth=0.8, alpha=0.9)
    # Highlight the Pareto frontier with a faint line through min-x/max-y
    sorted_pts = sorted(zip(xs, ys), key=lambda p: p[0])
    front: list[tuple[float, float]] = []
    best_y = float("-inf")
    for x, y in sorted_pts:
        if y > best_y:
            front.append((x, y))
            best_y = y
    if len(front) >= 2:
        fx, fy = zip(*front)
        ax.plot(fx, fy, "--", color=ACCENT_GOLD, alpha=0.55, linewidth=1.2)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title("Inverse-design Pareto front", color=INK)
    ax.grid(linestyle=":", alpha=0.4)
    return _to_png(fig)


# ─── KWN precipitation kinetics ───────────────────────────────────────

def render_kwn_kinetics(time_series: list[dict]) -> io.BytesIO | None:
    """Three stacked curves: mean radius, number density, volume fraction
    over time (log scale).  ``time_series`` is the standard KWN output."""
    if not time_series or len(time_series) < 3:
        return None
    ts        = [p.get("time_s", 0.0) for p in time_series]
    radii     = [p.get("mean_radius_nm", 0.0) for p in time_series]
    densities = [p.get("number_density_m3", 0.0) for p in time_series]
    fractions = [p.get("volume_fraction", 0.0) for p in time_series]

    _common_style()
    fig, axes = plt.subplots(3, 1, figsize=(6.4, 5.2), sharex=True)
    for ax, ys, ylabel, fmt in zip(
        axes,
        (radii, densities, fractions),
        ("Mean radius (nm)", "Number density (1/m³)", "Volume fraction"),
        ("plain", "sci", "plain"),
    ):
        ax.plot(ts, ys, color=ACCENT_GOLD, linewidth=1.4)
        ax.fill_between(ts, 0, ys, color=ACCENT_GOLD, alpha=0.12)
        ax.set_ylabel(ylabel)
        ax.grid(linestyle=":", alpha=0.4)
        ax.set_xscale("log")
        if fmt == "sci":
            ax.ticklabel_format(axis="y", style="sci", scilimits=(-3, 3))
    axes[-1].set_xlabel("Aging time (s, log scale)")
    fig.suptitle("KWN precipitation kinetics", y=0.97, color=INK,
                 fontweight="bold", fontsize=10)
    fig.tight_layout()
    return _to_png(fig)


# Convenience iterator so callers can omit empty charts in one loop.
def iter_named_pngs(*pngs: tuple[str, io.BytesIO | None]) -> Iterable[tuple[str, io.BytesIO]]:
    for name, png in pngs:
        if png is not None:
            yield name, png
