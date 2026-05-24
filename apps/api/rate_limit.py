"""
apps.api.rate_limit
====================

slowapi-based IP rate limiter.  Three tiers:

    rate_limit_llm_per_minute            ← /interpret*, /chat/* (cost-bearing)
    rate_limit_heavy_compute_per_minute  ← /microstructure/simulate, /scheil
    rate_limit_default_per_minute        ← everything else (catch-all)

Usage on a route:

    from apps.api.rate_limit import limiter, LLM_LIMIT

    @router.post("/interpret")
    @limiter.limit(LLM_LIMIT)
    async def endpoint(request: Request, req: MyRequest):
        ...

Notes:
* The endpoint MUST accept ``request: Request`` as a parameter — slowapi
  pulls the client IP from there.  Positional name doesn't matter as long
  as it's present.
* When the limit fires, the response is HTTP 429 with JSON body
  ``{"error": "Rate limit exceeded: ...", "detail": "..."}`` produced by
  slowapi's built-in handler.
* The limiter uses ``get_remote_address`` (client IP) as the key.  Behind
  a proxy / load balancer in production, replace it with a function that
  reads ``X-Forwarded-For``.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from apps.api.config import settings


# Module-level singleton.  Routers + main.py import this instance.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_default_per_minute}/minute"],
)


# Pre-formatted string literals so each route reads tier-by-name rather
# than fishing the integer out of settings inline.
LLM_LIMIT            = f"{settings.rate_limit_llm_per_minute}/minute"
HEAVY_COMPUTE_LIMIT  = f"{settings.rate_limit_heavy_compute_per_minute}/minute"
DEFAULT_LIMIT        = f"{settings.rate_limit_default_per_minute}/minute"
