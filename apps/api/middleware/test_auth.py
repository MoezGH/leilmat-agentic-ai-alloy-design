"""
Regression tests for the Supabase JWT auth middleware.

Covers the four real states:
  1. Bypassed path (no token needed)          → 200
  2. Gated path, no token                     → 401
  3. Gated path, invalid token                → 401
  4. Gated path, valid token                  → forwards to handler

Plus the soft-mode behaviour when SUPABASE_JWT_SECRET is empty (gated
paths fall through with a warning so local dev without auth works).

Run:
    pytest apps/api/middleware/test_auth.py -v
"""
# NB: no ``from __future__ import annotations`` — FastAPI's request-model
# introspection breaks on lazy forward-refs from inline-defined routes
# in this file.  Same root cause as the chat.py fix in 3a104f1.

import time

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from apps.api.middleware.auth import AuthMiddleware, ENFORCED_PREFIXES, _is_enforced


# ─────────────────────────────────────────────────────────────────────
# Prefix-matching helpers
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path, expected", [
    # bypassed
    ("/health", False),
    ("/api/health/budget", False),
    ("/api/cost/options", False),
    ("/api/predict", False),
    ("/api/phase/equilibrium", False),
    ("/api/phase/equilibrium/coverage", False),
    ("/api/phase/diagram", False),
    ("/api/precipitation/phases", False),
    # gated
    ("/api/chat/local", True),
    ("/api/chat/global", True),
    ("/api/chat/scan", True),
    ("/api/microstructure/interpret", True),
    ("/api/microstructure/simulate", True),
    ("/api/phase/interpret", True),
    ("/api/phase/interpret_scheil", True),     # prefix-match on /api/phase/interpret
    ("/api/phase/scheil", True),
    ("/api/precipitation/interpret", True),
    ("/api/precipitation/simulate", True),
    ("/api/design/inverse", True),
    ("/api/design/brief", True),
])
def test_is_enforced(path, expected):
    assert _is_enforced(path) is expected, (
        f"{path}: expected enforced={expected}, got {_is_enforced(path)}"
    )


# ─────────────────────────────────────────────────────────────────────
# Helpers for end-to-end middleware tests
# ─────────────────────────────────────────────────────────────────────

def _build_test_app() -> FastAPI:
    """Mini FastAPI app with the auth middleware + one route per tier
    so we can exercise the gating logic without spinning up the full
    LeilMat router stack."""
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.post("/api/chat/local")
    async def chat_local():
        return {"ok": True, "kind": "gated"}

    @app.get("/api/cost/options")
    async def cost_options():
        return {"ok": True, "kind": "bypassed"}

    return app


def _make_jwt(secret: str, **extra) -> str:
    from jose import jwt
    payload = {
        "sub":  "test-user-id",
        "aud":  "authenticated",
        "iat":  int(time.time()),
        "exp":  int(time.time()) + 3600,
        **extra,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# ─────────────────────────────────────────────────────────────────────
# Hard-gating behaviour (secret configured)
# ─────────────────────────────────────────────────────────────────────

def test_bypassed_route_no_token_is_200(monkeypatch):
    monkeypatch.setattr(
        "apps.api.middleware.auth.settings.supabase_jwt_secret",
        "test-secret",
        raising=False,
    )
    client = TestClient(_build_test_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_gated_route_no_token_returns_401(monkeypatch):
    monkeypatch.setattr(
        "apps.api.middleware.auth.settings.supabase_jwt_secret",
        "test-secret",
        raising=False,
    )
    client = TestClient(_build_test_app())
    r = client.post("/api/chat/local")
    assert r.status_code == 401
    body = r.json()
    assert body["error"] == "unauthenticated"
    assert "/api/chat/local" in body["detail"]


def test_gated_route_invalid_token_returns_401(monkeypatch):
    monkeypatch.setattr(
        "apps.api.middleware.auth.settings.supabase_jwt_secret",
        "test-secret",
        raising=False,
    )
    client = TestClient(_build_test_app())
    r = client.post(
        "/api/chat/local",
        headers={"Authorization": "Bearer not.a.real.jwt"},
    )
    assert r.status_code == 401


def test_gated_route_wrong_secret_returns_401(monkeypatch):
    """JWT signed with a different secret must be rejected."""
    monkeypatch.setattr(
        "apps.api.middleware.auth.settings.supabase_jwt_secret",
        "production-secret",
        raising=False,
    )
    client = TestClient(_build_test_app())
    forged = _make_jwt("attacker-secret")
    r = client.post(
        "/api/chat/local",
        headers={"Authorization": f"Bearer {forged}"},
    )
    assert r.status_code == 401


def test_gated_route_valid_token_passes(monkeypatch):
    monkeypatch.setattr(
        "apps.api.middleware.auth.settings.supabase_jwt_secret",
        "test-secret",
        raising=False,
    )
    client = TestClient(_build_test_app())
    token = _make_jwt("test-secret")
    r = client.post(
        "/api/chat/local",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "kind": "gated"}


def test_expired_token_returns_401(monkeypatch):
    """A JWT past its `exp` claim must be rejected."""
    monkeypatch.setattr(
        "apps.api.middleware.auth.settings.supabase_jwt_secret",
        "test-secret",
        raising=False,
    )
    client = TestClient(_build_test_app())
    expired = _make_jwt("test-secret", exp=int(time.time()) - 60)
    r = client.post(
        "/api/chat/local",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert r.status_code == 401


# ─────────────────────────────────────────────────────────────────────
# Soft-mode (no secret configured → all paths pass with warning)
# ─────────────────────────────────────────────────────────────────────

def test_soft_mode_gated_route_passes_without_token(monkeypatch, caplog):
    """When SUPABASE_JWT_SECRET is empty, gated paths must still work
    (local-dev convenience).  Log MUST carry a warning."""
    monkeypatch.setattr(
        "apps.api.middleware.auth.settings.supabase_jwt_secret",
        "",
        raising=False,
    )
    import logging
    caplog.set_level(logging.WARNING, logger="apps.api.middleware.auth")
    client = TestClient(_build_test_app())
    r = client.post("/api/chat/local")
    assert r.status_code == 200
    assert any("soft-mode" in rec.message for rec in caplog.records)


# ─────────────────────────────────────────────────────────────────────
# user_id propagation
# ─────────────────────────────────────────────────────────────────────

def test_user_id_attached_to_request_state(monkeypatch):
    """A valid JWT must populate ``request.state.user_id`` for handlers."""
    monkeypatch.setattr(
        "apps.api.middleware.auth.settings.supabase_jwt_secret",
        "test-secret",
        raising=False,
    )
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.post("/api/chat/local")
    async def who_am_i(request: Request):
        return {"user_id": getattr(request.state, "user_id", None)}

    client = TestClient(app)
    token = _make_jwt("test-secret", sub="user-42")
    r = client.post(
        "/api/chat/local",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["user_id"] == "user-42"
