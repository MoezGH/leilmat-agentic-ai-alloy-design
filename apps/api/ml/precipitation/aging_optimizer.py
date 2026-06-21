"""
apps.api.ml.precipitation.aging_optimizer
==========================================

Heat-treatment (aging) optimizer for precipitation-hardened alloys.

A single KWN run (``simulate_curve``) already gives the full vf(t), r̄(t)
trajectory at ONE temperature.  This sweeps a family of aging temperatures,
maps each (vf, r̄) point to its Orowan precipitation-strengthening increment
(``orowan_from_vf_r``), and finds the global peak — i.e. the **under-aged →
peak-aged → over-aged** locus that answers the real design question:

    "What aging schedule (T, t) maximizes precipitation strengthening?"

Output: a family of Δσ_Orowan-vs-time curves (one per temperature), the global
peak (T*, t*, Δσ*, vf*, r̄*), and a plain-language schedule recommendation.

Calibration = ``literature-correlation``.  The KWN kinetics carry fitted γ +
vacancy knobs (see ``interfacial_energy.py``) and Orowan uses literature matrix
constants — so this RANKS schedules and shows the peak-aging trend honestly,
but the absolute Δσ is a screening estimate, not a validated aging curve.  It
reports the precipitation increment Δσ; add the matrix/solid-solution base
(≈ the solutionized yield) for an absolute strength.

v1 supports the Orowan-parametrized families: **aluminum / nickel / titanium**.
"""
from __future__ import annotations

import base64
import io
import math
from typing import Any

from apps.api.ml.precipitation.kwn import simulate_curve
from apps.api.ml.strengthening import _ELEMENT_TO_FAMILY, orowan_from_vf_r

# Orowan matrix data exists only for these families (steel BCC excluded).
_OROWAN_FAMILIES = {"aluminum", "nickel", "titanium"}

# Peak (critical) precipitate radius per family, nm — the shearing↔looping
# crossover where strengthening peaks (literature-correlation).  Al-Mg-Si β″ /
# Al-Cu θ′ peak around a few nm; Ni γ′ and Ti precipitates coarser.
_R_STAR_NM: dict[str, float] = {"aluminum": 2.5, "nickel": 15.0, "titanium": 10.0}


def _ppt_strength(family: str, vf: float, r_nm: float) -> float:
    """Precipitation strengthening Δσ (MPa) — the physically-correct peak-aging
    form ``min(shearing, looping)``.

    * Looping (over-aged, r > r*): ``orowan_from_vf_r`` ∝ √vf / r (falls with r).
    * Shearing (under-aged, r < r*): rises with r; anchored to equal the Orowan
      stress at the family peak radius r* so the two branches cross exactly at
      r* (the peak-age point).  Δσ = min(rising, falling) → peaks at r*.
    """
    if family not in _R_STAR_NM or not vf or not r_nm or vf <= 0 or r_nm <= 0:
        return 0.0
    r_star = _R_STAR_NM[family]
    looping = orowan_from_vf_r(family, vf, r_nm)
    # Shearing branch = Orowan-at-r* scaled by √(r/r*); equals `looping` at r*.
    shearing = orowan_from_vf_r(family, vf, r_star) * math.sqrt(r_nm / r_star)
    return round(min(looping, shearing), 1)

# Sensible artificial-aging windows per family (°C) + a default max aging time.
_AGING_WINDOW: dict[str, tuple[float, float, float]] = {
    # family:        (T_min, T_max, default_max_time_h)
    "aluminum": (120.0, 220.0, 48.0),
    "nickel":   (650.0, 850.0, 100.0),
    "titanium": (450.0, 560.0, 50.0),
}


def family_for_aging(composition: dict[str, float] | None) -> str | None:
    """Family name for the aging optimizer, or None if not Orowan-supported."""
    if not composition:
        return None
    el = max(composition, key=lambda k: composition.get(k, 0) or 0)
    fam = _ELEMENT_TO_FAMILY.get(el)
    return fam if fam in _OROWAN_FAMILIES else None


def _temperatures(family: str, t_min: float | None, t_max: float | None,
                  n: int) -> list[float]:
    lo, hi, _ = _AGING_WINDOW[family]
    lo = float(t_min) if t_min is not None else lo
    hi = float(t_max) if t_max is not None else hi
    if hi <= lo:
        hi = lo + 100.0
    n = max(3, min(int(n), 10))
    step = (hi - lo) / (n - 1)
    return [round(lo + i * step, 1) for i in range(n)]


