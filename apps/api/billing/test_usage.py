"""
Regression tests for the per-user deduct helper (apps/api/billing/usage.py).

Covers the behaviour matrix:

  | agent_url | service_token | caller JWT | maybe_deduct_credits does …      |
  |-----------|---------------|------------|----------------------------------|
  | unset     | —             | —          | nothing (silent no-op)            |
  | set       | unset         | —          | nothing (logged no-op)            |
  | set       | set           | missing    | nothing (skip; can't attribute)   |
  | set       | set           | present    | POST /billing/credits/deduct      |

The live case asserts the forwarded Authorization header + user_id so a
regression that drops per-user attribution (the original TODO) fails loudly.

Run:
    pytest apps/api/billing/test_usage.py -v
"""
from __future__ import annotations

import asyncio

import pytest

from apps.api.billing import usage
from apps.api.billing.usage import (
    maybe_deduct_credits,
    maybe_deduct_flat_credits,
    maybe_deduct_metered_wall_time,
    set_billing_context,
)


def _run(coro):
    """Drive a coroutine to completion without pytest-asyncio.

    The repo's other async code is exercised via FastAPI's sync TestClient;
    this helper keeps the same zero-extra-dependency policy.
    """
    return asyncio.run(coro)


class _CapturingClient:
    """Minimal async-context-manager stand-in for httpx.AsyncClient.

    Records the single .post(...) call so tests can assert on URL /
    headers / body without a real network round-trip.
    """

    calls: list[dict] = []

    def __init__(self, *_, **__):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def post(self, url, *, headers=None, json=None):
        type(self).calls.append({"url": url, "headers": headers or {}, "json": json or {}})
        return None


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    """Each test starts with a clean call log + empty caller context."""
    _CapturingClient.calls = []
    set_billing_context(None, None)
    # Route the helper's lazy ``import httpx`` at call time to our fake.
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _CapturingClient)
    yield
    set_billing_context(None, None)


def _set_billing_env(monkeypatch, *, agent_url: str, token: str):
    monkeypatch.setattr(usage.settings, "leil_agent_url", agent_url, raising=False)
    monkeypatch.setattr(usage.settings, "leil_service_token", token, raising=False)


def test_no_agent_url_is_silent_noop(monkeypatch):
    _set_billing_env(monkeypatch, agent_url="", token="")
    set_billing_context("Bearer jwt", "user-1")
    _run(maybe_deduct_credits(endpoint="chat_local", prompt_tokens=10, completion_tokens=5))
    assert _CapturingClient.calls == []


def test_no_service_token_is_noop(monkeypatch):
    _set_billing_env(monkeypatch, agent_url="https://www.leil.app/api/v1", token="")
    set_billing_context("Bearer jwt", "user-1")
    _run(maybe_deduct_credits(endpoint="chat_local", prompt_tokens=10, completion_tokens=5))
    assert _CapturingClient.calls == []


def test_missing_caller_jwt_skips_deduct(monkeypatch):
    # Both env vars set (Phase 0a live) but no JWT in context → skip rather
    # than mis-charge.  This guards the "can't attribute" branch.
    _set_billing_env(monkeypatch, agent_url="https://www.leil.app/api/v1", token="svc-token")
    set_billing_context(None, None)
    _run(maybe_deduct_credits(endpoint="chat_local", prompt_tokens=10, completion_tokens=5))
    assert _CapturingClient.calls == []


def test_live_deduct_forwards_jwt_and_user(monkeypatch):
    _set_billing_env(monkeypatch, agent_url="https://www.leil.app/api/v1", token="svc-token")
    set_billing_context("Bearer real.jwt.value", "user-42")

    _run(maybe_deduct_credits(
        endpoint="chat_local",
        prompt_tokens=120,
        completion_tokens=30,
        model="deepseek/deepseek-v4-pro",
    ))

    assert len(_CapturingClient.calls) == 1
    call = _CapturingClient.calls[0]
    # No double /v1 — agent_url is the versioned base already.
    assert call["url"] == "https://www.leil.app/api/v1/billing/credits/deduct"
    # Per-user attribution: both the forwarded Bearer token AND the service token.
    assert call["headers"]["Authorization"] == "Bearer real.jwt.value"
    assert call["headers"]["X-Leil-Service-Token"] == "svc-token"
    # Body carries the metering inputs + identity + source app.
    body = call["json"]
    assert body["source_app"] == "leilmat"
    assert body["endpoint"] == "chat_local"
    assert body["model"] == "deepseek/deepseek-v4-pro"
    assert body["prompt_tokens"] == 120
    assert body["completion_tokens"] == 30
    assert body["user_id"] == "user-42"


