import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from apps.api.rate_limit import limiter
from apps.api.middleware.auth import AuthMiddleware
from apps.api.middleware.credits import CreditsMiddleware
from apps.api.routers import chat, predict, design, phase, health, microstructure, precipitation, cost, report, diffusion, compute
from apps.api.config import settings
from apps.api.data.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
    except Exception as exc:
        print(f"[startup] DB init skipped: {exc}")

    # Preload M3GNet in a background thread so the first user request isn't slow
    try:
        from apps.api.ml.m3gnet_predictor import preload_m3gnet_async
        preload_m3gnet_async()
    except Exception as exc:
        print(f"[startup] M3GNet preload skipped: {exc}")

    # Cloud-compute reaper — only when the Daytona tier is enabled.  Sweeps
    # orphaned sandboxes + times out stuck jobs so cost can't run away.
    reaper_task = None
    if settings.daytona_api_key:
        try:
            from apps.api.compute.reaper import reap_loop
            reaper_task = asyncio.create_task(reap_loop())
        except Exception as exc:
            print(f"[startup] compute reaper not started: {exc}")

    yield

    if reaper_task is not None:
        reaper_task.cancel()
        try:
            await reaper_task
        except asyncio.CancelledError:
            pass
        try:
            from apps.api.compute.runner import aclose_runner
            await aclose_runner()
        except Exception:
            pass


app = FastAPI(
    title="LeilMat API",
    description="AI-native alloy design platform",
    version="0.1.0",
    lifespan=lifespan,
    # OpenAPI surfaces (Swagger / ReDoc / openapi.json) DISABLED in
    # production to remove a free reconnaissance surface — endpoint
    # enumeration, request-payload schemas, FastAPI version
    # fingerprinting.  The real security boundary is JWT auth + rate
    # limits + Supabase RLS, but hiding the schema is cheap hygiene.
    #
    # If you need Swagger for local dev, temporarily override these
    # three kwargs to ``"/api/docs"``, ``"/api/redoc"``,
    # ``"/api/openapi.json"`` — do NOT commit that change.  The schema
    # is recoverable from the FastAPI source code in this repo, so
    # this isn't a developer-experience problem in practice.
    docs_url     = None,
    redoc_url    = None,
    openapi_url  = None,
)

# slowapi: register the limiter on app state and the default 429 handler.
# Per-route limits live as @limiter.limit decorators in each router.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Order matters: Starlette processes middlewares OUTSIDE-IN, so the
# LAST `add_middleware` call runs FIRST.  Stacking we want, from the
# perspective of an incoming request:
#   1. CORS              (so a 401/402 carries Access-Control-Allow-* headers)
#   2. AuthMiddleware    (bounce unauth on enforced prefixes)
#   3. CreditsMiddleware (gate on wallet balance once Phase 0a is live)
# Therefore we call add_middleware in REVERSE order.
app.add_middleware(CreditsMiddleware)

# Supabase JWT validation — opt-in gating on cost-bearing prefixes only.
# Soft-mode when SUPABASE_JWT_SECRET is unset (local dev without auth).
app.add_middleware(AuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:4000",
        "https://leil.xyz",
        "https://app.example.org",     # Phase 5 — production frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(predict.router, prefix="/api/predict", tags=["predict"])
app.include_router(design.router, prefix="/api/design", tags=["design"])
app.include_router(phase.router, prefix="/api/phase", tags=["phase"])
app.include_router(microstructure.router, prefix="/api/microstructure", tags=["microstructure"])
app.include_router(precipitation.router,  prefix="/api/precipitation", tags=["precipitation"])
app.include_router(cost.router,           prefix="/api/cost",          tags=["cost"])
app.include_router(report.router,         prefix="/api/report",        tags=["report"])
app.include_router(diffusion.router,      prefix="/api/diffusion",     tags=["diffusion"])
app.include_router(compute.router,        prefix="/api/compute",       tags=["compute"])
app.include_router(health.router, prefix="/api/health", tags=["health"])


@app.get("/health")
async def health():
    return {"status": "ok"}
