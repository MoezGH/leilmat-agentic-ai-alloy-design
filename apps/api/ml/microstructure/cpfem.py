"""DAMASK crystal-plasticity (CPFEM) stress-strain job: script builder + parser.

DAMASK (GPL/AGPL) solves crystal plasticity on a spectral/FFT grid.  We
generate a synthetic Voronoi polycrystal RVE, assign a phenomenological
power-law (``phenopowerlaw``) crystal-plasticity phase with **literature**
slip parameters, pull it in uniaxial tension, and read the homogenized
stress-strain flow curve.

Calibration = ``literature-correlation``.  The flow-curve SHAPE, the
hardening trend, and relative anisotropy are physically meaningful; the
ABSOLUTE stress level depends on the assumed critical resolved shear stress
(literature, NOT fit to the user's exact alloy/temper), so it is a screening
estimate — never a validated flow curve.

Scope (v1): **FCC families only** (Al/Ni/Cu base).  BCC (steel) and HCP (Ti)
need family-specific slip-interaction matrices that must be validated against
the solver before shipping — deferred to a follow-up.  ``family_for_composition``
returns ``None`` for those, and the router turns that into a clear message.

The DAMASK pipeline + python-damask 3.0.2 API were validated end-to-end on the
``leilmat-damask-v1`` snapshot (Voronoi grid → material.yaml → load.yaml →
``DAMASK_grid`` → ``damask.Result`` homogenized average).  The sandbox does the
full solve + postprocess and writes a compact JSON; the API renders the PNG.
"""
from __future__ import annotations

import base64
import io
import json
from typing import Callable

# ── Bounds (RVE size + loading), clamped server-side ──────────────────
MIN_CELLS, MAX_CELLS = 8, 32          # grid = cells³ voxels; 32³ is heavy but capped
MIN_GRAINS, MAX_GRAINS = 4, 64
MIN_STRAIN, MAX_STRAIN = 0.005, 0.10  # total engineering strain (uniaxial tension)
MIN_INCR, MAX_INCR = 10, 60
DEFAULT_CELLS = 16
DEFAULT_GRAINS = 20
DEFAULT_STRAIN = 0.02                 # 2 %
DEFAULT_INCR = 30                     # ~0.07 %/step → resolves elastic E + 0.2 % yield

ARTIFACTS = {"result": "/tmp/cpfem_result.json"}

# ── FCC crystal-plasticity parameter library (literature) ─────────────
# Elastic stiffness (Pa) + phenopowerlaw slip resistance.  Per dominant FCC
# metal so Ni/Cu don't inherit Al's stress level.  Sources: DAMASK example
# (Al), standard single-crystal elastic constants + CRSS handbooks.
_FCC_ELEMENTS = ("Al", "Ni", "Cu", "Ag", "Au", "Pt", "Pb")
_FCC_PARAMS: dict[str, dict] = {
    "Al": {"C_11": 106.75e9, "C_12": 60.41e9, "C_44": 28.34e9,
           "xi_0": 31.0e6, "xi_inf": 63.0e6, "h_0": 75.0e6},
    "Ni": {"C_11": 246.5e9, "C_12": 147.3e9, "C_44": 124.7e9,
           "xi_0": 31.0e6, "xi_inf": 180.0e6, "h_0": 300.0e6},
    "Cu": {"C_11": 168.4e9, "C_12": 121.4e9, "C_44": 75.4e9,
           "xi_0": 16.0e6, "xi_inf": 148.0e6, "h_0": 180.0e6},
}
_FCC_DEFAULT = "Al"


def family_for_composition(composition: dict[str, float] | None) -> str | None:
    """Return ``'fcc'`` when the alloy's majority element is an FCC metal we
    support, else ``None`` (BCC/HCP not supported in v1)."""
    if not composition:
        return None
    majority = max(composition, key=lambda k: composition.get(k, 0) or 0)
    return "fcc" if majority in _FCC_ELEMENTS else None


def _fcc_phase_metal(composition: dict[str, float] | None) -> str:
    """Pick which FCC parameter set to use (the dominant FCC element with a
    curated set; falls back to Al)."""
    if composition:
        for el in sorted(composition, key=lambda k: -(composition.get(k, 0) or 0)):
            if el in _FCC_PARAMS:
                return el
    return _FCC_DEFAULT


