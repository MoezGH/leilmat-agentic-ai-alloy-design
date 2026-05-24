"""
apps.api.ml.calphad.interpret_scheil
=====================================

Layer-1 + Layer-2 interpretation of Scheil-Gulliver solidification.

Layer 1 (deterministic):
  - mushy-zone bucket (eutectic / narrow / medium / wide / very wide)
  - hot-tearing tendency from the published Clyne-Davies index
  - terminal-liquid segregation summary (which elements concentrate)
  - last-to-freeze phase identification
  - castability category (commercial mould / sand / die / risky)

Layer 2 (LLM):
  - narrative tying the freezing curve to alloy class
  - process-route recommendations (sand vs die vs investment)
  - cross-references to the equilibrium and precipitation cards
  - honest limitations (Scheil's infinite-liquid-diffusion assumption)
"""
from __future__ import annotations

from typing import Any

from apps.api.ml.interpret_common import call_interpretation_llm


# ─────────────────────────────────────────────────────────────────────
# Mushy-zone + hot-tearing classification
# ─────────────────────────────────────────────────────────────────────

def _mushy_bucket(width_K: float) -> str:
    """Bucket the mushy-zone width into castability-relevant categories."""
    if width_K < 10:
        return "eutectic"             # excellent for casting; A356, Al-Si
    if width_K < 40:
        return "narrow"               # good for most processes
    if width_K < 80:
        return "medium"               # standard cast alloys
    if width_K < 130:
        return "wide"                 # hot-tearing concern; needs care
    return "very_wide"                # high hot-tearing risk


def _hot_tearing_bucket(index: float | None) -> str:
    """Map Clyne-Davies HTI to a low/medium/high bucket.

    Threshold split is conservative — anything above 1.0 has historical
    correlation with cracking; below 0.7 is usually safe.
    """
    if index is None:
        return "unknown"
    if index < 30:
        return "low"
    if index < 70:
        return "medium"
    return "high"


def _terminal_segregation(terminal_liquid: dict[str, float] | None,
                          nominal: dict[str, float] | None) -> dict[str, Any]:
    """How much each solute concentrates in the last-to-freeze liquid.

    Returns the top-3 segregating elements by enrichment ratio
    (terminal-liquid mole-fraction / nominal mole-fraction).
    """
    if not terminal_liquid or not nominal:
        return {"top_segregants": []}
    # Convert nominal wt-% to rough mole fractions (atomic-mass weighting
    # is approximate; for relative ranking the result is order-correct).
    # Normalise element keys to title-case so we can match e.g. pycalphad's
    # all-uppercase "CU" against the nominal's "Cu".
    tot = sum(nominal.values())
    if tot <= 0:
        return {"top_segregants": []}
    nominal_frac = {el.title(): v / tot for el, v in nominal.items()}
    ratios = []
    for el, term_frac in terminal_liquid.items():
        nf = nominal_frac.get(el.title())
        if not nf or nf < 1e-4 or term_frac < 1e-4:
            continue
        ratios.append((el.title(), round(term_frac / nf, 1)))
    ratios.sort(key=lambda x: -x[1])
    return {"top_segregants": [
        {"element": el, "enrichment_ratio": r}
        for el, r in ratios[:3]
    ]}


def _last_phase(terminal_eutectic: dict[str, float] | None) -> str | None:
    """Identify the dominant phase in the last-to-freeze eutectic mixture."""
    if not terminal_eutectic:
        return None
    items = [(p, f) for p, f in terminal_eutectic.items() if f > 0.0001]
    if not items:
        return None
    items.sort(key=lambda x: -x[1])
    return items[0][0]


