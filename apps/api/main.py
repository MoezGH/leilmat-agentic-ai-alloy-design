from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routers import chat, predict, design, phase
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


@app.get("/health")
async def health():
    return {"status": "ok"}
