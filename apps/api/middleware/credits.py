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

from apps.api.billing.usage import maybe_deduct_flat_credits
from apps.api.config import settings
from apps.api.middleware.auth import _is_enforced

logger = logging.getLogger(__name__)


# ─── Flat compute-credit prices (display credits) ──────────────────────
# Heavy simulations run on LeilMat's OWN server (a fixed cost we already
# pay), so there is no per-job marginal cloud cost to mark up — unlike
# LeilCFD's metered Daytona sandboxes.  These flat prices reflect the
# *value* + compute load of each run, charged directly (no 3× multiplier).
# Tune freely; keys are matched by exact path or path-prefix.
#
# Anchored against the LLM charges (~3–6 credits per chat turn):
#   scheil      — Scheil-Gulliver solidification (pycalphad, ~10–60 s)
#   precipitation/simulate — KWN precipitation solver
#   microstructure/simulate — phase-field dendrite (taichi, heaviest)
#   design/inverse — BoTorch inverse design (pure compute, no LLM here)
COMPUTE_CREDIT_COSTS: dict[str, int] = {
    "/api/phase/scheil":             5,
    "/api/precipitation/simulate":   8,
    "/api/microstructure/simulate": 15,
    "/api/design/inverse":          25,
}


def _compute_cost_for(path: str) -> tuple[str, int] | None:
    """Return (matched_key, credits) if this path is a billable sim."""
    for key, credits in COMPUTE_CREDIT_COSTS.items():
        if path == key or path.startswith(key + "/"):
            return key, credits
    return None


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

        # ── Pre-flight: block with 402 if the user can't afford this ──
        block = await self._preflight_check(request)
        if block is not None:
            return block

        # ── Run the endpoint ──
        response = await call_next(request)

        # ── Post-flight: flat compute charge for successful simulations ──
        await self._maybe_charge_compute(request, response)
        return response

    async def _preflight_check(self, request: Request) -> JSONResponse | None:
        """Ask LeilAI-5 whether the caller can afford this path.

        Returns a 402/401 ``JSONResponse`` to BLOCK the request, or
        ``None`` to allow it through (including all the no-op / degraded
        cases — we fail open so a slow billing backend never breaks the
        product; the local DailyBudget still caps LLM spend).
        """
        agent_url = (settings.leil_agent_url or "").rstrip("/")
        token     = settings.leil_service_token

        if not agent_url:
            # Phase 0a not yet wired locally — skip credit check entirely.
            logger.debug("[credits] LEIL_AGENT_URL unset; skipping check for %s",
                         request.url.path)
            return None

        if not token:
            # Pre-Phase 0a — billing service exists but the service token
            # isn't issued yet.  Log loudly so it's obvious the gate is
            # OPEN; pass through.
            logger.warning(
                "[credits] LEIL_SERVICE_TOKEN unset; credit-check is a "
                "no-op for %s (Phase 0a not deployed)",
                request.url.path,
            )
            return None

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
                    # LEIL_AGENT_URL is the *versioned* base
                    # (https://www.leil.app/api/v1) — append the
                    # route without re-adding /v1/.
                    f"{agent_url}/billing/credits/check",
                    headers={
                        "Authorization":       user_jwt,
                        "X-Leil-Service-Token": token,
                    },
                    json={"source_app": "leilmat", "path": request.url.path},
                )
        except httpx.TimeoutException:
            logger.warning("[credits] check timed out for %s; allowing",
                           request.url.path)
            return None
        except Exception as exc:
            logger.warning("[credits] check failed (%s) for %s; allowing",
                           exc, request.url.path)
            return None

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

        return None

    async def _maybe_charge_compute(self, request: Request, response) -> None:
        """Flat-charge a successful heavy-compute simulation.

        LLM endpoints debit themselves token-by-token inside the call;
        the pure-compute simulations have no such hook, so we charge a
        flat per-run price here once we know the run succeeded (2xx).
        No-op (logged) until Phase 0a's service token is live.
        """
        match = _compute_cost_for(request.url.path)
        if match is None:
            return
        # Only charge for a successful run — never bill a failed sim.
        if not (200 <= response.status_code < 300):
            return
        key, credits = match
        await maybe_deduct_flat_credits(endpoint=key, credits=credits)
