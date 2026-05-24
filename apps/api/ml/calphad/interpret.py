"""
apps.api.ml.calphad.interpret
==============================

Layer-1 + Layer-2 interpretation of CALPHAD phase-assemblage results.

Layer 1 (deterministic):
  - dominant matrix phase + fraction
  - secondary phase list with fractions
  - regime classification (single-phase / dual-phase / multi-phase)
  - unwanted-phase flags (σ, χ, brittle intermetallics)
  - matrix purity (how much solute partitions into the matrix vs precipitates)

Layer 2 (LLM):
  - 3-5 sentence narrative tying composition + T to the assemblage
  - 2-3 actionable recommendations (set_T, scroll_to_precipitation, etc.)
  - honest_limitations (TDB scope, equilibrium-only caveat, etc.)
"""
from __future__ import annotations

from typing import Any

from apps.api.ml.interpret_common import call_interpretation_llm


# ─────────────────────────────────────────────────────────────────────
# Known "unwanted" phases (brittle / corrosion-bad / hot-tearing) per family
# ─────────────────────────────────────────────────────────────────────

UNWANTED_PHASES = {
    # Stainless / Ni-base: σ-phase is the canonical embrittler
    "SIGMA":        "σ-phase: brittle Fe-Cr-Mo intermetallic; embrittles stainless above ~600 °C.",
    "SIGMA_FECR":   "σ-phase: brittle Fe-Cr intermetallic.",
    "CHI":          "χ-phase: brittle, related to σ but with more Mo/Ni.",
    "LAVES":        "Laves phase: brittle topologically-close-packed phase; common in over-aged Ni-superalloys.",
    "MU":           "μ-phase: TCP phase, embrittles Ni-superalloys at long service times.",
    "ETA_NI3TI":    "η-Ni3Ti: cellular precipitation, displaces strengthening γ'.",
    # Al-alloys
    "AL3FE":        "Al3Fe: coarse Fe-rich constituent; reduces ductility.",
    "AL13FE4":      "Al13Fe4: Fe-rich constituent; problematic for fatigue.",
    "AL7CU2FE":     "α-Al7Cu2Fe: detrimental for 2xxx-series fatigue performance.",
}


def _classify_regime(phase_fractions: dict[str, float]) -> str:
    """Bucket the assemblage by phase count + balance."""
    if not phase_fractions:
        return "no_phases_returned"
    sig = {p: f for p, f in phase_fractions.items() if f > 0.01}
    n = len(sig)
    if n == 0:
        return "trace_only"
    if n == 1:
        return "single_phase"
    # Dominant phase carries > 90 %?
    dominant_frac = max(sig.values())
    if dominant_frac >= 0.90:
        return "matrix_with_minor_precipitates"
    if n == 2:
        return "dual_phase"
    return "multi_phase"


def _unwanted_flags(phase_fractions: dict[str, float]) -> list[dict[str, Any]]:
    """Spot detrimental phases above 0.001 mole fraction."""
    flags: list[dict[str, Any]] = []
    for phase, fraction in phase_fractions.items():
        if fraction < 0.001:
            continue
        # Loose key-match — TDB phase names vary in casing and suffixes
        upper = phase.upper().replace("-", "_")
        for needle, msg in UNWANTED_PHASES.items():
            if needle in upper:
                flags.append({
                    "phase":     phase,
                    "fraction":  round(float(fraction), 5),
                    "concern":   msg,
                })
                break
    return flags


