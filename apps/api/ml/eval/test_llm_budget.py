"""
Regression tests for the daily LLM budget (apps/api/ml/llm_budget.py)
and the rate-limiter wiring (apps/api/rate_limit.py).

Budget is fully testable with no external dependencies; rate-limiter
tests use FastAPI's TestClient against an isolated mini-app so we don't
need uvicorn running.

Run:
    pytest apps/api/ml/eval/test_llm_budget.py -v
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.api.ml.llm_budget import DailyBudget, _fallback_cost


# ─────────────────────────────────────────────────────────────────────
# Fallback-cost estimator
# ─────────────────────────────────────────────────────────────────────

def test_fallback_cost_zero_tokens():
    assert _fallback_cost("deepseek/x", 0, 0) == 0.0


def test_fallback_cost_uses_model_specific_rate():
    """Models with cheaper per-1k rates should price lower for same tokens."""
    cheap = _fallback_cost("gpt-3.5-turbo", 1000, 1000)
    expensive = _fallback_cost("gpt-4-turbo",  1000, 1000)
    assert cheap < expensive


def test_fallback_cost_defaults_for_unknown_model():
    out = _fallback_cost("random/unknown-model", 500, 500)
    assert out > 0   # uses the "default" rate


# ─────────────────────────────────────────────────────────────────────
# DailyBudget — can_spend gate
# ─────────────────────────────────────────────────────────────────────

def test_can_spend_under_cap():
    b = DailyBudget(cap_usd=5.0)
    assert b.can_spend() is True


def test_can_spend_at_cap_is_false():
    b = DailyBudget(cap_usd=1.0)
    b.charge("test", cost_usd=1.0)
    assert b.can_spend() is False


def test_can_spend_zero_cap_disables_gate():
    """cap_usd=0 means "no budget cap" — every call passes."""
    b = DailyBudget(cap_usd=0)
    for _ in range(20):
        b.charge("test", cost_usd=10.0)
    assert b.can_spend() is True


def test_can_spend_negative_cap_disables_gate():
    """Defensive: negative caps shouldn't lock everything out."""
    b = DailyBudget(cap_usd=-1.0)
    b.charge("test", cost_usd=100.0)
    assert b.can_spend() is True


# ─────────────────────────────────────────────────────────────────────
# DailyBudget — charge() bookkeeping
# ─────────────────────────────────────────────────────────────────────

def test_charge_returns_reported_cost():
    b = DailyBudget(cap_usd=5.0)
    out = b.charge("a", cost_usd=0.012)
    assert out == pytest.approx(0.012)


def test_charge_falls_back_to_token_estimate_when_cost_missing():
    """If the upstream doesn't report cost, charge should still
    move the budget via the token-rate estimate."""
    b = DailyBudget(cap_usd=5.0)
    out = b.charge("a", cost_usd=None, prompt_tokens=500,
                   completion_tokens=500, model="deepseek/x")
    assert out > 0


def test_charge_accumulates_across_calls():
    b = DailyBudget(cap_usd=5.0)
    b.charge("a", 0.01)
    b.charge("b", 0.02)
    b.charge("a", 0.03)
    s = b.status()
    assert s["total_calls"]  == 3
    assert s["spent_usd"]    == pytest.approx(0.06)
    assert s["per_endpoint"]["a"]["calls"] == 2
    assert s["per_endpoint"]["b"]["calls"] == 1


def test_status_reports_remaining_and_over_budget():
    b = DailyBudget(cap_usd=1.0)
    b.charge("x", 0.30)
    s = b.status()
    assert s["spent_usd"]     == pytest.approx(0.30)
    assert s["remaining_usd"] == pytest.approx(0.70)
    assert s["over_budget"]   is False
    b.charge("x", 0.80)
    s = b.status()
    assert s["over_budget"]   is True
    assert s["remaining_usd"] == 0.0


# ─────────────────────────────────────────────────────────────────────
# DailyBudget — UTC rollover
# ─────────────────────────────────────────────────────────────────────

def test_rollover_resets_counters():
    """Force the internal date back by a day, then a charge should
    trigger a rollover and reset to zero."""
    b = DailyBudget(cap_usd=1.0)
    b.charge("a", 0.50)
    # Time-warp the budget back to yesterday — next interaction sees
    # "today != yesterday" and resets.
    b._date_utc = date.today() - timedelta(days=1)
    assert b.can_spend() is True   # this call rolls us over
    s = b.status()
    assert s["spent_usd"]   == 0.0
    assert s["total_calls"] == 0
    assert s["date_utc"]    == date.today().isoformat()


# ─────────────────────────────────────────────────────────────────────
# Rate-limiter wiring (uses TestClient, no live server needed)
# ─────────────────────────────────────────────────────────────────────

def test_limiter_fires_429_on_burst():
    """Burst N+1 requests at a route limited to N/minute → last one is 429."""
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    # Fresh limiter so the in-memory counters start clean for this test
    # rather than inheriting state from the production singleton.
    test_limiter = Limiter(key_func=get_remote_address, default_limits=[])
    app = FastAPI()
    app.state.limiter = test_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.get("/ping")
    @test_limiter.limit("3/minute")
    async def ping(request: Request):
        return {"ok": True}

    client = TestClient(app)
    statuses = [client.get("/ping").status_code for _ in range(5)]
    # First 3 pass, last 2 should be 429.
    assert statuses[:3] == [200, 200, 200], f"first 3 should pass: {statuses}"
    assert 429 in statuses[3:], f"4th+ should 429: {statuses}"


def test_429_body_carries_friendly_message():
    """The 429 response body should be machine-parseable so the frontend
    can show a friendly "rate-limited" badge."""
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from slowapi import _rate_limit_exceeded_handler, Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    test_limiter = Limiter(key_func=get_remote_address, default_limits=[])
    app = FastAPI()
    app.state.limiter = test_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.get("/ping")
    @test_limiter.limit("1/minute")
    async def ping(request: Request):
        return {"ok": True}

    client = TestClient(app)
    client.get("/ping")             # consume the single slot
    resp = client.get("/ping")
    assert resp.status_code == 429
    body = resp.json()
    assert "error" in body
    assert "Rate limit exceeded" in body["error"]
