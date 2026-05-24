"""
apps.api.ml.microstructure.interpret_llm
========================================

Layer 2 of the dendrite interpretation stack — turn Layer-1 numeric
measurements into a metallurgist-readable narrative plus 2-3 actionable
recommendations.

Why a separate module?  Keeps the prompt + JSON-schema work cleanly
isolated from both the image analysis (Layer 1) and the FastAPI router
plumbing.  The router just orchestrates: call Layer 1 → call this
module → return the merged payload.

Output schema
-------------
The LLM is constrained (via ``response_format=json_object`` plus a
strict prompt) to return:

    {
        "interpretation":       "<3-5 sentence summary tying composition to morphology>",
        "regime_call":          "<short label, e.g. 'fully developed FCC dendrite'>",
        "recommendations": [
            {
                "title":      "<imperative, ≤ 8 words>",
                "rationale":  "<one sentence why>",
                "executable": {                        # OPTIONAL
                    "type":  "set_undercooling_factor" | "set_crystal_symmetry"
                           | "set_fidelity"          | "scroll_to_card"
                           | "set_temperature_C"     | "info_only",
                    "value": <number | string>
                }
            },
            ...                                       # 2-3 entries
        ],
        "honest_limitations":   ["<bullet>", ...]
    }
"""
from __future__ import annotations

import json
import logging
from typing import Any

import openai

from apps.api.config import settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """\
You are a senior solidification metallurgist reviewing a 2D pure-substance
Kobayashi-Warren-Carter phase-field simulation.  The user has run the simulation
on a real engineering composition and is asking what it tells them.

Output strict JSON matching this schema:
  {
    "interpretation":     <string, 3-5 sentences>,
    "regime_call":        <string, short label like "fully developed FCC dendrite">,
    "recommendations": [  # 2-3 items
      {
        "title":     <string, imperative, ≤ 8 words>,
        "rationale": <string, one sentence>,
        "executable": {                               # optional
          "type":    "set_undercooling_factor" | "set_crystal_symmetry"
                   | "set_fidelity"          | "scroll_to_card"
                   | "set_temperature_C"     | "info_only",
          "value":   <number for set_* / fidelity string for set_fidelity
                       / card name for scroll_to_card / "" for info_only>
        }
      }
    ],
    "honest_limitations": [<2-4 bullet strings>]
  }

Constraints on style:
* Anchor every claim in the supplied measurements; do not invent numbers.
* Stay metallurgically rigorous — name regimes (planar / cellular /
  dendritic / equiaxed), invoke Mullins-Sekerka, Trivedi-Kurz, and the
  selection parameter σ* by name when relevant.
* Recommendations should be ACTIONABLE — either change a knob in this
  simulator (set_undercooling_factor, set_crystal_symmetry, set_fidelity)
  or point the user at another card (scroll_to_card: "solidification",
  "precipitation", "phase", or "cost").
* If the analysis flags boundary_touching = true, MUST mention it as a
  limitation and recommend a higher-fidelity rerun.
* If the composition is multi-component (e.g. Al-Mg-Si), explicitly
  note that the KWC simulator is single-substance and the real alloy's
  solute partitioning would sharpen tips / change λ₂.
* No filler; no emoji; no markdown; no chatty intro/outro.  Just the JSON.
"""


def _build_user_message(
    composition: dict[str, float] | None,
    temper: str | None,
    T_C: float | None,
    analysis: dict[str, Any],
    sim_metadata: dict[str, Any] | None,
) -> str:
    """Compose the user-side prompt embedding the Layer-1 numbers."""
    parts = ["Simulation results:", json.dumps({
        "composition_wt_pct":   composition,
        "temper":               temper,
        "temperature_C":        T_C,
        "analysis":             analysis,
        "simulation_metadata":  {
            k: v for k, v in (sim_metadata or {}).items()
            if k in ("grid", "n_steps_run", "elapsed_s",
                     "steps_per_s", "final_solid_fraction",
                     "params", "source", "calibration")
        },
    }, indent=2, default=str)]
    parts.append(
        "\nPlease return the JSON interpretation now.  Anchor every claim in "
        "the numbers above; mention any quality_warnings explicitly."
    )
    return "\n\n".join(parts)


