from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from apps.api.rate_limit import limiter
from apps.api.routers import chat, predict, design, phase, health, microstructure, precipitation, cost
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

    yield


app = FastAPI(
    title="LeilMat API",
    description="AI-native alloy design platform",
    version="0.1.0",
    lifespan=lifespan,
)

# slowapi: register the limiter on app state and the default 429 handler.
# Per-route limits live as @limiter.limit decorators in each router.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:4000", "https://leil.xyz"],
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
app.include_router(health.router, prefix="/api/health", tags=["health"])


@app.get("/health")
async def health():
    return {"status": "ok"}
