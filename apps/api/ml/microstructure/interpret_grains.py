"""
apps.api.ml.microstructure.interpret_grains
============================================

Layer-1 + Layer-2 interpretation of the two cloud grain features:

  * grain STRUCTURE  — Neper synthetic polycrystal (calibration
    ``deterministic-geometry``: exact cell count + normalized size stats,
    dimensionless unless a physical ``domain_um`` was supplied).
  * grain GROWTH     — SPPARKS Monte-Carlo Potts coarsening (calibration
    ``qualitative``: MC sweeps are NOT physical time, the lattice is
    dimensionless, so only morphology / count / distribution-shape are
    honest readouts).

Layer 1 distils the parsed sim result into a compact, deterministic summary
(coarsening regime, size-distribution uniformity, finite-size warnings).
Layer 2 narrates it via the shared ``call_interpretation_llm`` and proposes
"next move" recommendations whose ``executable`` blocks map to the frontend
action pills.

CRITICAL honesty contract (enforced by the system prompts + fallbacks):
  * Potts grain growth must NEVER be described in physical time (seconds,
    hours) or as a calibrated anneal — MC sweeps ≠ physical time.  Absolute
    µm / ASTM appear only when the user supplied ``domain_um`` (length scale
    only; the coarsening STATE stays uncalibrated either way).
  * Neper is a geometry/statistics engine, not a physics predictor of how a
    microstructure forms.

Allowed ``executable.type`` values (the frontend clamps every value):
  * ``set_grow_params``       — re-run growth  {grid?, sweeps?, domain_um?}
  * ``set_tessellate_params`` — re-run Neper    {n_grains?, morpho?, domain_um?}
  * ``scroll_to_card``        — jump to another card (value = card name)
  * ``run_predict``           — run the property prediction (value = "")
  * ``info_only``             — no action (value = "")
"""
from __future__ import annotations

from typing import Any

from apps.api.ml.interpret_common import call_interpretation_llm

# Re-run param envelopes — kept in sync with the API Field() bounds in
# routers/compute.py (GrainGrowRequest / GrainTessellateRequest).  The
# frontend clamps too; these are here so the deterministic fallback proposes
# in-range values.
_GRID_MIN, _GRID_MAX = 16, 64
_SWEEPS_MIN, _SWEEPS_MAX = 50, 2000
_NGRAINS_MIN, _NGRAINS_MAX = 8, 2000


# ─────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────

def _hist_stats(hist: dict[str, Any] | None) -> dict[str, float] | None:
    """Mean / std / coefficient-of-variation from a {bin_edges, counts} hist."""
    if not isinstance(hist, dict):
        return None
    edges = hist.get("bin_edges") or []
    counts = hist.get("counts") or []
    if len(edges) < 2 or not counts or len(counts) != len(edges) - 1:
        return None
    centers = [(edges[i] + edges[i + 1]) / 2.0 for i in range(len(counts))]
    n = float(sum(counts))
    if n <= 0:
        return None
    mean = sum(c * x for c, x in zip(counts, centers)) / n
    if mean <= 0:
        return None
    var = sum(c * (x - mean) ** 2 for c, x in zip(counts, centers)) / n
    std = var ** 0.5
    return {"mean": round(mean, 4), "std": round(std, 4), "cv": round(std / mean, 3)}


def _uniformity_bucket(cv: float | None) -> str:
    """Bucket a size-distribution coefficient of variation."""
    if cv is None:
        return "unknown"
    if cv < 0.40:
        return "tight"             # near-equiaxed, narrow spread
    if cv < 0.70:
        return "moderate"          # typical MC Potts / Voronoi spread
    return "broad"                 # wide / possibly bimodal


# ─────────────────────────────────────────────────────────────────────
# Grain GROWTH (SPPARKS Potts) — Layer 1
# ─────────────────────────────────────────────────────────────────────

def _coarsening_regime(mean_d_vox: float | None, grid_edge: int) -> str:
    """Qualitative coarsening state from mean grain Ø relative to the box."""
    if not mean_d_vox or grid_edge <= 0:
        return "unknown"
    r = mean_d_vox / grid_edge
    if r < 0.15:
        return "early"             # many fine grains, lots of boundary left
    if r < 0.30:
        return "intermediate"      # steady coarsening
    return "advanced"              # few large grains; finite-size effects loom


