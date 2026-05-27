"""
Optional LLM-generated executive summary for the PDF report's cover page.

A single non-streaming chat-completion call to OpenRouter that ingests
the design payload (alloy name + composition + properties + goals +
temper) and emits a tight 2-paragraph synthesis a working metallurgist
would expect to find at the top of a design-review packet.

Failure modes (network, budget exhaustion, OpenRouter 5xx, missing
key) all return ``None`` silently — the PDF builder treats absence
as "no exec-summary section."  This keeps the report-export endpoint
robust: even on a totally cold cluster with no LLM credits available,
``POST /api/report/generate`` still returns a clean multi-page PDF.

Budget accounting hooks into the same ``DailyBudget`` that gates
``/api/chat/*`` so the executive summary lives under the same daily
$5 cap.  Cost per call is typically ~$0.002 (DeepSeek V4 Pro, ~300
prompt tokens, ~200 completion tokens).
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import openai

from apps.api.config       import settings
from apps.api.ml.llm_budget import BUDGET


logger = logging.getLogger(__name__)


# Tight system prompt — what we want the LLM to write.  Constrained to
# 2 short paragraphs because the cover page has finite vertical space
# and the rest of the report carries the detailed numbers.
_SYSTEM = """You are summarising an alloy-design session for the cover page of
an audit-grade PDF report.

Given the composition, properties, goals, and temper, write a TIGHT
2-paragraph executive summary of AT MOST 120 words total that:

  * Names the alloy or its closest commercial designation if you
    recognise it (e.g. "near 6061-T6", "Scalmalloy-class").
  * States the top 2–3 properties + their values in one sentence each.
  * Calls out the headline trade-off the designer made (e.g.
    "trading 30 MPa of yield for −0.05 g/cm³ density").
  * Closes with the SINGLE most actionable next step a working
    metallurgist would do before casting trial (e.g. "validate Mg
    limit against AMS 4214 prior to LPBF parameter sweep").

Rules:
  * 2 paragraphs only.  No bullet lists.  No markdown.  No headers.
  * Plain prose; this is read on a printed page.
  * Be specific with numbers.  Avoid hedge words like "promising" or
    "interesting" — name the trade-off.
  * Do NOT invent properties that aren't in the payload.  If you can
    only see 1 property, write 1 sentence about it and move on."""


async def generate_executive_summary(payload: dict[str, Any]) -> str | None:
    """Call the LLM with the payload's design context and return the
    summary text.  Returns ``None`` on any failure (no exception
    surfaces past this boundary)."""

    # Soft-fail #1: no LLM key configured.
    if not settings.openrouter_api_key:
        return None

    # Soft-fail #2: today's budget exhausted.  Same cap as the chat
    # endpoints — the executive summary is opt-in cost, not load-bearing.
    if not BUDGET.can_spend():
        logger.info("[exec_summary] daily budget exhausted; skipping")
        return None

    # Build a compact context — strip noisy / oversized fields before
    # the LLM sees them (the full provenance lives in the PDF body
    # anyway, the summary just needs the design intent).
    ctx = {
        "alloy_name":   payload.get("alloy_name"),
        "composition":  payload.get("composition") or {},
        "temper":       payload.get("temper"),
        "goals":        payload.get("goals") or {},
        "constraints":  payload.get("constraints") or {},
    }
    # Distill properties down to {name: float} — the LLM doesn't need
    # the structured provenance dicts.
    props = payload.get("properties") or {}
    flat: dict[str, float] = {}
    for k, v in props.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            flat[k] = float(v)
        elif isinstance(v, dict) and isinstance(v.get("value"), (int, float)):
            flat[k] = float(v["value"])
    ctx["properties"] = flat

    client = openai.AsyncOpenAI(
        api_key  = settings.openrouter_api_key,
        base_url = settings.openrouter_base_url,
    )

    t0 = time.perf_counter()
    try:
        resp = await client.chat.completions.create(
            model       = settings.llm_model,
            max_tokens  = 320,
            messages    = [
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": json.dumps(ctx, indent=2)},
            ],
            # DeepSeek V4 Pro is a reasoning model — disable reasoning
            # tokens so all output lands in `content` rather than
            # being lost to the reasoning channel.
            extra_body     = {"reasoning": {"exclude": True}},
            # Ask OpenRouter to attach usage info so we can charge
            # the daily budget consistently with the rest of the LLM
            # surface.
            stream_options = {"include_usage": True},
            timeout        = 30,
        )
    except Exception as exc:                                          # noqa: BLE001
        logger.warning("[exec_summary] LLM call failed: %s", exc)
        return None

    # Charge the budget post-call.  The OpenAI client's non-streaming
    # path puts usage on the response object directly.
    usage = getattr(resp, "usage", None)
    cost_reported = getattr(usage, "cost", None) if usage else None
    prompt_tokens     = int(getattr(usage, "prompt_tokens",     0) or 0) if usage else 0
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0
    BUDGET.charge(
        endpoint           = "report_exec_summary",
        cost_usd           = cost_reported,
        prompt_tokens      = prompt_tokens,
        completion_tokens  = completion_tokens,
        model              = settings.llm_model,
    )
    elapsed_s = time.perf_counter() - t0
    logger.info(
        "[llm_cost] endpoint=report_exec_summary model=%s prompt=%d "
        "completion=%d cost_usd=%s elapsed_s=%.2f",
        settings.llm_model, prompt_tokens, completion_tokens,
        f"{cost_reported:.6f}" if cost_reported is not None else "missing",
        elapsed_s,
    )

    text = (resp.choices[0].message.content or "").strip()
    return text if text else None