def analyse_solidification(
    scheil_result: dict[str, Any],
    composition: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Distill a Scheil-Gulliver result into a structured Layer-1 summary."""
    if not scheil_result or scheil_result.get("error"):
        return {
            "mushy_bucket":         "no_data",
            "hot_tearing_bucket":   "unknown",
            "castability_category": "unknown",
            "top_segregants":       [],
            "last_to_freeze_phase": None,
            "quality_warnings":     [scheil_result.get("error", "no scheil data")
                                     if scheil_result else "no input"],
            "source":               "scheil_solidification_analysis_v1",
            "calibration":          "deterministic",
        }

    mushy = float(scheil_result.get("mushy_zone_K") or 0)
    hti   = scheil_result.get("hot_tearing_index")
    term_liq = scheil_result.get("terminal_liquid")
    term_eut = scheil_result.get("terminal_eutectic")
    last_phase = _last_phase(term_eut)
    seg = _terminal_segregation(term_liq, composition)

    mushy_b = _mushy_bucket(mushy)
    htb     = _hot_tearing_bucket(hti)

    # Castability bucket combines mushy + HTI
    if mushy_b == "eutectic" and htb == "low":
        castability = "excellent_for_casting"
    elif mushy_b in ("narrow", "medium") and htb in ("low", "medium"):
        castability = "standard"
    elif mushy_b == "wide" or htb == "medium":
        castability = "needs_care"
    else:
        castability = "hot_tearing_risk"

    warnings: list[str] = []
    if hti is not None and hti > 100:
        warnings.append(
            f"hot-tearing index {hti:.0f} is very high — risk of "
            "centerline cracking in unrestrained castings"
        )
    if mushy > 150:
        warnings.append(
            f"mushy-zone width {mushy:.0f} K is exceptionally wide — "
            "consider this alloy primarily for wrought processing"
        )

    return {
        "liquidus_K":            scheil_result.get("liquidus_K"),
        "solidus_K":             scheil_result.get("solidus_K"),
        "mushy_zone_K":          round(mushy, 1),
        "mushy_bucket":          mushy_b,
        "hot_tearing_index":     hti,
        "hot_tearing_bucket":    htb,
        "castability_category":  castability,
        "last_to_freeze_phase":  last_phase,
        "top_segregants":        seg["top_segregants"],
        "quality_warnings":      warnings,
        "source":                "scheil_solidification_analysis_v1",
        "calibration":           "deterministic",
    }


# ─────────────────────────────────────────────────────────────────────
# Layer 2 — LLM interpretation
# ─────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a senior foundry engineer reviewing a Scheil-Gulliver solidification
calculation.  The user is exploring a real engineering composition.

Output strict JSON matching this schema:
  {
    "interpretation":     <string, 3-5 sentences>,
    "regime_call":        <string, short label like "narrow-mushy A356-like alloy">,
    "recommendations": [  # 2-3 items
      {
        "title":     <string, imperative, ≤ 8 words>,
        "rationale": <string, one sentence>,
        "executable": {                                    # optional
          "type":    "scroll_to_card" | "info_only",
          "value":   <card name "phase" / "precipitation" / "cost" or "">
        }
      }
    ],
    "honest_limitations": [<2-4 bullet strings>]
  }

Style constraints:
* Anchor every number in the supplied analysis; do not invent values.
* Name the cast-process suitability ("excellent for high-pressure die-cast",
  "needs unrestrained shrinkage paths", "use riser-fed sand mould", etc.).
* If hot_tearing_bucket=high, explicitly recommend either composition
  adjustment (drop a heavy segregant) or process route (e.g. graphite mould,
  vacuum-arc remelt) — be SPECIFIC.
* If mushy_bucket=eutectic, mention that this is the canonical Al-Si A356
  / A380 regime — excellent fluidity, suitable for thin-wall casts.
* Limitations MUST include: Scheil assumes zero solid diffusion + infinite
  liquid diffusion (real metals fall between Scheil and lever), and that
  hot-tearing index is correlational not mechanistic.
* No filler; no markdown; no chatty intro/outro.  Pure JSON only.
"""


def _fallback(analysis: dict[str, Any], reason: str) -> dict[str, Any]:
    """Deterministic numeric-only interpretation when the LLM is down."""
    mushy = analysis.get("mushy_zone_K") or 0
    mb = analysis.get("mushy_bucket", "unknown")
    htb = analysis.get("hot_tearing_bucket", "unknown")
    cast = analysis.get("castability_category", "unknown")

    parts = [
        f"Mushy-zone width {mushy:.0f} K ({mb}); hot-tearing risk "
        f"{htb}; overall castability {cast}."
    ]
    segs = analysis.get("top_segregants") or []
    if segs:
        seg_str = ", ".join(f"{s['element']} ×{s['enrichment_ratio']:.1f}"
                            for s in segs[:3])
        parts.append(f"Last-to-freeze liquid enriched in: {seg_str}.")
    last_phase = analysis.get("last_to_freeze_phase")
    if last_phase:
        parts.append(f"Terminal eutectic dominated by {last_phase}.")

    recs: list[dict] = []
    if mb in ("wide", "very_wide") or htb == "high":
        recs.append({
            "title":     "Reduce a heavy segregant",
            "rationale": "Wide mushy zone or high HTI suggests one solute is the culprit.",
            "executable": {"type": "info_only", "value": ""},
        })
    if mb == "eutectic":
        recs.append({
            "title":     "Use for thin-wall casting",
            "rationale": "Eutectic alloys have excellent fluidity for high-pressure die-cast.",
            "executable": {"type": "info_only", "value": ""},
        })
    recs.append({
        "title":     "Cross-check with equilibrium phases",
        "rationale": "Scheil is non-equilibrium; compare with the CALPHAD card.",
        "executable": {"type": "scroll_to_card", "value": "phase"},
    })

    return {
        "interpretation":     " ".join(parts),
        "regime_call":        f"{mb} mushy, {htb} hot-tearing",
        "recommendations":    recs[:3],
        "honest_limitations": [
            f"Numeric-only fallback (LLM unavailable): {reason}",
            "Scheil assumes zero solid diffusion + infinite liquid diffusion.",
            "Hot-tearing index is correlational; real cracking also depends on mould geometry.",
        ] + (analysis.get("quality_warnings") or []),
        "source":             "deterministic_fallback",
        "calibration":        "numeric_only",
    }


async def interpret_solidification(
    composition: dict[str, float] | None,
    scheil_result: dict[str, Any],
    analysis: dict[str, Any] | None = None,
    sim_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """LLM-narrate a Scheil-Gulliver solidification result."""
    analysis = analysis or analyse_solidification(scheil_result, composition)
    # Keep the LLM payload compact — the freezing curve has 30 points but
    # the LLM doesn't need them all.  Send liquidus, solidus, mushy width,
    # and a 5-point downsample.
    fs_curve = scheil_result.get("fraction_solid_curve") or []
    sparse = fs_curve[::max(1, len(fs_curve) // 5)] if fs_curve else []

    payload = {
        "composition_wt_pct":  composition,
        "analysis":            analysis,
        "fraction_solid_curve_sparse": sparse,
        "terminal_liquid":     scheil_result.get("terminal_liquid"),
        "terminal_eutectic":   scheil_result.get("terminal_eutectic"),
        "metadata":            {
            k: v for k, v in (sim_metadata or {}).items()
            if k in ("tdb", "chemsys", "source")
        },
    }
    return await call_interpretation_llm(
        system_prompt=SYSTEM_PROMPT,
        user_payload=payload,
        fallback_fn=lambda reason: _fallback(analysis, reason),
        endpoint_label="scheil_interpret",
    )