def analyse_phase_assemblage(
    phases: dict[str, float],
    T_K: float | None = None,
    composition: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Distill a pycalphad equilibrium result into a structured summary."""
    if not phases:
        return {
            "regime":              "no_data",
            "dominant_phase":      None,
            "dominant_fraction":   0.0,
            "secondary_phases":    [],
            "unwanted_flags":      [],
            "n_phases_significant": 0,
            "quality_warnings":    ["no phase fractions returned by pycalphad"],
            "source":              "phase_assemblage_analysis_v1",
            "calibration":         "deterministic",
        }

    sig = {p: float(f) for p, f in phases.items() if f > 0.001}
    sorted_phases = sorted(sig.items(), key=lambda kv: -kv[1])
    dominant_phase, dominant_fraction = sorted_phases[0] if sorted_phases else (None, 0.0)
    secondary = [
        {"phase": p, "fraction": round(f, 5)}
        for p, f in sorted_phases[1:5]   # cap at top-4 secondary
    ]
    regime = _classify_regime(phases)
    flags = _unwanted_flags(phases)

    warnings: list[str] = []
    if regime == "trace_only":
        warnings.append("all phases below 1 mole-% — convergence may be unreliable")
    if T_K is not None and (T_K < 200 or T_K > 3000):
        warnings.append(f"T={T_K:.0f} K is outside the typical pycalphad calibration range")
    if flags:
        warnings.append(
            f"detected {len(flags)} detrimental phase(s) above 0.1 % — "
            "see unwanted_flags"
        )

    return {
        "regime":               regime,
        "dominant_phase":       dominant_phase,
        "dominant_fraction":    round(dominant_fraction, 4),
        "secondary_phases":     secondary,
        "unwanted_flags":       flags,
        "n_phases_significant": len(sig),
        "T_K":                  T_K,
        "T_C":                  None if T_K is None else round(T_K - 273.15, 1),
        "quality_warnings":     warnings,
        "source":               "phase_assemblage_analysis_v1",
        "calibration":          "deterministic",
    }


# ─────────────────────────────────────────────────────────────────────
# Layer 2 — LLM interpretation
# ─────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a senior alloy designer reviewing a CALPHAD equilibrium calculation
from pycalphad.  The user is exploring a real engineering composition at a
specific temperature.

Output strict JSON matching this schema:
  {
    "interpretation":     <string, 3-5 sentences>,
    "regime_call":        <string, short label like "α-Al matrix with β″ precipitate seeds">,
    "recommendations": [  # 2-3 items
      {
        "title":     <string, imperative, ≤ 8 words>,
        "rationale": <string, one sentence>,
        "executable": {                                    # optional
          "type":    "set_temperature_C" | "scroll_to_card" | "info_only",
          "value":   <number for temperature / card name for scroll / "" for info>
        }
      }
    ],
    "honest_limitations": [<2-4 bullet strings>]
  }

Constraints on style:
* Anchor every claim in the supplied phases dict; do not invent fractions.
* Name phases by their CALPHAD database key (FCC_A1, MG2SI, etc.) AND in
  metallurgical English ("α-Al matrix", "β″ Mg₂Si precipitate seeds").
* If unwanted_flags is non-empty, prominently call out the brittle/
  deleterious phase, what it does, and which T range avoids it.
* If single-phase: discuss solid-solution strengthening, dislocation
  density potential, suitability for cold work, etc.
* If multi-phase: identify the matrix vs the strengthening / brittle
  precipitates; mention CALPHAD couples to KWN for kinetic prediction
  (route the user to the Precipitation card when sensible).
* "set_temperature_C" recommendations should be concrete numbers in the
  CALPHAD-database-supported range (typically 300-3000 K).
* Limitations MUST include: equilibrium-only (no kinetics), TDB-coverage
  caveat, and that real-temper microstructure depends on cooling rate.
* No filler; no markdown; no chatty intro/outro.  Just the JSON.
"""


def _fallback(analysis: dict[str, Any], composition: dict | None,
              T_K: float | None, reason: str) -> dict[str, Any]:
    """Deterministic numeric-only interpretation when the LLM is down."""
    regime = analysis.get("regime", "unknown")
    dom = analysis.get("dominant_phase")
    dom_f = analysis.get("dominant_fraction", 0)
    secondaries = analysis.get("secondary_phases", []) or []
    flags = analysis.get("unwanted_flags", []) or []

    parts = [
        f"{regime.replace('_', ' ')}: "
        f"{dom} dominates at {dom_f:.2%} mole fraction."
    ]
    if secondaries:
        sec_str = ", ".join(f"{s['phase']} ({s['fraction']:.2%})"
                            for s in secondaries[:3])
        parts.append(f"Secondary phases: {sec_str}.")
    if flags:
        parts.append(
            f"⚠ {len(flags)} detrimental phase(s) detected: "
            + "; ".join(f["phase"] for f in flags)
        )

    recs: list[dict] = []
    if flags:
        recs.append({
            "title":     "Find a T window without the brittle phase",
            "rationale": (f"{flags[0]['phase']} should suppress above/below "
                          "a critical T — sweep the temperature."),
            "executable": {"type": "info_only", "value": ""},
        })
    if regime == "matrix_with_minor_precipitates":
        recs.append({
            "title":     "Run KWN kinetics on the strengthening phase",
            "rationale": ("Equilibrium tells you what *could* form; KWN "
                          "tells you when and how big."),
            "executable": {"type": "scroll_to_card", "value": "precipitation"},
        })

    return {
        "interpretation":     " ".join(parts),
        "regime_call":        regime,
        "recommendations":    recs[:3],
        "honest_limitations": [
            f"Numeric-only fallback (LLM unavailable): {reason}",
            "Equilibrium calculation only — no nucleation/growth kinetics.",
            "TDB coverage is limited; check phases against your alloy family.",
        ] + (analysis.get("quality_warnings") or []),
        "source":             "deterministic_fallback",
        "calibration":        "numeric_only",
    }


async def interpret_phase_assemblage(
    composition: dict[str, float] | None,
    T_K: float | None,
    phases: dict[str, float],
    analysis: dict[str, Any] | None = None,
    sim_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """LLM-narrate a CALPHAD equilibrium calculation."""
    analysis = analysis or analyse_phase_assemblage(phases, T_K, composition)
    payload = {
        "composition_wt_pct": composition,
        "T_K":                T_K,
        "T_C":                None if T_K is None else round(T_K - 273.15, 1),
        "analysis":           analysis,
        "phases":             {p: round(float(f), 5) for p, f in phases.items() if f > 0.0005},
        "metadata":           {
            k: v for k, v in (sim_metadata or {}).items()
            if k in ("tdb", "chemsys", "source", "calibration")
        },
    }
    return await call_interpretation_llm(
        system_prompt=SYSTEM_PROMPT,
        user_payload=payload,
        fallback_fn=lambda reason: _fallback(analysis, composition, T_K, reason),
    )