def _clamp(v, lo, hi, default):
    try:
        v = type(default)(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _material_header(metal: str) -> str:
    """homogenization + a single FCC phenopowerlaw phase (no material list —
    the sandbox appends per-grain orientations)."""
    p = _FCC_PARAMS.get(metal, _FCC_PARAMS[_FCC_DEFAULT])
    return (
        "homogenization:\n"
        "  SX: {N_constituents: 1, mechanical: {type: pass}}\n"
        "phase:\n"
        f"  {metal}:\n"
        "    lattice: cF\n"
        "    mechanical:\n"
        "      output: [F, P]\n"
        "      elastic: {type: Hooke, "
        f"C_11: {p['C_11']:.4g}, C_12: {p['C_12']:.4g}, C_44: {p['C_44']:.4g}}}\n"
        "      plastic:\n"
        "        type: phenopowerlaw\n"
        "        N_sl: [12]\n"
        "        a_sl: [2.25]\n"
        "        atol_xi: 1.0\n"
        "        dot_gamma_0_sl: [0.001]\n"
        f"        h_0_sl-sl: [{p['h_0']:.4g}]\n"
        "        h_sl-sl: [1, 1, 1.4, 1.4, 1.4, 1.4, 1.4]\n"
        "        n_sl: [20]\n"
        "        output: [xi_sl]\n"
        f"        xi_0_sl: [{p['xi_0']:.4g}]\n"
        f"        xi_inf_sl: [{p['xi_inf']:.4g}]\n"
    )


# The sandbox job: generate RVE → material → load → solve → homogenize → JSON.
# ``__PARAMS_JSON__`` is replaced with a JSON blob so the embedded Python needs
# no f-string brace-escaping.  Runs on the conda base env (python-damask 3.0.2
# + DAMASK_grid both on PATH from the snapshot).
_JOB_TEMPLATE = r'''
import os, glob, subprocess, json, numpy as np, damask
P = json.loads(r"""__PARAMS_JSON__""")
os.makedirs("/tmp/run", exist_ok=True); os.chdir("/tmp/run")
n = int(P["cells"]); cells = np.array([n, n, n]); size = np.ones(3) * 1.0e-4
if P.get("seeds"):
    # Rebuild the user's ACTUAL Neper Voronoi tessellation (seeds in unit-cube
    # coords) at this raster resolution — the same grain structure they ran.
    seeds = np.asarray(P["seeds"], float) * size
    N = len(seeds)
else:
    N = int(P["n_grains"])
    seeds = damask.seeds.from_random(size, N, cells, rng_seed=int(P["seed"]))
damask.GeomGrid.from_Voronoi_tessellation(cells, size, seeds).save("grid")
ori = damask.Rotation.from_random(N, rng_seed=int(P["seed"]) + 1).as_quaternion()
rows = ["  - homogenization: SX\n    constituents:\n      - phase: %s\n        v: 1.0\n"
        "        O: [%.10f, %.10f, %.10f, %.10f]\n" % ((P["phase_name"],) + tuple(q)) for q in ori]
open("material.yaml", "w").write(P["material_header"] + "material:\n" + "".join(rows))
rate = 1.0e-3; t = float(P["max_strain"]) / rate; Ninc = int(P["n_increments"])
open("tension.yaml", "w").write(
    "solver:\n  mechanical: spectral_basic\n"
    "loadstep:\n  - boundary_conditions:\n      mechanical:\n"
    "        dot_F: [[%g, 0, 0], [0, x, 0], [0, 0, x]]\n"
    "        P: [[x, x, x], [x, 0, x], [x, x, 0]]\n"
    "    discretization: {t: %g, N: %d}\n    f_out: 1\n" % (rate, t, Ninc))
r = subprocess.run(["DAMASK_grid", "-g", "grid.vti", "-l", "tension.yaml",
                    "-m", "material.yaml", "-w", "."], capture_output=True, text=True)
h5 = glob.glob("*.hdf5")
out = {"ok": False, "family": "fcc", "phase": P["phase_name"], "cells": n,
       "n_grains": N, "max_strain": float(P["max_strain"]),
       "rve_source": "neper" if P.get("seeds") else "synthetic",
       "calibration": "literature-correlation"}
if r.returncode == 0 and h5:
    res = damask.Result(h5[0]); res.add_stress_Cauchy(); res.add_strain()
    sig = res.get("sigma"); eps = res.get("epsilon_V^0.0(F)")
    avg = lambda d, i: np.asarray(d[i]).reshape(-1, 3, 3).mean(axis=0)
    pts = sorted((float(avg(eps, i)[0, 0]), float(avg(sig, i)[0, 0]) / 1e6) for i in res.increments)
    out.update({"ok": True, "strain": [p[0] for p in pts], "stress_MPa": [p[1] for p in pts]})
else:
    out["error"] = (r.stdout or "")[-1500:]
json.dump(out, open("/tmp/cpfem_result.json", "w"))
print("CPFEM done ok=%s" % out["ok"])
'''


def build_cpfem_script(params: dict) -> str:
    """Build the bash body that runs the DAMASK CPFEM job in the sandbox."""
    composition = params.get("composition") or {}
    if family_for_composition(composition) != "fcc":
        # Caller (router) should have gated this; guard anyway.
        raise ValueError("CPFEM v1 supports FCC alloys (Al/Ni/Cu base) only")

    metal = _fcc_phase_metal(composition)
    # Optional: rebuild the user's actual Neper tessellation from its seeds.
    seeds = params.get("seeds")
    clean_seeds = None
    if isinstance(seeds, list) and seeds:
        clean_seeds = [
            [float(p[0]), float(p[1]), float(p[2])]
            for p in seeds[:MAX_GRAINS]
            if isinstance(p, (list, tuple)) and len(p) >= 3
        ] or None
    job = {
        "cells": _clamp(params.get("cells", DEFAULT_CELLS), MIN_CELLS, MAX_CELLS, DEFAULT_CELLS),
        "n_grains": _clamp(params.get("n_grains", DEFAULT_GRAINS), MIN_GRAINS, MAX_GRAINS, DEFAULT_GRAINS),
        "max_strain": _clamp(params.get("max_strain", DEFAULT_STRAIN), MIN_STRAIN, MAX_STRAIN, DEFAULT_STRAIN),
        "n_increments": _clamp(params.get("n_increments", DEFAULT_INCR), MIN_INCR, MAX_INCR, DEFAULT_INCR),
        "seed": 0,
        "seeds": clean_seeds,            # None → synthetic random RVE
        "phase_name": metal,
        "material_header": _material_header(metal),
    }
    py = _JOB_TEMPLATE.replace("__PARAMS_JSON__", json.dumps(job))
    return (
        "cd /tmp\n"
        "cat > /tmp/cpfem_job.py <<'PYEOF'\n"
        + py
        + "\nPYEOF\n"
        # The snapshot's conda base env has python-damask + DAMASK_grid on PATH.
        "python /tmp/cpfem_job.py\n"
        "ls -la /tmp/cpfem_result.json\n"
    )


# ── parsing (API-side: JSON → metrics + flow-curve PNG) ───────────────

def _hill_youngs_modulus_GPa(metal: str) -> float | None:
    """Polycrystal (Hill-average) Young's modulus from the cubic single-crystal
    elastic constants — a clean closed form, far more robust than the
    flow-curve slope (these FCC params yield near ~0.1 % strain, so only a
    point or two are purely elastic).  Pa → GPa."""
    p = _FCC_PARAMS.get(metal)
    if not p:
        return None
    c11, c12, c44 = p["C_11"] / 1e9, p["C_12"] / 1e9, p["C_44"] / 1e9
    K = (c11 + 2 * c12) / 3.0
    g_voigt = (c11 - c12 + 3 * c44) / 5.0
    denom = 4 * c44 + 3 * (c11 - c12)
    g_reuss = 5 * (c11 - c12) * c44 / denom if denom > 0 else g_voigt
    G = 0.5 * (g_voigt + g_reuss)
    E = 9 * K * G / (3 * K + G)
    return round(E, 1) if E > 0 else None


def _derive_metrics(strain: list[float], stress: list[float],
                    modulus_GPa: float | None = None) -> dict:
    """0.2 %-offset yield, flow stress at the target strain, and peak stress.

    ``modulus_GPa`` (the closed-form elastic modulus) is used for the offset
    line when supplied; otherwise we fall back to the curve's initial slope.
    """
    import numpy as np
    e = np.asarray(strain, float); s = np.asarray(stress, float)
    order = np.argsort(e); e, s = e[order], s[order]
    out: dict = {"flow_stress_MPa": round(float(s[-1]), 1),
                 "peak_stress_MPa": round(float(s.max()), 1)}
    E = modulus_GPa
    if E is None:                                  # fallback: curve slope
        if len(e) >= 2 and e[1] > e[0]:
            E = (s[1] - s[0]) / (e[1] - e[0]) / 1000.0
    out["youngs_modulus_GPa"] = round(E, 1) if E and E > 0 else None
    # 0.2 % offset yield (intersection of the offset line with the curve).
    if E and E > 0:
        offset = s - E * 1000.0 * (e - 0.002)
        for i in range(1, len(e)):
            if offset[i] <= 0:
                ys = float(np.interp(0.0, [offset[i], offset[i - 1]],
                                     [s[i], s[i - 1]]))
                out["yield_strength_MPa"] = round(ys, 1)
                break
    return out


def _render_curve_png(strain: list[float], stress: list[float],
                      metrics: dict) -> str | None:
    """Render the homogenized σ-ε flow curve to a base64 PNG (API-side)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None
    fig, ax = plt.subplots(figsize=(4.2, 3.2), dpi=110)
    ax.plot([100 * x for x in strain], stress, "-o", color="#0ea5e9", ms=3, lw=1.6)
    ys = metrics.get("yield_strength_MPa")
    if ys:
        ax.axhline(ys, ls="--", lw=0.8, color="#f59e0b")
        ax.text(0.02, ys, f" 0.2%% yield ≈ {ys:.0f} MPa", color="#b45309",
                fontsize=7, va="bottom")
    ax.set_xlabel("Engineering strain (%)", fontsize=8)
    ax.set_ylabel("Cauchy stress (MPa)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def parse_cpfem_result(downloaded: dict, *, composition: dict | None = None) -> dict:
    """Turn the sandbox JSON artifact into the final result block."""
    raw = downloaded.get("result")
    if not raw:
        return {"error": "no CPFEM result produced", "calibration": "literature-correlation"}
    try:
        data = json.loads(raw.decode() if isinstance(raw, (bytes, bytearray)) else raw)
    except Exception as exc:
        return {"error": f"unparseable CPFEM result: {exc}",
                "calibration": "literature-correlation"}

    if not data.get("ok"):
        return {"error": "DAMASK solve did not converge: "
                         + (data.get("error", "") or "")[-400:],
                "calibration": "literature-correlation"}

    strain = data.get("strain") or []
    stress = data.get("stress_MPa") or []
    E = _hill_youngs_modulus_GPa(data.get("phase") or "")
    metrics = _derive_metrics(strain, stress, modulus_GPa=E) if len(strain) >= 2 else {}
    png = _render_curve_png(strain, stress, metrics) if strain else None

    return {
        "method": "Crystal-plasticity FFT (DAMASK phenopowerlaw, uniaxial tension)",
        "family": data.get("family", "fcc"),
        "phase": data.get("phase"),
        "cells": data.get("cells"),
        "n_grains": data.get("n_grains"),
        "rve_source": data.get("rve_source", "synthetic"),
        "max_strain_pct": round(100 * float(data.get("max_strain", 0)), 2),
        "stress_strain": {"strain": strain, "stress_MPa": stress},
        **metrics,
        "png_base64": png,
        "source": "damask_cpfem",
        "calibration": "literature-correlation",
        "warnings": [
            "Absolute stress is literature-parametrized (phenopowerlaw CRSS not "
            "fit to this exact alloy/temper) — screening estimate, not a "
            "validated flow curve.",
            (
                "RVE geometry is your Neper grain structure (rasterized), with "
                "random crystal orientations + periodic BCs; no texture, second "
                "phases, or precipitates."
                if data.get("rve_source") == "neper" else
                "Synthetic random-orientation RVE with periodic BCs; no texture, "
                "second phases, or precipitates."
            ),
        ],
    }


def make_cpfem_job(params: dict) -> tuple[str, dict, Callable[[dict], dict]]:
    """Return (bash body, artifacts, parse) for the orchestrator."""
    composition = params.get("composition") or {}
    body = build_cpfem_script(params)

    def _parse(downloaded: dict) -> dict:
        return parse_cpfem_result(downloaded, composition=composition)

    return body, ARTIFACTS, _parse