def _validate_payload(raw: dict) -> dict:
    """Soft validation — coerce missing keys to safe defaults rather than
    rejecting outright.  Layer-2 output is meant to be best-effort."""
    out = {
        "interpretation":     str(raw.get("interpretation", "")).strip(),
        "regime_call":        str(raw.get("regime_call", "")).strip(),
        "recommendations":    [],
        "honest_limitations": [],
    }
    recs = raw.get("recommendations") or []
    if isinstance(recs, list):
        for r in recs[:5]:
            if not isinstance(r, dict):
                continue
            entry = {
                "title":     str(r.get("title", "")).strip(),
                "rationale": str(r.get("rationale", "")).strip(),
            }
            if not entry["title"] or not entry["rationale"]:
                continue
            ex = r.get("executable")
            if isinstance(ex, dict) and "type" in ex:
                entry["executable"] = {
                    "type":  str(ex["type"]),
                    "value": ex.get("value"),
                }
            out["recommendations"].append(entry)
    lims = raw.get("honest_limitations") or []
    if isinstance(lims, list):
        out["honest_limitations"] = [str(x) for x in lims if str(x).strip()]
    return out


async def interpret_dendrite(
    composition: dict[str, float] | None,
    temper: str | None,
    T_C: float | None,
    analysis: dict[str, Any],
    sim_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """Call the LLM, parse JSON, return a structured interpretation dict.

    On any failure (no API key, LLM timeout, bad JSON), returns a fallback
    interpretation built from the Layer-1 numbers alone so the UI stays
    usable.  ``source`` field distinguishes the two paths.
    """
    if not settings.openrouter_api_key:
        logger.warning("OPENROUTER_API_KEY not set — returning numeric-only fallback")
        return _fallback(analysis, "no_api_key")

    user_msg = _build_user_message(composition, temper, T_C, analysis, sim_metadata)

    try:
        client = openai.AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
        resp = await client.chat.completions.create(
            model=settings.llm_model,
            max_tokens=900,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            response_format={"type": "json_object"},
            # DeepSeek V4 Pro is a reasoning model — disable reasoning so
            # all output goes to .content (matching the chat router).
            extra_body={"reasoning": {"exclude": True}},
            timeout=20.0,
        )
        text = resp.choices[0].message.content or ""
    except Exception as exc:
        logger.exception("LLM interpretation call failed")
        return _fallback(analysis, f"llm_error: {type(exc).__name__}")

    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON; first 200 chars: %s", text[:200])
        return _fallback(analysis, "non_json_response")

    payload = _validate_payload(raw)
    payload["source"]      = "llm_interpretation_deepseek"
    payload["calibration"] = "narrative"
    return payload


# ─────────────────────────────────────────────────────────────────────
# Fallback when the LLM path is unavailable
# ─────────────────────────────────────────────────────────────────────

def _fallback(analysis: dict[str, Any], reason: str) -> dict[str, Any]:
    """Synthesize a minimal interpretation from Layer-1 numbers only.

    Keeps the UI useful when the LLM is down or unconfigured; clearly
    labels itself as ``source: deterministic_fallback``.
    """
    regime  = analysis.get("regime", "unknown")
    n_arms  = analysis.get("n_arms_detected", 0)
    n_exp   = analysis.get("n_arms_expected", 0)
    amp     = analysis.get("side_branch_amplitude", "none")
    bound   = analysis.get("boundary_touching", False)
    sf      = analysis.get("solid_fraction_final", 0)
    warns   = analysis.get("quality_warnings", []) or []

    parts = [
        f"Detected {n_arms} arms (expected {n_exp} from anisotropy order); "
        f"regime classified as **{regime}** with **{amp}** side-branching "
        f"at solid fraction {sf:.2f}."
    ]
    if bound:
        parts.append(
            "The solidification front has reached the simulation box "
            "boundary — re-run at a higher fidelity (larger grid) for a "
            "morphologically uncontaminated final state."
        )

    recs: list[dict] = []
    if bound:
        recs.append({
            "title":     "Rerun at higher fidelity",
            "rationale": "Boundary impingement is biasing the final morphology.",
            "executable": {"type": "set_fidelity", "value": "publication"},
        })
    if regime == "spherical" or amp == "none":
        recs.append({
            "title":     "Increase undercooling to develop arms",
            "rationale": "At this driving force the front stays stable; "
                         "stronger ΔT will trigger Mullins-Sekerka.",
            "executable": {"type": "set_undercooling_factor", "value": 1.5},
        })
    if regime in ("dendritic", "early dendritic"):
        recs.append({
            "title":     "Compare castability via Scheil",
            "rationale": "Heavy side-branching at low undercooling correlates "
                         "with mushy-zone hot-tearing risk.",
            "executable": {"type": "scroll_to_card", "value": "solidification"},
        })

    return {
        "interpretation":     " ".join(parts),
        "regime_call":        regime,
        "recommendations":    recs[:3],
        "honest_limitations": [
            "Numeric-only fallback (LLM unavailable): " + reason,
            "2D pure-substance KWC; real multi-component partitioning not modelled.",
        ] + warns,
        "source":             "deterministic_fallback",
        "calibration":        "numeric_only",
    }