def test_flat_deduct_forwards_jwt_and_flat_credits(monkeypatch):
    _set_billing_env(monkeypatch, agent_url="https://www.leil.app/api/v1", token="svc-token")
    set_billing_context("Bearer real.jwt.value", "user-42")

    _run(maybe_deduct_flat_credits(endpoint="/api/microstructure/simulate", credits=15))

    assert len(_CapturingClient.calls) == 1
    call = _CapturingClient.calls[0]
    assert call["url"] == "https://www.leil.app/api/v1/billing/credits/deduct"
    assert call["headers"]["Authorization"] == "Bearer real.jwt.value"
    assert call["headers"]["X-Leil-Service-Token"] == "svc-token"
    body = call["json"]
    assert body["source_app"] == "leilmat"
    assert body["endpoint"] == "/api/microstructure/simulate"
    assert body["flat_credits"] == 15
    assert body["user_id"] == "user-42"
    # Flat charge carries NO token fields — signals "deduct directly, no markup".
    assert "prompt_tokens" not in body
    assert "model" not in body


def test_flat_deduct_noop_without_token(monkeypatch):
    _set_billing_env(monkeypatch, agent_url="https://www.leil.app/api/v1", token="")
    set_billing_context("Bearer jwt", "user-1")
    _run(maybe_deduct_flat_credits(endpoint="/api/phase/scheil", credits=5))
    assert _CapturingClient.calls == []


def _set_cloud_cost_env(monkeypatch, *, price=0.05, markup=3.0, per_dollar=100):
    monkeypatch.setattr(usage.settings, "daytona_usd_per_vcpu_hour", price, raising=False)
    monkeypatch.setattr(usage.settings, "cloud_cost_markup", markup, raising=False)
    monkeypatch.setattr(usage.settings, "credits_per_dollar", per_dollar, raising=False)


def test_metered_wall_time_prices_and_bills_flat(monkeypatch):
    # cost = 2100/3600 × 4 × 0.05 × 3 = $0.35 → 35 flat credits.
    _set_billing_env(monkeypatch, agent_url="https://www.leil.app/api/v1", token="svc-token")
    _set_cloud_cost_env(monkeypatch)
    set_billing_context("Bearer real.jwt.value", "user-42")

    _run(maybe_deduct_metered_wall_time(
        endpoint="/api/compute/grain/grow", wall_secs=2100, cpu_count=4))

    assert len(_CapturingClient.calls) == 1
    body = _CapturingClient.calls[0]["json"]
    assert body["source_app"] == "leilmat"
    assert body["endpoint"] == "/api/compute/grain/grow"
    assert body["flat_credits"] == 35          # the priced cloud cost, not a flat $0.01
    assert body["user_id"] == "user-42"
    # Billed via the flat path — no token fields (so LeilAI-5 won't re-price it).
    assert "wall_secs" not in body and "model" not in body


def test_metered_wall_time_scales_with_job_size(monkeypatch):
    # A long job must cost more than a short one (the bug we fixed: both were $0.01).
    _set_billing_env(monkeypatch, agent_url="https://www.leil.app/api/v1", token="svc-token")
    _set_cloud_cost_env(monkeypatch)
    set_billing_context("Bearer jwt", "user-1")

    _run(maybe_deduct_metered_wall_time(endpoint="x", wall_secs=120, cpu_count=4))
    short = _CapturingClient.calls[-1]["json"]["flat_credits"]
    _run(maybe_deduct_metered_wall_time(endpoint="x", wall_secs=7200, cpu_count=4))
    long = _CapturingClient.calls[-1]["json"]["flat_credits"]
    assert long > short > 0


def test_metered_wall_time_subcent_skips_deduct(monkeypatch):
    # A few-second job rounds to <1 credit → no billing round-trip.
    _set_billing_env(monkeypatch, agent_url="https://www.leil.app/api/v1", token="svc-token")
    _set_cloud_cost_env(monkeypatch)
    set_billing_context("Bearer jwt", "user-1")
    _run(maybe_deduct_metered_wall_time(endpoint="x", wall_secs=5, cpu_count=1))
    assert _CapturingClient.calls == []


def test_metered_wall_time_clamps_to_max(monkeypatch):
    # A pathological wall-time can't exceed LeilAI-5's MAX_FLAT_CREDITS (would 400).
    _set_billing_env(monkeypatch, agent_url="https://www.leil.app/api/v1", token="svc-token")
    _set_cloud_cost_env(monkeypatch)
    set_billing_context("Bearer jwt", "user-1")
    _run(maybe_deduct_metered_wall_time(endpoint="x", wall_secs=10**9, cpu_count=64))
    assert _CapturingClient.calls[-1]["json"]["flat_credits"] == 1000


def test_deduct_swallows_billing_errors(monkeypatch):
    # A failing billing call must never bubble up into the user's response.
    _set_billing_env(monkeypatch, agent_url="https://www.leil.app/api/v1", token="svc-token")
    set_billing_context("Bearer jwt", "user-1")

    class _BoomClient(_CapturingClient):
        async def post(self, *_, **__):
            raise RuntimeError("billing down")

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _BoomClient)

    # Should NOT raise.
    _run(maybe_deduct_credits(endpoint="chat_local", prompt_tokens=1, completion_tokens=1))
