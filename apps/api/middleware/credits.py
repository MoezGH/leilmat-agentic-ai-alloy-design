"""
Pre-flight credit-check middleware (Phase D).

Calls LeilAI-5's billing API to confirm the signed-in user has enough
balance BEFORE we kick off a cost-bearing endpoint.  Runs only on the
same set of prefixes the auth middleware enforces — so unauthenticated
requests have already been bounced with 401 by the time we arrive.

──── Behaviour matrix ────

| Phase 0a deployed?  | LEIL_AGENT_URL  | LEIL_SERVICE_TOKEN | What this middleware does                          |
|---------------------|-----------------|--------------------|----------------------------------------------------|
| no                  | blank           | blank              | Pass-through (logged-only "credits-check skipped") |
| no                  | set             | blank              | Pass-through + WARNING (token not yet issued)       |
| yes                 | set             | set                | POST /v1/billing/credits/check; 402 → propagate     |

The "logged-only no-op" mode is the explicit handoff requirement:
> Until Phase 0a is deployed, you can build the middleware but flip the
> `deduct` call to a no-op (log only).

Deduct is handled by the existing cost-logging path in
``apps/api/ml/interpret_common.py`` — when LEIL_SERVICE_TOKEN is set,
it'll POST /v1/billing/credits/deduct after each LLM call alongside
the local DailyBudget.charge().  Until then, deduct is also a no-op.
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

import httpx
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from apps.api.config import settings
from apps.api.middleware.auth import _is_enforced

logger = logging.getLogger(__name__)


class CreditsMiddleware(BaseHTTPMiddleware):
    """Pre-flight check against LeilAI-5's wallet.

    Skips paths that the auth middleware doesn't enforce — there's no
    point checking credits on /health or /api/cost/options.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable],
    ):
        if not _is_enforced(request.url.path):
            return await call_next(request)

        agent_url = (settings.leil_agent_url or "").rstrip("/")
        token     = settings.leil_service_token

        if not agent_url:
            # Phase 0a not yet wired locally — skip credit check entirely.
            # The local DailyBudget cap still applies as a fallback.
            logger.debug("[credits] LEIL_AGENT_URL unset; skipping check for %s",
                         request.url.path)
            return await call_next(request)

        if not token:
            # Pre-Phase 0a — billing service exists but the service token
            # isn't issued yet.  Log loudly so it's obvious the gate is
            # OPEN; pass through.
            logger.warning(
                "[credits] LEIL_SERVICE_TOKEN unset; credit-check is a "
                "no-op for %s (Phase 0a not deployed)",
                request.url.path,
            )
            return await call_next(request)

        # Read the user's JWT from the request — auth middleware ran
        # already and verified it.  We re-read the raw header here
        # because forwarding the same Bearer token upstream is exactly
        # what LeilAI-5 expects (it re-verifies on its end).
        user_jwt = request.headers.get("Authorization", "")
        if not user_jwt.startswith("Bearer "):
            # Shouldn't happen — auth middleware enforces this — but
            # be defensive.
            return JSONResponse(
                status_code=401,
                content={"error": "unauthenticated",
                         "detail": "JWT missing on credits check"},
            )

        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                r = await client.post(
                    f"{agent_url}/v1/billing/credits/check",
                    headers={
                        "Authorization":       user_jwt,
                        "X-Leil-Service-Token": token,
                    },
                    json={"source_app": "leilmat", "path": request.url.path},
                )
        except httpx.TimeoutException:
            # Don't block the user on a slow billing backend.  Log and
            # let the request through; the local DailyBudget still
            # caps spend at the LeilMat level.
            logger.warning("[credits] check timed out for %s; allowing",
                           request.url.path)
            return await call_next(request)
        except Exception as exc:
            logger.warning("[credits] check failed (%s) for %s; allowing",
                           exc, request.url.path)
            return await call_next(request)

        if r.status_code == 402:
            # Insufficient credits — propagate to the browser so the UI
            # can route the user to www.leil.app/billing.
            try:
                body = r.json()
            except Exception:
                body = {"error": "insufficient_credits"}
            body.setdefault("detail",
                            "Insufficient credits.  Top up at www.leil.app/billing.")
            return JSONResponse(status_code=402, content=body)

        if r.status_code >= 500:
            logger.warning("[credits] upstream %d on %s; allowing",
                           r.status_code, request.url.path)

        return await call_next(request)
