"""
apps.api.ml.precipitation.interpret
====================================

Layer-1 + Layer-2 interpretation of KWN precipitation kinetics.

Layer 1 (deterministic):
  - aging regime classification (under-aged / peak-aged / over-aged)
  - peak-age comparison to literature canonical values (per-phase)
  - estimated Orowan strengthening contribution Δσ
  - LSW-coarsening detection from trajectory slope
  - dimensionless aging clock Z = D·t/r̄²

Layer 2 (LLM):
  - narrative tying (T, time, composition) to the strengthening outcome
  - process recommendations (over-aging cure, peak-age window, etc.)
  - cross-references to the CALPHAD card for the equilibrium driving force
  - honest limitations (single-precipitate, mean-field, no PSD)
"""
from __future__ import annotations

import math
from typing import Any

from apps.api.ml.interpret_common import call_interpretation_llm


# ─────────────────────────────────────────────────────────────────────
# Per-phase literature peak-aged references
# ─────────────────────────────────────────────────────────────────────

# (vf, r̄_nm) at the documented peak-aged condition.  Used as the
# "north star" for the aging-regime classifier and the LLM prompt.
PHASE_PEAK_REFERENCE: dict[str, dict[str, Any]] = {
    "Al2Cu_theta_prime": {
        "alloy_example": "Al-4Cu T6",
        "vf_peak":       0.03,
        "r_nm_peak":     50.0,
        "peak_T_C":      190,
        "peak_t_h":      8,
        "matrix_family": "aluminum",
    },
    "Mg2Si_beta_doubleprime": {
        "alloy_example": "6061-T6",
        "vf_peak":       0.012,
        "r_nm_peak":     5.0,
        "peak_T_C":      175,
        "peak_t_h":      8,
        "matrix_family": "aluminum",
    },
    "MgZn2_eta_prime": {
        "alloy_example": "7075-T6",
        "vf_peak":       0.05,
        "r_nm_peak":     10.0,
        "peak_T_C":      120,
        "peak_t_h":      24,
        "matrix_family": "aluminum",
    },
    "Ni3Al_gamma_prime": {
        "alloy_example": "IN 718 γ' (low-Al)",
        "vf_peak":       0.04,
        "r_nm_peak":     20.0,
        "peak_T_C":      720,
        "peak_t_h":      8,
        "matrix_family": "nickel",
    },
    "Ni3Nb_gamma_doubleprime": {
        "alloy_example": "IN 718 γ\"",
        "vf_peak":       0.15,
        "r_nm_peak":     30.0,
        "peak_T_C":      720,
        "peak_t_h":      8,
        "matrix_family": "nickel",
    },
    "Ti_alpha_widmanstatten": {
        "alloy_example": "Ti-6-4 STA",
        "vf_peak":       0.07,
        "r_nm_peak":     1000.0,
        "peak_T_C":      950,
        "peak_t_h":      2,
        "matrix_family": "titanium",
    },
}


# Same matrix-property table as apps/api/ml/strengthening.py.  Duplicated
# here to avoid an import cycle; the values are stable.
_MATRIX_DATA = {
    "aluminum":      {"M": 3.06, "G_GPa": 27.0, "b_nm": 0.286},
    "titanium":      {"M": 3.00, "G_GPa": 44.0, "b_nm": 0.295},
    "nickel":        {"M": 3.06, "G_GPa": 80.0, "b_nm": 0.250},
    "general_steel": {"M": 2.75, "G_GPa": 80.0, "b_nm": 0.248},
}


