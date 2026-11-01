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

Every row above describes the middleware WITH ENFORCEMENT ON, which is what
`_enforcing` below turns on for this module. Enforcement is off by default
(`leil_enforce_credits`), so the matrix is reached only once someone can
actually pay — see the enforcement-switch tests at the end of this file.

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


@pytest.fixture(autouse=True)
def _enforcing(monkeypatch):
    """Enforcement on for the matrix tests in this module.

    The product default is OFF — metering without refusal — so without this the
    pre-flight check returns early and every "does it block?" assertion below
    would pass for the wrong reason.
    """
    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_enforce_credits",
        True, raising=False,
    )


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


# ─────────────────────────────────────────────────────────────────────
# The enforcement switch: metering is not refusal
# ─────────────────────────────────────────────────────────────────────

def test_enforcement_off_never_blocks_even_when_the_wallet_says_no(monkeypatch):
    """The beta posture: a user out of credits is still served.

    With no Stripe key in the deployment and `can_purchase_credits: false` on the
    free tier, a 402 is a dead end only we can clear — so during the beta the
    pre-flight check must not run at all, let alone refuse.
    """
    calls = []

    async def fake_post(self, url, headers=None, json=None, **_):
        calls.append(url)
        return httpx.Response(402, json={"error": "insufficient_credits", "balance": 0.0})

    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_enforce_credits", False, raising=False)
    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_agent_url",
        "https://leil.app/api", raising=False)
    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_service_token", "test-token", raising=False)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    r = TestClient(_build_app()).post(
        "/api/chat/local", headers={"Authorization": "Bearer fake.jwt.here"})

    assert r.status_code == 200
    assert not [u for u in calls if "credits/check" in u], \
        "enforcement off must not even ask; asking costs a round-trip on every request"


def test_enforcement_off_is_the_default(monkeypatch):
    """Nobody should have to remember to turn blocking off before a release."""
    from apps.api.config import Settings
    assert Settings().leil_enforce_credits is False


def test_enforcement_off_still_meters(monkeypatch):
    """The point of the split: usage is attributed even though nothing is refused.

    The flat compute charge is post-flight, so it must survive enforcement being
    off — otherwise turning blocking off would also blind us to what users cost.
    """
    charged = []

    async def fake_charge(self, request, response):
        charged.append(request.url.path)

    monkeypatch.setattr(
        "apps.api.middleware.credits.settings.leil_enforce_credits", False, raising=False)
    monkeypatch.setattr(CreditsMiddleware, "_maybe_charge_compute", fake_charge)

    r = TestClient(_build_app()).post(
        "/api/chat/local", headers={"Authorization": "Bearer fake.jwt.here"})

    assert r.status_code == 200
    assert charged == ["/api/chat/local"]
