"""Per-user credit deduction against LeilAI-5's central wallet.

Two responsibilities:

1. **Caller identity context.**  The auth middleware verifies the
   Supabase JWT and stashes the raw ``Authorization`` header + ``sub``
   (user id) into contextvars at the top of every request — *before*
   ``call_next``.  Starlette spawns the downstream app (the endpoint
   and every LLM helper it calls) in a task that inherits a **copy** of
   the current context, so these values are visible all the way down to
   the deduct call.  (The reverse direction — a value ``set()`` inside
   the endpoint being visible back up in the middleware — is the case
   Starlette does *not* support; we don't rely on it.)

2. **The shared deduct helper.**  Every cost-bearing LLM path (chat
   stream, interpretation, session-autoname) funnels through
   ``maybe_deduct_credits`` so per-user attribution and the Phase-0a
   behaviour matrix live in exactly one place.

──── Behaviour matrix (mirrors apps/api/middleware/credits.py) ────

| LEIL_AGENT_URL | LEIL_SERVICE_TOKEN | caller JWT | deduct does …                       |
|----------------|--------------------|------------|-------------------------------------|
| blank          | —                  | —          | silent no-op                        |
| set            | blank              | —          | logged-only no-op (Phase 0a not live)|
| set            | set                | missing    | logged warning, skip (can't attribute)|
| set            | set                | present    | POST /billing/credits/deduct (live) |

The deduct is **fire-and-forget**: we never block the user's response on
the billing round-trip, and a billing-service failure is logged but
swallowed (the local ``DailyBudget`` still capped spend).
"""
from __future__ import annotations

import contextvars
import logging

from apps.api.config import settings

logger = logging.getLogger(__name__)


# ─── Per-request caller identity ───────────────────────────────────────
# Set by AuthMiddleware before call_next; read by maybe_deduct_credits
# deep in the LLM call stack.  Defaults make non-request code paths
# (tests, scripts) safe — they simply produce a no-op deduct.
_auth_header: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "leil_auth_header", default=None
)
_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "leil_user_id", default=None
)


def set_billing_context(auth_header: str | None, user_id: str | None) -> None:
    """Record the caller's JWT + user id for the current request task.

    Call this at the top of the auth middleware for *every* request
    (passing ``None`` when unauthenticated) so a previous request's
    identity can never leak into this one.
    """
    _auth_header.set(auth_header or None)
    _user_id.set(user_id or None)


def current_auth_header() -> str | None:
    return _auth_header.get()


def current_user_id() -> str | None:
    return _user_id.get()


async def _post_deduct(endpoint: str, body_extra: dict) -> None:
    """Shared gate + POST for both token-metered and flat deducts.

    No-op unless both ``LEIL_AGENT_URL`` and ``LEIL_SERVICE_TOKEN`` are
    set (Phase 0a live) *and* a caller JWT is present in the request
    context.  Never raises — failures are logged and swallowed.
    """
    agent_url = (settings.leil_agent_url or "").rstrip("/")
    token = settings.leil_service_token

    if not agent_url:
        # Phase 0a not wired locally — local DailyBudget is the only cap.
        return

    if not token:
        logger.warning(
            "[credits] LEIL_SERVICE_TOKEN unset; deduct for %s is a no-op "
            "(Phase 0a not deployed)",
            endpoint,
        )
        return

    auth_header = current_auth_header()
    if not auth_header:
        # We have a service token but no per-user JWT — LeilAI-5 can't
        # tell which wallet to debit.  Skip rather than mis-charge, and
        # log loudly so this is obvious if it ever happens on a gated
        # path (it shouldn't: those always carry a verified Bearer token).
        logger.warning(
            "[credits] no caller JWT in context for %s; skipping deduct "
            "(cannot attribute spend to a wallet)",
            endpoint,
        )
        return

    body = {"source_app": "leilmat", "endpoint": endpoint, **body_extra}
    user_id = current_user_id()
    if user_id:
        body["user_id"] = user_id

    # Lazy import — keeps the OpenAI-only test paths fast.
    import httpx

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(
                # LEIL_AGENT_URL is the versioned base (.../api/v1);
                # do NOT re-add /v1 here.
                f"{agent_url}/billing/credits/deduct",
                headers={
                    "Authorization": auth_header,
                    "X-Leil-Service-Token": token,
                },
                json=body,
            )
    except Exception as exc:
        # Never block the user's response on a billing-call failure;
        # the local DailyBudget already capped spend.
        logger.warning("[credits] deduct failed for %s: %s", endpoint, exc)


