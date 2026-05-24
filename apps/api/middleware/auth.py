"""
Supabase JWT validation middleware for LeilMat.

Design: **opt-in gating** (rather than LeilStruct's opt-out BYPASS_PATHS).
Every request flows through this middleware, but only paths whose prefix
matches ``ENFORCED_PREFIXES`` are required to carry a valid Bearer token.

Why opt-in:
* The canvas at ``/canvas`` needs to render for signed-out users until
  Phase C wires the actual "Sign in with Google" CTA in the header.
* Deterministic / cheap endpoints (``/api/predict``, ``/api/phase/equilibrium``,
  ``/api/cost/options``, the various ``/api/health/*`` probes) stay open.
* Cost-bearing endpoints (anything that hits the LLM, anything that runs
  multi-minute physics) get gated immediately.

Side effect: when a valid JWT is present we attach
``request.state.user_id`` (Supabase ``sub`` claim) regardless of whether
the path was gated.  Downstream handlers can opt into per-user logic
when present without having to re-parse the token.

Soft-mode behaviour:
* If ``settings.supabase_jwt_secret`` is empty, ALL paths pass through
  with a warning.  Lets local-dev work without Supabase configured.
* If the secret is present but no token / bad token is provided on a
  gated path, return 401.

Reference: HANDOFF_AUTH.md step 10 + AUTH_BILLING_REFERENCE.md §4.
"""
from __future__ import annotations

import logging
from typing import Iterable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from apps.api.config import settings

logger = logging.getLogger(__name__)


# Path prefixes that REQUIRE a valid Supabase JWT.  Everything else
# passes through.  Keep this list tight and explicit; widening it is a
# breaking change for the canvas UX.
ENFORCED_PREFIXES: tuple[str, ...] = (
    # All LLM-firing chat endpoints (Local AI, Global AI, Scan).
    "/api/chat/",
    # Cost-bearing interpretation endpoints (LLM-narrated insights).
    "/api/microstructure/interpret",
    "/api/phase/interpret",                # /interpret + /interpret_scheil
    "/api/precipitation/interpret",
    # Heavy compute (multi-minute CPU runs).
    "/api/microstructure/simulate",
    "/api/precipitation/simulate",
    "/api/phase/scheil",
    # Inverse design (BoTorch, expensive).
    "/api/design/",
)


def _is_enforced(path: str, prefixes: Iterable[str] = ENFORCED_PREFIXES) -> bool:
    return any(path.startswith(p) for p in prefixes)


class AuthMiddleware(BaseHTTPMiddleware):
    """Soft-gate auth via Supabase HS256 JWT."""

    async def dispatch(self, request: Request, call_next):
        # Initialise — handlers that read request.state.user_id can
        # assume the attribute always exists.
        request.state.user_id = None

        token_valid = False
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and settings.supabase_jwt_secret:
            token = auth_header.split(" ", 1)[1]
            try:
                # Lazy-import jose so test suites that don't exercise auth
                # don't pay the import cost.
                from jose import jwt
                payload = jwt.decode(
                    token,
                    settings.supabase_jwt_secret,
                    algorithms=["HS256"],
                    options={"verify_aud": False},
                )
                request.state.user_id = payload.get("sub")
                token_valid = True
            except Exception as exc:
                # Don't 401 here — only fail on gated paths.  Soft-fail
                # on cheap paths so an expired session doesn't break the
                # canvas's basic property readout.
                logger.debug("Auth: JWT decode failed for %s: %s",
                             request.url.path, exc)

        # Enforce only on cost-bearing prefixes
        if _is_enforced(request.url.path):
            if not settings.supabase_jwt_secret:
                # Soft-mode: env not configured.  Allow through with a
                # WARNING log so a misconfiguration is loud at deploy
                # time but doesn't break local dev.
                logger.warning(
                    "[auth] SUPABASE_JWT_SECRET missing; allowing gated "
                    "path %s in soft-mode (dev only)",
                    request.url.path,
                )
                return await call_next(request)

            if not token_valid:
                # NB: HTTPException raised inside BaseHTTPMiddleware.dispatch
                # bypasses FastAPI's standard exception handler and surfaces
                # as a 500.  Return a JSONResponse directly so the browser
                # sees the 401 + JSON error body it can render.
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "unauthenticated",
                        "detail": (
                            "Authentication required.  Sign in to use "
                            f"{request.url.path}."
                        ),
                    },
                )

        return await call_next(request)
