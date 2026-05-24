"""
apps.api.ml.llm_budget
=======================

In-process daily LLM-spend cap.  Tracks cumulative USD cost reported by
OpenRouter on each completion and short-circuits to the deterministic
fallback path once we exceed ``settings.llm_daily_budget_usd``.

Why in-process?  Current LeilMat runs as a single uvicorn worker; a
shared file or Redis would add deps and offer little benefit at this
scale.  The counter rolls over automatically at UTC midnight so a
"day" is wall-clock, not "since process start."

Concurrency: the singleton uses ``threading.Lock`` because charge() can
be called from multiple FastAPI async workers via asyncio.to_thread, and
the increments must be atomic.

Cost extraction: OpenRouter's chat-completion response carries the cost
in ``response.usage.cost`` (USD).  Some providers return None; in that
case we estimate from token counts via a per-model fallback rate.
"""
from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timezone
from typing import Any

from apps.api.config import settings

logger = logging.getLogger(__name__)


# Per-1k-token fallback rates used when OpenRouter doesn't return a cost
# field.  Order-of-magnitude correct as of 2025; doesn't have to be precise
# — it's only used to keep the budget tracker non-zero when the provider
# omits cost.
_FALLBACK_RATE_USD_PER_1K_TOKENS = {
    "default":  0.005,
    "deepseek": 0.004,
    "gpt-4":    0.03,
    "gpt-3.5":  0.002,
    "claude":   0.015,
}


def _fallback_cost(model: str | None, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost when the upstream response doesn't carry one."""
    rate = _FALLBACK_RATE_USD_PER_1K_TOKENS["default"]
    if model:
        m = model.lower()
        for key, r in _FALLBACK_RATE_USD_PER_1K_TOKENS.items():
            if key in m:
                rate = r
                break
    return (prompt_tokens + completion_tokens) / 1000.0 * rate


class DailyBudget:
    """Singleton in-memory tracker.  Resets at UTC midnight."""

    def __init__(self, cap_usd: float):
        self._cap_usd = cap_usd
        self._date_utc: date = datetime.now(timezone.utc).date()
        self._spent_usd: float = 0.0
        self._calls: int = 0
        self._per_endpoint: dict[str, dict[str, float]] = {}   # {endpoint: {calls, cost}}
        self._lock = threading.Lock()

    @property
    def cap_usd(self) -> float:
        return self._cap_usd

    def _maybe_rollover(self) -> None:
        """Reset counters if we've crossed UTC midnight since last access."""
        today = datetime.now(timezone.utc).date()
        if today != self._date_utc:
            logger.info(
                "[llm_budget] UTC rollover %s → %s; previous day spent $%.4f over %d calls",
                self._date_utc, today, self._spent_usd, self._calls,
            )
            self._date_utc = today
            self._spent_usd = 0.0
            self._calls = 0
            self._per_endpoint = {}

    # ── Public surface ──────────────────────────────────────────────

    def can_spend(self) -> bool:
        """``True`` if there's still room in today's budget.

        Cap of 0 (or negative) disables the gate — every call passes.
        """
        with self._lock:
            self._maybe_rollover()
            if self._cap_usd <= 0:
                return True
            return self._spent_usd < self._cap_usd

    def charge(
        self,
        endpoint: str,
        cost_usd: float | None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        model: str | None = None,
    ) -> float:
        """Record an LLM call's actual (or estimated) cost.

        Returns the cost that was charged.  Safe to call even when no
        cost was reported by the provider — falls back to a token-based
        estimate so the budget still moves.
        """
        cost = float(cost_usd) if cost_usd is not None and cost_usd > 0 else \
            _fallback_cost(model, prompt_tokens, completion_tokens)
        with self._lock:
            self._maybe_rollover()
            self._spent_usd += cost
            self._calls     += 1
            bucket = self._per_endpoint.setdefault(
                endpoint, {"calls": 0, "cost": 0.0}
            )
            bucket["calls"] += 1
            bucket["cost"]  += cost
        return cost

    def status(self) -> dict[str, Any]:
        """Snapshot for the /api/health/budget endpoint and tests."""
        with self._lock:
            self._maybe_rollover()
            return {
                "date_utc":          self._date_utc.isoformat(),
                "cap_usd":           round(self._cap_usd, 4),
                "spent_usd":         round(self._spent_usd, 4),
                "remaining_usd":     round(max(0.0, self._cap_usd - self._spent_usd), 4)
                                     if self._cap_usd > 0 else None,
                "total_calls":       self._calls,
                "over_budget":       self._cap_usd > 0 and self._spent_usd >= self._cap_usd,
                "per_endpoint":      {
                    ep: {"calls": v["calls"], "cost": round(v["cost"], 4)}
                    for ep, v in self._per_endpoint.items()
                },
            }


# Module-level singleton — every caller (interpret_common, chat router,
# tests) imports this.  Initialised once at import time.
BUDGET = DailyBudget(cap_usd=settings.llm_daily_budget_usd)
