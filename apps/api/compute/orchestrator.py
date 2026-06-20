"""Job lifecycle orchestration + always-on cost guardrails.

``submit_job`` performs the cost-guard checks, inserts a ``queued`` row, and
launches a background task that drives the runner through
submit → poll(rc-file) → download → parse → cleanup, persisting each state
transition to Postgres so any worker can serve the poll.

Cost guardrails are enforced HERE, not in the credit middleware, because real
money is spent the moment a sandbox runs — regardless of whether the (dormant)
LeilAI-5 credit system is wired.  Three layers:
  * concurrency cap   — refuse if too many jobs are already active
  * daily USD ceiling — refuse if today's committed spend would exceed the cap
  * per-job wall clock — the driver kills + marks ``timeout`` past the cap

MVP drives jobs with ``asyncio.create_task``; if the worker restarts mid-job
the row is left ``running`` and the reaper marks it ``timeout`` and sweeps the
sandbox.  The hardening path (a dedicated DB-polling worker) is noted for later.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable

from apps.api.compute import jobs
from apps.api.compute.calibration import validate_calibration
from apps.api.compute.runner import CloudRunner, get_runner
from apps.api.config import settings

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 3.0
# Conservative upper-bound price for a small CPU sandbox, used only to
# estimate spend for the daily cap.  Daytona's H100 is $3.95/hr; a 1-2 vCPU
# box is far cheaper, but we over-estimate so the cap errs safe.
_PRICE_USD_PER_HOUR = 0.20

# Keep strong refs to in-flight driver tasks so they aren't GC'd.
_TASKS: set[asyncio.Task] = set()


class CloudDisabledError(RuntimeError):
    """Raised when no runner is configured (DAYTONA_API_KEY unset)."""


class CapExceeded(RuntimeError):
    """Raised when a cost guardrail blocks the submission."""

    def __init__(self, reason: str, detail: str):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _actual_cost(wall_secs: float, floor: float) -> float:
    return round(max(floor, (wall_secs / 3600.0) * _PRICE_USD_PER_HOUR), 4)


# Map a job kind to its billing endpoint path (for the metered deduct).
_KIND_PATH = {"grain_tessellate": "grain/tessellate", "grain_grow": "grain/grow"}


def _kind_endpoint(kind: str) -> str:
    return f"/api/compute/{_KIND_PATH.get(kind, kind)}"


async def submit_job(
    *,
    kind: str,
    params: dict,
    user_id: str | None,
    body: str,
    artifacts: dict[str, str],
    parse: Callable[[dict[str, bytes | None]], dict],
    snapshot: str | None = None,
    est_cost_usd: float = 0.10,
    user_email: str | None = None,
    wall_cap_s: int | None = None,
) -> jobs.ComputeJob:
    """Validate cost guardrails, create the job row, and launch the driver.

    Raises :class:`CloudDisabledError` (→ 503) or :class:`CapExceeded` (→ 429).
    """
    runner = get_runner()
    if runner is None:
        raise CloudDisabledError("Cloud compute is disabled (DAYTONA_API_KEY unset).")

    active = await jobs.count_active_jobs()
    if active >= settings.daytona_max_concurrent_jobs:
        raise CapExceeded(
            "concurrency",
            f"Too many cloud jobs running ({active}/{settings.daytona_max_concurrent_jobs}). "
            "Try again shortly.",
        )

    spent = await jobs.daily_cost_usd()
    if spent + est_cost_usd >= settings.daytona_daily_budget_usd:
        raise CapExceeded(
            "daily_budget",
            f"Daily cloud-compute budget reached (${spent:.2f}/${settings.daytona_daily_budget_usd:.2f}).",
        )

    job = await jobs.create_job(kind=kind, params=params, user_id=user_id, user_email=user_email)
    # Commit the estimate up front so concurrent submits see it in the cap.
    await jobs.update_job(job.id, est_cost_usd=est_cost_usd)

    cap = wall_cap_s or settings.daytona_job_wall_cap_s
    cpu_count = getattr(runner, "_cpu", 4)
    task = asyncio.create_task(
        _drive(runner, job.id, kind, body, snapshot, artifacts, parse,
               est_cost_usd, cap, user_email, cpu_count)
    )
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return job


async def _finalize(
    job_id: str, kind: str, status: str, *,
    elapsed: float, est_cost_usd: float, cpu_count: int, user_email: str | None,
    result: dict | None = None, error: str | None = None,
) -> None:
    """Single terminal transition: persist the row, meter the spend, notify."""
    await jobs.update_job(
        job_id, status=status, result=result, error=error,
        finished_at=_now(), wall_secs=round(elapsed, 1),
        est_cost_usd=_actual_cost(elapsed, est_cost_usd),
    )
    # Metered billing by CPU-time (no-op until the service token is live).
    try:
        from apps.api.billing.usage import maybe_deduct_metered_wall_time
        await maybe_deduct_metered_wall_time(
            endpoint=_kind_endpoint(kind), wall_secs=elapsed, cpu_count=cpu_count,
        )
    except Exception as exc:  # never let billing affect the job
        logger.warning("[compute] metered deduct failed for %s: %s", job_id, exc)
    # Notify once (email; the frontend tray/toast/browser-notification handle
    # the in-app side via polling). Guarded by notify_sent.
    try:
        job = await jobs.get_job(job_id)
        if job and not job.notify_sent:
            from apps.api.notify.email import send_job_complete_email
            await send_job_complete_email(
                user_email, kind=kind, status=status, result=result, job_id=job_id,
            )
            await jobs.update_job(job_id, notify_sent=True)
    except Exception as exc:
        logger.warning("[compute] notify failed for %s: %s", job_id, exc)


async def _drive(
    runner: CloudRunner,
    job_id: str,
    kind: str,
    body: str,
    snapshot: str | None,
    artifacts: dict[str, str],
    parse: Callable[[dict[str, bytes | None]], dict],
    est_cost_usd: float,
    cap: int,
    user_email: str | None,
    cpu_count: int,
) -> None:
    handle = None
    started = time.monotonic()
    try:
        await jobs.update_job(job_id, status=jobs.RUNNING, started_at=_now())
        handle = await runner.submit(body, job_id=job_id, snapshot=snapshot, wall_cap_s=cap)
        await jobs.update_job(job_id, sandbox_id=handle.sandbox_id)

        while True:
            elapsed = time.monotonic() - started
            if elapsed > cap:
                await _finalize(job_id, kind, jobs.TIMEOUT, elapsed=elapsed,
                                est_cost_usd=est_cost_usd, cpu_count=cpu_count,
                                user_email=user_email,
                                error=f"wall-clock cap of {cap}s exceeded")
                return

            res = await runner.poll(handle)
            if res.state == "running":
                await asyncio.sleep(POLL_INTERVAL_S)
                continue

            elapsed = time.monotonic() - started
            if res.state == "failed":
                log_tail = (await runner.fetch_log(handle))[-2000:]
                await _finalize(job_id, kind, jobs.FAILED, elapsed=elapsed,
                                est_cost_usd=est_cost_usd, cpu_count=cpu_count,
                                user_email=user_email,
                                error=f"job exited rc={res.rc}\n{log_tail}")
                return

            # done — download artifacts and parse
            downloaded: dict[str, bytes | None] = {}
            for name, path in artifacts.items():
                downloaded[name] = await runner.download(handle, path)
            try:
                result = parse(downloaded)
                # Honesty gate: refuse to ship a result that overclaims its
                # calibration (the 878857b discipline, enforced for cloud).
                validate_calibration(result)
            except Exception as exc:
                logger.exception("[compute] parse/contract failed for job %s", job_id)
                await _finalize(job_id, kind, jobs.FAILED, elapsed=elapsed,
                                est_cost_usd=est_cost_usd, cpu_count=cpu_count,
                                user_email=user_email,
                                error=f"result parse/contract failed: {exc}")
                return
            await _finalize(job_id, kind, jobs.DONE, elapsed=elapsed,
                            est_cost_usd=est_cost_usd, cpu_count=cpu_count,
                            user_email=user_email, result=result)
            return
    except Exception as exc:
        logger.exception("[compute] driver crashed for job %s", job_id)
        try:
            await _finalize(job_id, kind, jobs.FAILED,
                            elapsed=time.monotonic() - started,
                            est_cost_usd=est_cost_usd, cpu_count=cpu_count,
                            user_email=user_email, error=str(exc))
        except Exception:
            pass
    finally:
        if handle is not None:
            await runner.cleanup(handle)
