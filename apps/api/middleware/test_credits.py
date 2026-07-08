"""
Regression tests for the credit-check middleware.

Covers the behaviour matrix from apps/api/middleware/credits.py:

  | agent_url | service_token | behaviour                          |
  |-----------|---------------|------------------------------------|
  | unset     | unset         | silent no-op (pass-through)         |
  | set       | unset         | logged-only no-op + WARNING         |
  | set       | set + 200     | passes through                      |
  | set       | set + 402     | propagates 402 to client            |
  | set       | set + timeout | graceful pass-through + WARNING     |

Plus: routes not in ENFORCED_PREFIXES bypass the middleware entirely
(spec: only cost-bearing paths burn credits).

Run:
    pytest apps/api/middleware/test_credits.py -v
"""
import logging

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import httpx

from apps.api.middleware.credits import CreditsMiddleware


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CreditsMiddleware)

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.post("/api/chat/local")
    async def chat_local(request: Request):
        return {"ok": True}

    @app.post("/api/cost/options")          # bypassed (not in ENFORCED_PREFIXES)
    async def cost_options():
        return {"ok": True}

    return app


# ─────────────────────────────────────────────────────────────────────
# Bypass: non-enforced routes never touch the billing API
# ─────────────────────────────────────────────────────────────────────

def test_health_passes_without_billing_call(monkeypatch):
    """/health is not in ENFORCED_PREFIXES so credits middleware skips."""
    called = []

    async def fake_post(*args, **kwargs):
        called.append((args, kwargs))
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_agent_url",
        "https://leil.app/api", raising=False,
    )
    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_service_token",
        "test-token", raising=False,
    )
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    client = TestClient(_build_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert called == []   # billing was NOT called


def test_cost_options_passes_without_billing_call(monkeypatch):
    """/api/cost/options is bypass-listed (read-only, not cost-bearing)."""
    called = []
    async def fake_post(*args, **kwargs):
        called.append(args)
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_agent_url",
        "https://leil.app/api", raising=False,
    )
    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_service_token",
        "test-token", raising=False,
    )
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    client = TestClient(_build_app())
    client.post("/api/cost/options")
    assert called == []


# ─────────────────────────────────────────────────────────────────────
# No-op modes (Phase 0a not deployed)
# ─────────────────────────────────────────────────────────────────────

def test_silent_noop_when_agent_url_unset(monkeypatch):
    """No LEIL_AGENT_URL → silent pass-through, no billing call attempted."""
    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_agent_url", "",
        raising=False,
    )
    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_service_token", "",
        raising=False,
    )
    client = TestClient(_build_app())
    r = client.post("/api/chat/local")
    assert r.status_code == 200


def test_logged_only_noop_when_service_token_unset(monkeypatch, caplog):
    """LEIL_AGENT_URL set but no service token → logged WARNING, pass-through."""
    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_agent_url",
        "https://leil.app/api", raising=False,
    )
    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_service_token", "",
        raising=False,
    )
    caplog.set_level(logging.WARNING, logger="apps.api.middleware.credits")
    client = TestClient(_build_app())
    r = client.post("/api/chat/local")
    assert r.status_code == 200
    assert any("Phase 0a not deployed" in rec.message for rec in caplog.records)


# ─────────────────────────────────────────────────────────────────────
# Live-billing mode (Phase 0a deployed)
# ─────────────────────────────────────────────────────────────────────

def test_402_propagates_to_client(monkeypatch):
    """When the wallet says insufficient credits, surface 402 to the client."""

    async def fake_post(self, url, headers=None, json=None, **_):
        assert "credits/check" in url
        assert headers["X-Leil-Service-Token"] == "test-token"
        return httpx.Response(
            402,
            json={"error": "insufficient_credits", "balance": 0.0},
        )

    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_agent_url",
        "https://leil.app/api", raising=False,
    )
    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_service_token",
        "test-token", raising=False,
    )
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    client = TestClient(_build_app())
    r = client.post(
        "/api/chat/local",
        headers={"Authorization": "Bearer fake.jwt.here"},
    )
    assert r.status_code == 402
    body = r.json()
    assert body["error"] == "insufficient_credits"
    assert "detail" in body
    assert "www.leil.app/pricing" in body["detail"]


