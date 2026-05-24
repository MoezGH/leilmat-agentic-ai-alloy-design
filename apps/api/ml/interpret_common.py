"""
apps.api.ml.interpret_common
=============================

Shared plumbing for Layer-2 LLM interpretation across all sprint domains
(microstructure dendrite, CALPHAD equilibrium, Scheil solidification,
KWN precipitation, …).

Each domain supplies:
* ``system_prompt`` — describes the schema the LLM must return
* ``user_payload``  — dict of measurements + provenance to embed
* ``fallback_fn``   — deterministic alternative when the LLM is down

This module handles the parts that don't change between domains:
* OpenRouter/DeepSeek client setup
* strict-JSON ``response_format``
* ``reasoning.exclude`` flag for the DeepSeek V4 Pro path
* request timeout + exception handling
* common output envelope: ``{interpretation, regime_call,
  recommendations, honest_limitations, source, calibration}``
* shape-tolerant validation that coerces missing keys to safe defaults
  rather than rejecting partial responses

Usage
-----
    from apps.api.ml.interpret_common import call_interpretation_llm

    SYSTEM_PROMPT = "..."

    async def interpret_my_domain(payload, fallback_fn):
        return await call_interpretation_llm(
            system_prompt=SYSTEM_PROMPT,
            user_payload=payload,
            fallback_fn=fallback_fn,
        )
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Awaitable, Callable

import openai

from apps.api.config import settings
from apps.api.ml.llm_budget import BUDGET

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Common output envelope
# ─────────────────────────────────────────────────────────────────────

def _validate_payload(raw: dict) -> dict:
    """Shape-tolerant validation: coerce missing/bad keys to safe defaults.

    Layer-2 output is meant to be best-effort.  A partially-malformed
    LLM response should still produce something usable for the UI,
    rather than crashing the request.
    """
    out: dict[str, Any] = {
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


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

async def _maybe_deduct_credits(
    endpoint: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """Phase D: POST /v1/billing/credits/deduct to LeilAI-5.

    Behaviour matrix matches apps/api/middleware/credits.py:
      * LEIL_AGENT_URL unset      → silent no-op
      * LEIL_SERVICE_TOKEN unset  → logged-only no-op (Phase 0a not live)
      * both set                  → real deduction (fire-and-forget; we
        do not block the response on the billing-service round-trip)

    No JWT forwarding here — by the time we reach interpret_common we
    no longer have the request scope.  The billing API trusts the
    sub-app identified by X-Leil-Service-Token; per-user attribution
    will be added when auth-aware request-state plumbing lands.
    TODO(post-auth): forward Authorization: Bearer <user-jwt> through
    so LeilAI-5 can debit the correct wallet.
    """
    agent_url = (settings.leil_agent_url or "").rstrip("/")
    token     = settings.leil_service_token

    if not agent_url:
        return
    if not token:
        logger.warning(
            "[credits] LEIL_SERVICE_TOKEN unset; deduct for %s is a "
            "no-op (Phase 0a not deployed)", endpoint,
        )
        return

    # Lazy import — keeps the OpenAI-only test paths fast.
    import httpx
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(
                f"{agent_url}/v1/billing/credits/deduct",
                headers={"X-Leil-Service-Token": token},
                json={
                    "source_app":         "leilmat",
                    "endpoint":           endpoint,
                    "model":              settings.llm_model,
                    "prompt_tokens":      prompt_tokens,
                    "completion_tokens":  completion_tokens,
                },
            )
    except Exception as exc:
        # Never block the user's response on billing-call failure;
        # the local DailyBudget still capped spend.
        logger.warning("[credits] deduct failed for %s: %s", endpoint, exc)


async def call_interpretation_llm(
    system_prompt: str,
    user_payload: dict[str, Any],
    fallback_fn: Callable[[str], dict[str, Any]],
    max_tokens: int = 2400,
    timeout_s: float = 30.0,
    endpoint_label: str = "interpret",
) -> dict[str, Any]:
    """Run an interpretation LLM call with strict JSON response.

    Parameters
    ----------
    system_prompt
        Domain-specific system message describing the schema and style.
    user_payload
        Domain-specific measurements / provenance to be JSON-serialised
        and sent as the user message.  Caller is responsible for keeping
        this payload reasonably-sized (< 4 KB) — the LLM ignores deeply-
        nested objects anyway.
    fallback_fn
        Synchronous function ``(reason: str) -> dict`` that produces a
        deterministic interpretation when the LLM is unavailable.  The
        returned dict must already match the standard envelope shape;
        this module will pass it through unchanged.
    max_tokens
        Output budget.  Defaults to 2400 because DeepSeek V4 Pro is a
        reasoning model — even with ``reasoning.exclude=True`` (which
        only suppresses the reasoning *output*, not its token cost), a
        typical interpretation burns 800-1500 reasoning tokens before
        emitting any content.  At 900 max_tokens the JSON gets
        truncated mid-stream and the parser fires the fallback.
    timeout_s
        Hard timeout for the LLM call.  Beyond this we cut over to the
        fallback.

    Returns
    -------
    dict
        ``{interpretation, regime_call, recommendations, honest_limitations,
           source, calibration}``.  ``source`` distinguishes the path:
        ``llm_interpretation_deepseek`` or ``deterministic_fallback``.
    """
    if not settings.openrouter_api_key:
        logger.warning("OPENROUTER_API_KEY not set — using fallback")
        return fallback_fn("no_api_key")

    # Daily-budget gate — once we've exceeded settings.llm_daily_budget_usd
    # the fallback path serves the deterministic interpretation instead.
    # Resets at UTC midnight.
    if not BUDGET.can_spend():
        status = BUDGET.status()
        logger.warning(
            "[llm_budget] daily cap reached: spent $%.4f / $%.4f over %d calls",
            status["spent_usd"], status["cap_usd"], status["total_calls"],
        )
        return fallback_fn("daily_budget_exhausted")

    user_message = (
        json.dumps(user_payload, indent=2, default=str)
        + "\n\nReturn the JSON interpretation now.  Anchor every claim "
          "in the numbers above; mention any warnings explicitly."
    )

    t0 = time.perf_counter()
    try:
        client = openai.AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
        resp = await client.chat.completions.create(
            model=settings.llm_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            response_format={"type": "json_object"},
            # DeepSeek V4 Pro: redirect reasoning tokens away from .content
            extra_body={"reasoning": {"exclude": True}},
            timeout=timeout_s,
        )
        text = resp.choices[0].message.content or ""
    except Exception as exc:
        logger.exception("interpretation LLM call failed")
        return fallback_fn(f"llm_error: {type(exc).__name__}")

    elapsed_s = time.perf_counter() - t0

    # Charge the daily budget + emit structured cost log.  The OpenRouter
    # response carries the cost in .usage.cost when available; we fall
    # back to a token-rate estimate otherwise.
    usage = getattr(resp, "usage", None)
    cost_reported = getattr(usage, "cost", None) if usage else None
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    cost_charged = BUDGET.charge(
        endpoint=endpoint_label,
        cost_usd=cost_reported,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model=settings.llm_model,
    )
    logger.info(
        "[llm_cost] endpoint=%s model=%s prompt=%d completion=%d "
        "cost_usd=%.4f reported=%s elapsed_s=%.2f",
        endpoint_label, settings.llm_model,
        prompt_tokens, completion_tokens,
        cost_charged,
        f"{cost_reported:.6f}" if cost_reported is not None else "missing",
        elapsed_s,
    )

    # Phase D — also charge against the LeilAI-5 wallet when Phase 0a's
    # service-token middleware is live.  Logged-only no-op otherwise.
    await _maybe_deduct_credits(
        endpoint=endpoint_label,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )

    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON; first 200 chars: %s", text[:200])
        return fallback_fn("non_json_response")

    payload = _validate_payload(raw)
    payload["source"]      = "llm_interpretation_deepseek"
    payload["calibration"] = "narrative"
    return payload
