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

import json
import logging
import os
import time
import urllib.request
from typing import Iterable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from apps.api.billing.usage import set_billing_context
from apps.api.config import settings

logger = logging.getLogger(__name__)


# ─── JWKS cache for ES256/RS256 signed tokens ──────────────────────────
# Newer Supabase projects sign JWTs with asymmetric keys (ES256 via the
# ``/auth/v1/.well-known/jwks.json`` endpoint) rather than the legacy
# HS256 shared secret.  When a project rotates to signing keys, the
# legacy ``SUPABASE_JWT_SECRET`` shown in the dashboard becomes inert
# for actual signature validation and ``jwt.decode(algorithms=["HS256"])``
# starts rejecting every real token with ``"The specified alg value is
# not allowed"``.
#
# We accommodate both flavours: try JWKS-based asymmetric verification
# first (covers ES256 / RS256), fall back to HS256-with-secret for any
# project still on the legacy scheme.
_JWKS_CACHE: dict = {"jwks": None, "fetched_at": 0.0}
_JWKS_TTL_SECONDS = 600


def _supabase_url() -> str | None:
    """Return the project URL from env, or None if unset."""
    # Prefer explicit SUPABASE_URL; fall back to NEXT_PUBLIC_SUPABASE_URL
    # because that's what the .env file is most likely to have populated.
    return os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")


def _get_jwks() -> dict | None:
    """Lazily fetch + cache the project's JWKS.  Returns None if unreachable."""
    now = time.time()
    if _JWKS_CACHE["jwks"] and (now - _JWKS_CACHE["fetched_at"]) < _JWKS_TTL_SECONDS:
        return _JWKS_CACHE["jwks"]

    base = _supabase_url()
    if not base:
        return None
    url = f"{base.rstrip('/')}/auth/v1/.well-known/jwks.json"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        _JWKS_CACHE["jwks"] = data
        _JWKS_CACHE["fetched_at"] = now
        return data
    except Exception as exc:  # network, JSON, anything
        logger.warning("Auth: JWKS fetch failed (%s): %s", url, exc)
        return None


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
    # Cloud compute — submitting a sandbox job is cost-bearing.  Only the
    # submit path is gated; polling (/api/compute/jobs/{id}) stays open so
    # the frontend can poll freely (job ids are unguessable uuids).
    "/api/compute/grain",
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
        # Accept any auth context as long as a Bearer token is present.
        # We try asymmetric (JWKS) first, then HS256-with-secret.
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            # Lazy-import jose so test suites that don't exercise auth
            # don't pay the import cost.
            from jose import jwt as jose_jwt
            from jose.exceptions import JWTError

            payload = None
            errors: list[str] = []

            # ── Path 1: asymmetric verification via JWKS ────────────────
            # Newer Supabase projects sign tokens with ES256 / RS256.
            jwks = _get_jwks()
            if jwks:
                try:
                    payload = jose_jwt.decode(
                        token,
                        jwks,
                        algorithms=["ES256", "RS256", "EdDSA"],
                        options={"verify_aud": False},
                    )
                except JWTError as exc:
                    errors.append(f"jwks: {exc}")
                except Exception as exc:  # pragma: no cover
                    errors.append(f"jwks: {exc!r}")

            # ── Path 2: legacy HS256 with shared secret ─────────────────
            # Kept for projects that haven't rotated to signing keys, and
            # for the in-process smoke tests that mint tokens with the
            # secret directly.
            if payload is None and settings.supabase_jwt_secret:
                try:
                    payload = jose_jwt.decode(
                        token,
                        settings.supabase_jwt_secret,
                        algorithms=["HS256"],
                        options={"verify_aud": False},
                    )
                except JWTError as exc:
                    errors.append(f"hs256: {exc}")
                except Exception as exc:  # pragma: no cover
                    errors.append(f"hs256: {exc!r}")

            if payload is not None:
                request.state.user_id = payload.get("sub")
                token_valid = True
            else:
                # Don't 401 here — only fail on gated paths.  Soft-fail
                # on cheap paths so an expired session doesn't break the
                # canvas's basic property readout.
                logger.debug("Auth: JWT decode failed for %s: %s",
                             request.url.path, "; ".join(errors) or "no validators configured")

        # Record the caller's identity for the downstream deduct path.
        # Forward the raw Bearer header ONLY when the token actually
        # verified — never relay a bad token to LeilAI-5's wallet.  We set
        # this for every request (None when unauthenticated) so a prior
        # request's identity can't leak into this task's context.
        set_billing_context(
            auth_header if token_valid else None,
            request.state.user_id,
        )

        # Enforce only on cost-bearing prefixes
        if _is_enforced(request.url.path):
            if not settings.supabase_jwt_secret and not _supabase_url():
                # Soft-mode: nothing configured (neither HS256 secret
                # nor a Supabase URL we could fetch JWKS from).  Allow
                # through with a WARNING log so a misconfiguration is
                # loud at deploy time but doesn't break local dev.
                logger.warning(
                    "[auth] No JWT validators configured (neither "
                    "SUPABASE_JWT_SECRET nor SUPABASE_URL/JWKS); "
                    "allowing gated path %s in soft-mode (dev only)",
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