def test_billing_500_allows_request_through(monkeypatch, caplog):
    """Don't block the user when the billing service is sick."""

    async def fake_post(*args, **kwargs):
        return httpx.Response(503, json={"error": "service_unavailable"})

    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_agent_url",
        "https://leil.app/api", raising=False,
    )
    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_service_token",
        "test-token", raising=False,
    )
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    caplog.set_level(logging.WARNING, logger="apps.api.middleware.credits")
    client = TestClient(_build_app())
    r = client.post(
        "/api/chat/local",
        headers={"Authorization": "Bearer fake.jwt"},
    )
    assert r.status_code == 200
    assert any("upstream 503" in rec.message for rec in caplog.records)


def test_billing_timeout_allows_request_through(monkeypatch, caplog):
    """httpx.TimeoutException must not block the user."""

    async def fake_post(*args, **kwargs):
        raise httpx.TimeoutException("upstream slow")

    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_agent_url",
        "https://leil.app/api", raising=False,
    )
    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_service_token",
        "test-token", raising=False,
    )
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    caplog.set_level(logging.WARNING, logger="apps.api.middleware.credits")
    client = TestClient(_build_app())
    r = client.post(
        "/api/chat/local",
        headers={"Authorization": "Bearer fake.jwt"},
    )
    assert r.status_code == 200
    assert any("timed out" in rec.message for rec in caplog.records)


def test_missing_authorization_header_returns_401(monkeypatch):
    """Defensive: even if auth middleware was somehow bypassed, the
    credits middleware refuses to call upstream without a JWT."""
    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_agent_url",
        "https://leil.app/api", raising=False,
    )
    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_service_token",
        "test-token", raising=False,
    )
    client = TestClient(_build_app())
    r = client.post("/api/chat/local")          # no Authorization header
    assert r.status_code == 401
    body = r.json()
    assert body["error"] == "unauthenticated"


# ─────────────────────────────────────────────────────────────────────
# Flat compute charge for heavy simulations (post-response)
# ─────────────────────────────────────────────────────────────────────

def _build_compute_app(monkeypatch) -> tuple[FastAPI, list]:
    """App with a successful + a failing simulation route, plus a
    captured ``maybe_deduct_flat_credits`` so we can assert on charges
    without exercising the real billing round-trip."""
    from starlette.responses import JSONResponse as _JSONResponse

    charged: list[tuple[str, int]] = []

    async def fake_flat(*, endpoint, credits):
        charged.append((endpoint, credits))

    monkeypatch.setattr(
        "apps.api.middleware.credits.maybe_deduct_flat_credits",
        fake_flat, raising=False,
    )
    # Pre-flight check is a silent no-op (no agent URL) so it never blocks;
    # we're isolating the post-response compute charge.
    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_agent_url", "", raising=False,
    )

    app = FastAPI()
    app.add_middleware(CreditsMiddleware)

    @app.post("/api/microstructure/simulate")
    async def simulate():
        return {"ok": True}

    @app.get("/api/phase/scheil")
    async def scheil():
        return _JSONResponse(status_code=500, content={"error": "solver_blew_up"})

    return app, charged


def test_successful_simulation_charges_flat_credits(monkeypatch):
    app, charged = _build_compute_app(monkeypatch)
    client = TestClient(app)
    r = client.post("/api/microstructure/simulate")
    assert r.status_code == 200
    # Phase-field is the 15-credit tier.
    assert charged == [("/api/microstructure/simulate", 15)]


def test_failed_simulation_not_charged(monkeypatch):
    app, charged = _build_compute_app(monkeypatch)
    client = TestClient(app)
    r = client.get("/api/phase/scheil")
    assert r.status_code == 500
    assert charged == []          # never bill a failed run


def test_non_simulation_path_not_charged(monkeypatch):
    """LLM / chat paths debit themselves token-by-token; they must NOT
    also pick up a flat compute charge."""
    app, charged = _build_compute_app(monkeypatch)

    @app.post("/api/chat/local")
    async def chat_local():
        return {"ok": True}

    client = TestClient(app)
    r = client.post("/api/chat/local")
    assert r.status_code == 200
    assert charged == []