def analyse_grain_growth(
    result: dict[str, Any],
    composition: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Distill a SPPARKS Potts grain-growth result into a Layer-1 summary."""
    if not result or result.get("error"):
        return {
            "feature": "grain_growth",
            "regime": "no_data",
            "uniformity": "unknown",
            "quality_warnings": [result.get("error", "no grain-growth data")
                                 if result else "no input"],
            "source": "grain_growth_analysis_v1",
            "calibration": "qualitative",
        }

    grid = result.get("grid") or []
    grid_edge = int(min(grid)) if grid else 0
    n_sites = 1
    for g in (grid or [0]):
        n_sites *= int(g) if g else 1
    grain_count = int(result.get("grain_count") or 0)
    n_sweeps = int(result.get("n_sweeps") or 0)
    mean_d = result.get("mean_grain_size_voxels")
    stats = _hist_stats(result.get("size_distribution_voxels"))
    cv = stats["cv"] if stats else None

    regime = _coarsening_regime(mean_d, grid_edge)
    uniformity = _uniformity_bucket(cv)

    warnings: list[str] = []
    # Always-on honesty caveat for the qualitative Potts model.
    warnings.append(
        "MC sweeps are not physical time and the lattice is dimensionless — "
        "coarsening STATE and absolute size are uncalibrated to a real anneal."
    )
    if grain_count and grain_count < 20:
        warnings.append(
            f"only {grain_count} grains remain — too few for reliable "
            "size statistics; finite-box effects dominate."
        )
    if regime == "advanced":
        warnings.append(
            "advanced coarsening in a small box: a handful of grains now span "
            "an appreciable fraction of the lattice (periodic-image bias)."
        )

    return {
        "feature": "grain_growth",
        "grain_count": grain_count,
        "n_sweeps": n_sweeps,
        "grid": grid,
        "n_sites": n_sites,
        "mean_grain_size_voxels": mean_d,
        "size_cv": cv,
        "regime": regime,
        "uniformity": uniformity,
        "has_domain_um": result.get("domain_um") is not None,
        "mean_grain_size_um": result.get("mean_grain_size_um"),
        "quality_warnings": warnings,
        "source": "grain_growth_analysis_v1",
        "calibration": "qualitative",
    }


GROWTH_SYSTEM_PROMPT = """\
You are a microstructure scientist reviewing a Monte-Carlo Potts grain-GROWTH
simulation (SPPARKS).  The user is exploring how grains coarsen in a real
engineering alloy.

Output strict JSON matching this schema:
  {
    "interpretation":     <string, 3-5 sentences>,
    "regime_call":        <string, short label like "early coarsening, moderate spread">,
    "recommendations": [  # 2-4 items, ordered most-useful first
      {
        "title":     <string, imperative, <= 8 words>,
        "rationale": <string, one sentence>,
        "executable": {                                    # optional
          "type":  "set_grow_params" | "scroll_to_card" | "run_predict" | "info_only",
          "value": <object|string|"">
        }
      }
    ],
    "honest_limitations": [<2-4 bullet strings>]
  }

executable.value by type:
  * set_grow_params  -> object with any of {"grid": int 16-64, "sweeps": int 50-2000, "domain_um": number}
  * scroll_to_card   -> a card name string: "phase" | "precipitation" | "grain_structure" | "predict"
  * run_predict      -> ""
  * info_only        -> ""

HARD HONESTY RULES (violating these is a critical error):
* NEVER express the result in physical time (seconds, hours, minutes) — MC
  sweeps are NOT physical time.  Talk in "more sweeps" / "further coarsening".
* NEVER claim a calibrated anneal temperature/time or a validated grain size.
* Absolute µm appears ONLY if has_domain_um is true, and even then it is an
  INDICATIVE length scale — the coarsening state is still uncalibrated.
* If grain_count < ~20, you MUST flag that the box holds too few grains for
  reliable statistics and recommend a larger lattice.

Style: anchor every claim in the supplied analysis numbers; name the Hall-Petch
strength implication qualitatively (coarser grains -> lower yield).  Recommend
concrete next moves: coarsen further (more sweeps), enlarge the lattice for
statistics, or predict properties for the alloy.  No markdown, pure JSON only.
"""


def _growth_fallback(analysis: dict[str, Any], reason: str) -> dict[str, Any]:
    """Deterministic interpretation when the LLM is unavailable."""
    gc = analysis.get("grain_count") or 0
    sweeps = analysis.get("n_sweeps") or 0
    regime = analysis.get("regime", "unknown")
    uni = analysis.get("uniformity", "unknown")
    grid = analysis.get("grid") or []
    grid_edge = int(min(grid)) if grid else 0

    parts = [
        f"{gc} grains remain after {sweeps} Monte-Carlo sweeps "
        f"({regime} coarsening, {uni} size spread)."
    ]
    if analysis.get("has_domain_um") and analysis.get("mean_grain_size_um"):
        parts.append(
            f"With the supplied domain, mean grain Ø is ~{analysis['mean_grain_size_um']:.1f} µm "
            "(indicative length scale only)."
        )
    parts.append("Coarser grains imply lower Hall-Petch yield strength, qualitatively.")

    recs: list[dict] = []
    if regime in ("early", "intermediate"):
        recs.append({
            "title": "Coarsen further",
            "rationale": "More sweeps continue grain growth toward a steady-state distribution.",
            "executable": {"type": "set_grow_params",
                           "value": {"sweeps": min(_SWEEPS_MAX, max(sweeps * 3, _SWEEPS_MIN))}},
        })
    if gc < 20 and grid_edge:
        recs.append({
            "title": "Enlarge lattice for statistics",
            "rationale": "Too few grains remain for reliable size statistics in this box.",
            "executable": {"type": "set_grow_params",
                           "value": {"grid": min(_GRID_MAX, grid_edge + 16)}},
        })
    recs.append({
        "title": "Predict properties",
        "rationale": "Estimate strength/density for this composition with the grain-size context.",
        "executable": {"type": "run_predict", "value": ""},
    })

    return {
        "interpretation": " ".join(parts),
        "regime_call": f"{regime} coarsening, {uni} spread",
        "recommendations": recs[:4],
        "honest_limitations": [
            f"Numeric-only fallback (LLM unavailable): {reason}.",
        ] + (analysis.get("quality_warnings") or []),
        "source": "deterministic_fallback",
        "calibration": "numeric_only",
    }


async def interpret_grain_growth(
    composition: dict[str, float] | None,
    result: dict[str, Any],
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """LLM-narrate a SPPARKS Potts grain-growth result."""
    analysis = analysis or analyse_grain_growth(result, composition)
    payload = {
        "composition_wt_pct": composition,
        "analysis": analysis,
    }
    return await call_interpretation_llm(
        system_prompt=GROWTH_SYSTEM_PROMPT,
        user_payload=payload,
        fallback_fn=lambda reason: _growth_fallback(analysis, reason),
        endpoint_label="grain_growth_interpret",
    )


# ─────────────────────────────────────────────────────────────────────
# Grain STRUCTURE (Neper) — Layer 1
# ─────────────────────────────────────────────────────────────────────

def _astm_regime(astm: float | None) -> str:
    """Coarse/medium/fine label from an ASTM E112 grain number."""
    if astm is None:
        return "unknown"
    if astm < 5:
        return "coarse"
    if astm < 8:
        return "medium"
    return "fine"


def analyse_grain_structure(
    result: dict[str, Any],
    composition: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Distill a Neper polycrystal result into a Layer-1 summary."""
    if not result or result.get("error"):
        return {
            "feature": "grain_structure",
            "regime": "no_data",
            "uniformity": "unknown",
            "quality_warnings": [result.get("error", "no grain-structure data")
                                 if result else "no input"],
            "source": "grain_structure_analysis_v1",
            "calibration": "deterministic-geometry",
        }

    grain_count = int(result.get("grain_count") or 0)
    morpho = result.get("morpho", "voronoi")
    has_domain = result.get("domain_um") is not None
    astm = result.get("astm_grain_number")
    stats = _hist_stats(result.get("size_distribution_normalized"))
    cv = stats["cv"] if stats else None
    if cv is None and result.get("mean_grain_size_normalized") and result.get("std_grain_size_normalized"):
        m = result["mean_grain_size_normalized"]
        s = result["std_grain_size_normalized"]
        cv = round(s / m, 3) if m else None

    uniformity = _uniformity_bucket(cv)
    regime = _astm_regime(astm) if has_domain else "dimensionless"

    warnings: list[str] = []
    if not has_domain:
        warnings.append(
            "no domain_um supplied — grain sizes are DIMENSIONLESS (unit-cube "
            "fraction); set a physical domain edge to get µm + ASTM."
        )
    warnings.append(
        "Neper is a geometry/statistics engine, not a physics predictor of how "
        "this microstructure forms."
    )

    return {
        "feature": "grain_structure",
        "grain_count": grain_count,
        "morpho": morpho,
        "uniformity": uniformity,
        "size_cv": cv,
        "has_domain_um": has_domain,
        "domain_um": result.get("domain_um"),
        "mean_grain_size_um": result.get("mean_grain_size_um"),
        "astm_grain_number": astm,
        "regime": regime,
        "quality_warnings": warnings,
        "source": "grain_structure_analysis_v1",
        "calibration": "deterministic-geometry",
    }


STRUCTURE_SYSTEM_PROMPT = """\
You are a microstructure scientist reviewing a synthetic polycrystal generated
by Neper (a geometry/statistics tessellation engine).  The user is exploring a
real engineering alloy.

Output strict JSON matching this schema:
  {
    "interpretation":     <string, 3-5 sentences>,
    "regime_call":        <string, short label like "fine equiaxed, tight spread">,
    "recommendations": [  # 2-4 items, ordered most-useful first
      {
        "title":     <string, imperative, <= 8 words>,
        "rationale": <string, one sentence>,
        "executable": {                                    # optional
          "type":  "set_tessellate_params" | "scroll_to_card" | "run_predict" | "info_only",
          "value": <object|string|"">
        }
      }
    ],
    "honest_limitations": [<2-4 bullet strings>]
  }

executable.value by type:
  * set_tessellate_params -> object with any of {"n_grains": int 8-2000, "morpho": "voronoi"|"graingrowth", "domain_um": number}
  * scroll_to_card        -> a card name string: "phase" | "precipitation" | "grain_growth" | "predict"
  * run_predict           -> ""
  * info_only             -> ""

HARD HONESTY RULES (violating these is a critical error):
* Neper is GEOMETRY/STATISTICS, not a physics prediction of microstructure
  formation — never claim it predicts how grains nucleate or grow.
* Cell count and the NORMALIZED size distribution are exact; absolute µm and
  the ASTM number exist ONLY if has_domain_um is true.
* If has_domain_um is false, your FIRST recommendation must be to set a domain
  edge (set_tessellate_params with domain_um) so size becomes physical (µm + ASTM).

Style: anchor every claim in the supplied numbers; relate grain size to
Hall-Petch strength qualitatively (finer -> stronger).  Useful next moves:
set a physical domain for µm/ASTM, try graingrowth morphology for a more
coarsened topology, coarsen this structure dynamically (grain_growth card), or
predict properties.  No markdown, pure JSON only.
"""


def _structure_fallback(analysis: dict[str, Any], reason: str) -> dict[str, Any]:
    """Deterministic interpretation when the LLM is unavailable."""
    gc = analysis.get("grain_count") or 0
    morpho = analysis.get("morpho", "voronoi")
    uni = analysis.get("uniformity", "unknown")
    has_domain = analysis.get("has_domain_um")

    parts = [f"{gc}-grain {morpho} polycrystal with a {uni} size distribution."]
    if has_domain and analysis.get("mean_grain_size_um"):
        parts.append(
            f"Mean grain Ø ~{analysis['mean_grain_size_um']:.1f} µm, "
            f"ASTM {analysis.get('astm_grain_number')} ({analysis.get('regime')})."
        )
        parts.append("Finer grains imply higher Hall-Petch yield strength, qualitatively.")
    else:
        parts.append("Sizes are dimensionless until a physical domain edge is set.")

    recs: list[dict] = []
    if not has_domain:
        recs.append({
            "title": "Set domain for µm + ASTM",
            "rationale": "A physical cube edge converts normalized sizes to µm and an ASTM number.",
            "executable": {"type": "set_tessellate_params", "value": {"domain_um": 100.0}},
        })
    if morpho == "voronoi":
        recs.append({
            "title": "Try grain-growth morphology",
            "rationale": "Laguerre/graingrowth tessellation gives a more coarsened topology.",
            "executable": {"type": "set_tessellate_params", "value": {"morpho": "graingrowth"}},
        })
    recs.append({
        "title": "Coarsen dynamically (Potts)",
        "rationale": "Run Monte-Carlo grain growth to see this structure evolve.",
        "executable": {"type": "scroll_to_card", "value": "grain_growth"},
    })
    recs.append({
        "title": "Predict properties",
        "rationale": "Estimate strength/density for this composition.",
        "executable": {"type": "run_predict", "value": ""},
    })

    return {
        "interpretation": " ".join(parts),
        "regime_call": f"{gc}-grain {morpho}, {uni} spread",
        "recommendations": recs[:4],
        "honest_limitations": [
            f"Numeric-only fallback (LLM unavailable): {reason}.",
        ] + (analysis.get("quality_warnings") or []),
        "source": "deterministic_fallback",
        "calibration": "numeric_only",
    }


async def interpret_grain_structure(
    composition: dict[str, float] | None,
    result: dict[str, Any],
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """LLM-narrate a Neper synthetic-polycrystal result."""
    analysis = analysis or analyse_grain_structure(result, composition)
    payload = {
        "composition_wt_pct": composition,
        "analysis": analysis,
    }
    return await call_interpretation_llm(
        system_prompt=STRUCTURE_SYSTEM_PROMPT,
        user_payload=payload,
        fallback_fn=lambda reason: _structure_fallback(analysis, reason),
        endpoint_label="grain_structure_interpret",
    )


# ─────────────────────────────────────────────────────────────────────
# CPFEM stress-strain (DAMASK) — Layer 1 + Layer 2
# ─────────────────────────────────────────────────────────────────────

def analyse_stress_strain(
    result: dict[str, Any],
    composition: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Distill a DAMASK CPFEM flow-curve result into a Layer-1 summary."""
    if not result or result.get("error"):
        return {
            "feature": "stress_strain",
            "regime": "no_data",
            "quality_warnings": [result.get("error", "no CPFEM data")
                                 if result else "no input"],
            "source": "stress_strain_analysis_v1",
            "calibration": "literature-correlation",
        }
    ys = result.get("yield_strength_MPa")
    flow = result.get("flow_stress_MPa")
    hardening = None
    if ys and flow and ys > 0:
        hardening = round((flow - ys) / ys, 3)   # fractional post-yield rise
    return {
        "feature": "stress_strain",
        "family": result.get("family"),
        "phase": result.get("phase"),
        "n_grains": result.get("n_grains"),
        "cells": result.get("cells"),
        "max_strain_pct": result.get("max_strain_pct"),
        "youngs_modulus_GPa": result.get("youngs_modulus_GPa"),
        "yield_strength_MPa": ys,
        "flow_stress_MPa": flow,
        "hardening_fraction": hardening,
        "quality_warnings": result.get("warnings") or [],
        "source": "stress_strain_analysis_v1",
        "calibration": "literature-correlation",
    }


STRESS_STRAIN_SYSTEM_PROMPT = """\
You are a mechanical metallurgist reviewing a crystal-plasticity (DAMASK CPFEM)
uniaxial-tension simulation of a synthetic polycrystal RVE.

Output strict JSON matching this schema:
  {
    "interpretation":     <string, 3-5 sentences>,
    "regime_call":        <string, short label like "low-hardening FCC flow">,
    "recommendations": [  # 2-4 items, most useful first
      {
        "title":     <string, imperative, <= 8 words>,
        "rationale": <string, one sentence>,
        "executable": {                                    # optional
          "type":  "set_cpfem_params" | "scroll_to_card" | "run_predict" | "info_only",
          "value": <object|string|"">
        }
      }
    ],
    "honest_limitations": [<2-4 bullet strings>]
  }

executable.value by type:
  * set_cpfem_params -> object with any of {"cells": int 8-32, "n_grains": int 4-64, "max_strain": number 0.005-0.10, "n_increments": int 10-60}
  * scroll_to_card   -> "grain_structure" | "grain_growth" | "phase" | "predict"
  * run_predict      -> ""
  * info_only        -> ""

HARD HONESTY RULES (violating these is a critical error):
* This is calibration="literature-correlation": the flow-curve SHAPE, hardening
  trend, and modulus are meaningful, but the ABSOLUTE stress depends on the
  literature CRSS (phenopowerlaw), NOT fit to this alloy/temper. Never present
  it as a validated/measured flow curve.
* The RVE is a synthetic random-orientation polycrystal with periodic BCs — no
  texture, second phases, or precipitates. Say so if comparing to a real alloy.
* Young's modulus is the closed-form polycrystal (Hill) average of the elastic
  constants — robust; the yield is a 0.2 %-offset on the simulated curve.

Style: anchor every claim in the supplied numbers (yield, modulus, hardening).
Useful next moves: refine the RVE (more grains / finer increments for a smoother
curve), extend the strain range, or cross-check with the ML property prediction.
No markdown, pure JSON only.
"""


def _stress_strain_fallback(analysis: dict[str, Any], reason: str) -> dict[str, Any]:
    ys = analysis.get("yield_strength_MPa")
    flow = analysis.get("flow_stress_MPa")
    E = analysis.get("youngs_modulus_GPa")
    hard = analysis.get("hardening_fraction")
    parts = []
    if ys is not None:
        parts.append(f"0.2%-offset yield ≈ {ys} MPa")
    if flow is not None:
        parts.append(f"flow stress ≈ {flow} MPa at {analysis.get('max_strain_pct')}% strain")
    if E is not None:
        parts.append(f"E ≈ {E} GPa (Hill average)")
    summary = ("CPFEM uniaxial tension of a "
               f"{analysis.get('n_grains')}-grain {analysis.get('family','').upper()} RVE: "
               + ", ".join(parts) + ".") if parts else "CPFEM flow curve computed."
    if hard is not None:
        summary += f" Post-yield hardening ~{round(100*hard)}% of yield."

    recs = [{
        "title": "Refine the RVE",
        "rationale": "More grains + increments give a smoother, better-converged flow curve.",
        "executable": {"type": "set_cpfem_params", "value": {"n_grains": 32, "n_increments": 40}},
    }, {
        "title": "Cross-check with ML prediction",
        "rationale": "Compare this physics-based yield to the data-driven property model.",
        "executable": {"type": "run_predict", "value": ""},
    }]

    return {
        "interpretation": summary,
        "regime_call": f"{analysis.get('family','fcc').upper()} flow curve",
        "recommendations": recs,
        "honest_limitations": [
            f"Numeric-only fallback (LLM unavailable): {reason}.",
        ] + (analysis.get("quality_warnings") or []),
        "source": "deterministic_fallback",
        "calibration": "numeric_only",
    }


async def interpret_stress_strain(
    composition: dict[str, float] | None,
    result: dict[str, Any],
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """LLM-narrate a DAMASK CPFEM stress-strain result."""
    analysis = analysis or analyse_stress_strain(result, composition)
    payload = {"composition_wt_pct": composition, "analysis": analysis}
    return await call_interpretation_llm(
        system_prompt=STRESS_STRAIN_SYSTEM_PROMPT,
        user_payload=payload,
        fallback_fn=lambda reason: _stress_strain_fallback(analysis, reason),
        endpoint_label="stress_strain_interpret",
    )