async def maybe_deduct_credits(
    *,
    endpoint: str,
    prompt_tokens: int,
    completion_tokens: int,
    model: str | None = None,
) -> None:
    """Token-metered deduct: LeilAI-5 computes cost = tokens × price × 3.0×.

    Use for LLM calls, where the central wallet applies the standard
    ``TOKEN_PRICE_MULTIPLIER`` markup against the reported model + tokens.
    """
    await _post_deduct(
        endpoint,
        {
            "model": model or settings.llm_model,
            "prompt_tokens": int(prompt_tokens or 0),
            "completion_tokens": int(completion_tokens or 0),
        },
    )


async def maybe_deduct_flat_credits(*, endpoint: str, credits: int) -> None:
    """Flat deduct: charge a fixed number of display credits directly.

    Use for heavy local compute (Scheil, phase-field, KWN, inverse design)
    that runs on LeilMat's own server.  Marginal infra cost is negligible,
    so there is nothing to mark up — the flat ``credits`` value is the
    final price (≈100 % margin) and LeilAI-5 debits ``credits / 100``
    dollars from the wallet with NO multiplier.

    The ``flat_credits`` field signals the central API to skip token-cost
    computation.  (Contract of the optional credit/billing backend
    configured via ``LEIL_AGENT_URL``.)
    """
    await _post_deduct(endpoint, {"flat_credits": int(credits)})


# Mirror of LeilAI-5's MAX_FLAT_CREDITS guard (subapp_credits.py): a single
# flat charge above this is rejected with HTTP 400.  We clamp on our side so a
# pathological wall-time never trips it (2 h × 4 vCPU is only ~120 credits).
_MAX_FLAT_CREDITS = 1000


async def maybe_deduct_metered_wall_time(
    *,
    endpoint: str,
    wall_secs: float,
    cpu_count: int,
) -> None:
    """Wall-time-metered deduct for CLOUD jobs (Daytona sandboxes).

    Unlike local sims (flat) or LLM calls (token), cloud jobs incur a real
    per-job marginal cost proportional to ``wall_secs × cpu_count``.

    LeilAI-5's deduct endpoint has no wall-time shape (only token + flat), so
    LeilMat prices the job itself —
    ``cost_usd = wall_secs/3600 × cpu × daytona_usd_per_vcpu_hour ×
    cloud_cost_markup`` — converts it to display credits (``× credits_per_dollar``,
    matching LeilAI-5's ``CREDITS_PER_DOLLAR``) and bills it through the FLAT
    path, which LeilAI-5 charges verbatim with no further markup.  Charged at
    job COMPLETION (not submit), so the user pays for the compute actually used.
    No-op until the service token is live.
    """
    hours = max(0.0, float(wall_secs)) / 3600.0
    cpu = max(1, int(cpu_count or 1))
    cost_usd = (
        hours * cpu
        * settings.daytona_usd_per_vcpu_hour
        * settings.cloud_cost_markup
    )
    credits = max(0, min(round(cost_usd * settings.credits_per_dollar), _MAX_FLAT_CREDITS))
    if credits <= 0:
        # Sub-cent job — not worth a billing round-trip.
        logger.info("[credits] %s wall-time cost rounds to 0 credits; skipping deduct",
                    endpoint)
        return
    await maybe_deduct_flat_credits(endpoint=endpoint, credits=credits)