def _orowan_estimate(vf: float, r_nm: float, family: str) -> float:
    """Δσ_Orowan in MPa from (vf, r̄) and the family's matrix shear modulus.

    Mirrors apps/api/ml/strengthening.orowan_strengthening but operates on
    the values returned by the live KWN solve (not the canonical
    temper-default table).  Capped at 1000 MPa per the shearing crossover.
    """
    if vf <= 0 or r_nm <= 0 or family not in _MATRIX_DATA:
        return 0.0
    m = _MATRIX_DATA[family]
    M, G_MPa, b_nm = m["M"], m["G_GPa"] * 1e3, m["b_nm"]
    if r_nm <= b_nm:
        return 0.0
    L_nm = r_nm * math.sqrt(2.0 * math.pi / (3.0 * vf))
    sigma = 0.84 * M * G_MPa * b_nm / L_nm
    return float(min(sigma, 1000.0))


# ─────────────────────────────────────────────────────────────────────
# Trajectory analysis: aging regime + coarsening detection
# ─────────────────────────────────────────────────────────────────────

def _aging_regime(
    final_vf: float,
    final_r_nm: float,
    trajectory: dict[str, list[float]] | None,
    phase_ref: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    """Classify (under-aged | peak-aged | over-aged) using the trajectory
    slope and a comparison to the literature peak point.

    Returns (regime, diagnostic_dict).
    """
    diag: dict[str, Any] = {}
    if trajectory is None or not trajectory.get("times_s"):
        return "unknown", diag

    times = trajectory["times_s"]
    vfs   = trajectory.get("vf") or []
    rs    = trajectory.get("r_bar_nm") or []
    if len(times) < 5 or len(vfs) != len(times) or len(rs) != len(times):
        return "unknown", diag

    # Late-half slope estimate
    n = len(times)
    late = max(2, n // 4)
    dt = times[-1] - times[-late]
    if dt <= 0:
        return "unknown", diag

    dvf_dt = (vfs[-1] - vfs[-late]) / dt
    dr_dt  = (rs[-1]  - rs[-late])  / dt
    relative_vf_growth = dvf_dt * times[-1] / max(final_vf, 1e-9)
    relative_r_growth  = dr_dt  * times[-1] / max(final_r_nm, 1e-9)

    diag.update({
        "dvf_dt_late":       round(float(dvf_dt), 6),
        "dr_dt_late":        round(float(dr_dt), 6),
        "vf_growth_fraction": round(float(relative_vf_growth), 3),
        "r_growth_fraction":  round(float(relative_r_growth), 3),
    })

    if phase_ref:
        vf_ratio = final_vf / max(phase_ref["vf_peak"], 1e-9)
        r_ratio  = final_r_nm / max(phase_ref["r_nm_peak"], 1e-9)
        diag["vf_ratio_to_peak"] = round(float(vf_ratio), 3)
        diag["r_ratio_to_peak"]  = round(float(r_ratio), 3)
    else:
        vf_ratio = 1.0
        r_ratio  = 1.0

    # Classification
    if relative_vf_growth > 0.10:
        return "under_aged", diag    # still nucleating / growing in vf
    if r_ratio > 2.5 and relative_r_growth > 0.10:
        return "over_aged", diag     # coarsening past peak
    if 0.4 <= vf_ratio <= 2.5 and 0.3 <= r_ratio <= 2.5:
        return "peak_aged", diag
    if r_ratio > 2.5:
        return "over_aged", diag
    if vf_ratio < 0.4:
        return "under_aged", diag
    return "transitional", diag


# ─────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────

def analyse_precipitation(
    kwn_result: dict[str, Any],
    composition: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Distill a KWN result into a structured Layer-1 summary."""
    if not kwn_result or kwn_result.get("error"):
        return {
            "regime":           "no_data",
            "phase":             None,
            "vf_predicted":      None,
            "r_nm_predicted":    None,
            "vf_reference":      None,
            "r_nm_reference":    None,
            "orowan_MPa":        None,
            "quality_warnings": [kwn_result.get("error", "no kwn data")
                                  if kwn_result else "no input"],
            "source":            "precipitation_kinetics_analysis_v1",
            "calibration":       "deterministic",
        }

    phase = kwn_result.get("phase")
    value = kwn_result.get("value") or {}
    vf = float(value.get("volume_fraction") or 0)
    r_nm = float(value.get("mean_radius_nm") or 0)
    T_C = value.get("aging_temperature_C")
    t_s = value.get("aging_time_s")
    trajectory = kwn_result.get("trajectory")

    phase_ref = PHASE_PEAK_REFERENCE.get(phase) if phase else None
    family    = (phase_ref or {}).get("matrix_family", "aluminum")

    regime, diag = _aging_regime(vf, r_nm, trajectory, phase_ref)
    orowan = _orowan_estimate(vf, r_nm, family)

    warnings: list[str] = []
    if phase and phase_ref is None:
        warnings.append(
            f"phase '{phase}' has no canonical peak-age reference; "
            "regime classification used trajectory slope only"
        )
    if regime == "over_aged":
        warnings.append("r̄ has grown well past the canonical peak value — "
                        "Δσ_Orowan estimate decays as 1/L̄")
    if T_C is not None and phase_ref and abs(T_C - phase_ref["peak_T_C"]) > 80:
        warnings.append(
            f"aging T={T_C} °C is far from the canonical peak-age T="
            f"{phase_ref['peak_T_C']} °C for {phase_ref['alloy_example']}"
        )

    return {
        "regime":            regime,
        "phase":             phase,
        "alloy_example":     (phase_ref or {}).get("alloy_example"),
        "vf_predicted":      round(vf, 5) if vf else 0.0,
        "r_nm_predicted":    round(r_nm, 2) if r_nm else 0.0,
        "vf_reference":      (phase_ref or {}).get("vf_peak"),
        "r_nm_reference":    (phase_ref or {}).get("r_nm_peak"),
        "peak_T_C_reference":(phase_ref or {}).get("peak_T_C"),
        "peak_t_h_reference":(phase_ref or {}).get("peak_t_h"),
        "matrix_family":     family,
        "orowan_MPa":        round(orowan, 0),
        "aging_T_C":         T_C,
        "aging_time_s":      t_s,
        "trajectory_diagnostics": diag,
        "quality_warnings":  warnings,
        "source":            "precipitation_kinetics_analysis_v1",
        "calibration":       "deterministic",
    }


# ─────────────────────────────────────────────────────────────────────
# Layer 2 — LLM interpretation
# ─────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a senior physical metallurgist reviewing a KWN (Kampmann-Wagner
numerical) precipitation-kinetics calculation.  The user is exploring how
a specific aging condition affects a strengthening phase.

Output strict JSON matching this schema:
  {
    "interpretation":     <string, 3-5 sentences>,
    "regime_call":        <string, short label like "peak-aged β″ in 6xxx Al">,
    "recommendations": [  # 2-3 items
      {
        "title":     <string, imperative, ≤ 8 words>,
        "rationale": <string, one sentence>,
        "executable": {                                    # optional
          "type":    "set_temperature_C" | "set_aging_hours"
                   | "scroll_to_card" | "info_only",
          "value":   <number for T or hours; card key for scroll; "" for info>
        }
      }
    ],
    "honest_limitations": [<2-4 bullet strings>]
  }

Style constraints:
* Anchor every claim in the supplied analysis (vf, r̄, Orowan estimate,
  trajectory slope).  Quote vf_ratio_to_peak / r_ratio_to_peak when
  judging where the user sits on the aging curve.
* Name the phase in metallurgical convention: β″-Mg₂Si, η′-MgZn₂,
  γ′-Ni₃Al, γ″-Ni₃Nb, θ′-Al₂Cu, α-Widmanstätten.
* For under_aged: suggest concrete (T, t) to reach peak, anchored on
  peak_T_C_reference / peak_t_h_reference.
* For over_aged: explain WHY (LSW coarsening; r̄ ∝ t^(1/3)) and
  recommend a lower-T anneal to slow coarsening.
* For peak_aged: validate the choice, mention the Δσ_Orowan contribution
  in MPa, recommend cross-checking with the CALPHAD equilibrium card.
* Limitations MUST include: single-precipitate mean-field (real PSD has
  width), KWN's literature-fit γ + vacancy-enhancement factor, and
  morphology caveats for needle/disk precipitates.
* No filler; no markdown; no chatty intro/outro.  Pure JSON only.
"""


def _fallback(analysis: dict[str, Any], reason: str) -> dict[str, Any]:
    regime = analysis.get("regime", "unknown")
    vf = analysis.get("vf_predicted") or 0
    r = analysis.get("r_nm_predicted") or 0
    vf_ref = analysis.get("vf_reference")
    r_ref = analysis.get("r_nm_reference")
    orowan = analysis.get("orowan_MPa") or 0
    phase = analysis.get("phase") or "precipitate"
    alloy = analysis.get("alloy_example") or ""

    parts = [
        f"{phase}: vf = {vf:.4f}, r̄ = {r:.1f} nm at "
        f"{analysis.get('aging_T_C', '?')} °C / "
        f"{(analysis.get('aging_time_s') or 0) / 3600:.1f} h."
    ]
    if vf_ref is not None and r_ref is not None:
        parts.append(
            f"Literature peak-age reference for {alloy}: "
            f"vf ≈ {vf_ref}, r̄ ≈ {r_ref} nm."
        )
    parts.append(
        f"Classified as **{regime.replace('_', '-')}**; "
        f"estimated Δσ_Orowan ≈ {orowan:.0f} MPa."
    )

    recs: list[dict] = []
    if regime == "under_aged" and analysis.get("peak_T_C_reference"):
        peak_T = analysis["peak_T_C_reference"]
        peak_t = analysis.get("peak_t_h_reference") or 8
        recs.append({
            "title":     "Move toward peak-age condition",
            "rationale": f"Canonical {alloy}: ~{peak_T} °C for {peak_t} h.",
            "executable": {"type": "set_temperature_C", "value": peak_T},
        })
    if regime == "over_aged":
        recs.append({
            "title":     "Reduce aging temperature",
            "rationale": "LSW coarsening (r̄ ∝ t^(1/3)) accelerates with T.",
            "executable": {"type": "info_only", "value": ""},
        })
    recs.append({
        "title":     "Cross-check equilibrium driving force",
        "rationale": "Equilibrium phase fractions set the upper bound for vf.",
        "executable": {"type": "scroll_to_card", "value": "phase"},
    })

    return {
        "interpretation":     " ".join(parts),
        "regime_call":        f"{regime}-{phase}",
        "recommendations":    recs[:3],
        "honest_limitations": [
            f"Numeric-only fallback (LLM unavailable): {reason}",
            "Single-precipitate mean-field — real PSD has finite width.",
            "γ and vacancy-enhancement are literature-fit; ±factor-of-2 on vf/r̄.",
        ] + (analysis.get("quality_warnings") or []),
        "source":             "deterministic_fallback",
        "calibration":        "numeric_only",
    }


async def interpret_precipitation(
    composition: dict[str, float] | None,
    kwn_result: dict[str, Any],
    analysis: dict[str, Any] | None = None,
    sim_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """LLM-narrate a KWN precipitation-kinetics result."""
    analysis = analysis or analyse_precipitation(kwn_result, composition)
    # Keep payload compact — strip the full trajectory arrays; the
    # Layer-1 diagnostics already capture the relevant slopes.
    payload = {
        "composition_wt_pct": composition,
        "analysis":           analysis,
        "kwn_value":          kwn_result.get("value"),
        "morphology":         kwn_result.get("morphology"),
        "phase":              kwn_result.get("phase"),
        "kwn_metadata":       {
            k: v for k, v in (sim_metadata or {}).items()
            if k in ("source", "calibration")
        },
    }
    return await call_interpretation_llm(
        system_prompt=SYSTEM_PROMPT,
        user_payload=payload,
        fallback_fn=lambda reason: _fallback(analysis, reason),
    )