def optimize_aging(
    composition: dict[str, float],
    phase: str,
    *,
    t_min_C: float | None = None,
    t_max_C: float | None = None,
    max_time_h: float | None = None,
    n_temps: int = 6,
) -> dict[str, Any]:
    """Sweep aging temperature × time → Orowan Δσ; return curves + peak."""
    family = family_for_aging(composition)
    if family is None:
        return {"error": "Aging optimizer supports Al/Ni/Ti-base alloys.",
                "calibration": "literature-correlation"}

    max_time_h = float(max_time_h) if max_time_h else _AGING_WINDOW[family][2]
    max_time_s = max_time_h * 3600.0
    temps = _temperatures(family, t_min_C, t_max_C, n_temps)

    curves: list[dict] = []
    peak = {"delta_sigma_MPa": -1.0}
    for T_C in temps:
        try:
            res = simulate_curve(composition, phase, T_C, max_time_s)
        except Exception as exc:                                       # noqa: BLE001
            return {"error": f"KWN failed at {T_C} °C: {exc}",
                    "calibration": "literature-correlation"}
        traj = res.get("trajectory") or {}
        times_s = traj.get("times_s") or []
        vfs = traj.get("vf") or []
        rs = traj.get("r_bar_nm") or []
        dsig = [_ppt_strength(family, vf, r) for vf, r in zip(vfs, rs)]
        curves.append({
            "T_C": T_C,
            "times_h": [round(t / 3600.0, 4) for t in times_s],
            "delta_sigma_MPa": dsig,
            "vf": [round(float(v), 5) for v in vfs],
            "r_nm": [round(float(r), 2) for r in rs],
        })
        for i, d in enumerate(dsig):
            if d > peak["delta_sigma_MPa"]:
                peak = {"T_C": T_C, "t_h": round(times_s[i] / 3600.0, 3),
                        "delta_sigma_MPa": d, "vf": round(float(vfs[i]), 5),
                        "r_nm": round(float(rs[i]), 2)}

    png = _render_aging_curves(curves, peak)
    rec = _recommendation(peak, max_time_h)
    return {
        "phase": phase,
        "family": family,
        "temperatures_C": temps,
        "max_time_h": max_time_h,
        "curves": curves,
        "peak": peak,
        "recommendation": rec,
        "png_base64": png,
        "source": "kwn_aging_optimizer",
        "calibration": "literature-correlation",
        "warnings": [
            "Δσ is the Orowan precipitation increment (screening estimate, "
            "literature-parametrized KWN + matrix constants) — add the matrix/"
            "solid-solution base (≈ solutionized yield) for absolute strength.",
            "Ranks aging schedules + shows the peak-aging trend; not a validated "
            "aging curve for this exact alloy/temper.",
        ],
    }


def _recommendation(peak: dict, max_time_h: float) -> str:
    if peak.get("delta_sigma_MPa", -1) <= 0:
        return "No meaningful precipitation strengthening in this window."
    t = peak["t_h"]
    t_str = f"{t:.1f} h" if t >= 1 else f"{t * 60:.0f} min"
    tail = (" (peak is at the end of the swept time — try a longer max time)"
            if t >= 0.98 * max_time_h else "")
    return (f"Age at {peak['T_C']:.0f} °C for ~{t_str} → peak Δσ ≈ "
            f"{peak['delta_sigma_MPa']:.0f} MPa "
            f"(vf {peak['vf']:.3f}, r̄ {peak['r_nm']:.1f} nm){tail}.")


def _render_aging_curves(curves: list[dict], peak: dict) -> str | None:
    """Family of Δσ-vs-aging-time curves (log time), peak marked."""
    if not curves:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:                                                  # noqa: BLE001
        return None
    fig, ax = plt.subplots(figsize=(4.6, 3.3), dpi=110)
    cmap = plt.get_cmap("viridis")
    n = len(curves)
    for k, c in enumerate(curves):
        t = [max(x, 1e-3) for x in c["times_h"]]
        ax.plot(t, c["delta_sigma_MPa"], "-", lw=1.4,
                color=cmap(k / max(1, n - 1)), label=f"{c['T_C']:.0f} °C")
    if peak.get("t_h"):
        ax.plot(max(peak["t_h"], 1e-3), peak["delta_sigma_MPa"], "*",
                ms=13, color="#dc2626", zorder=5)
        ax.annotate(f" peak {peak['delta_sigma_MPa']:.0f} MPa\n {peak['T_C']:.0f}°C, {peak['t_h']:.1f}h",
                    (max(peak["t_h"], 1e-3), peak["delta_sigma_MPa"]),
                    fontsize=6.5, color="#991b1b", va="top")
    ax.set_xscale("log")
    ax.set_xlabel("Aging time (h)", fontsize=8)
    ax.set_ylabel("Δσ Orowan (MPa)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(fontsize=6, ncol=2, framealpha=0.6)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()
