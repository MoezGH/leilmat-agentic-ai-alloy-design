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

    job = await jobs.create_job(kind=kind, params=params, user_id=user_id)
    # Commit the estimate up front so concurrent submits see it in the cap.
    await jobs.update_job(job.id, est_cost_usd=est_cost_usd)

    task = asyncio.create_task(
        _drive(runner, job.id, body, snapshot, artifacts, parse, est_cost_usd)
    )
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return job


async def _drive(
    runner: CloudRunner,
    job_id: str,
    body: str,
    snapshot: str | None,
    artifacts: dict[str, str],
    parse: Callable[[dict[str, bytes | None]], dict],
    est_cost_usd: float,
) -> None:
    handle = None
    started = time.monotonic()
    cap = settings.daytona_job_wall_cap_s
    try:
        await jobs.update_job(job_id, status=jobs.RUNNING, started_at=_now())
        handle = await runner.submit(body, job_id=job_id, snapshot=snapshot)
        await jobs.update_job(job_id, sandbox_id=handle.sandbox_id)

        while True:
            elapsed = time.monotonic() - started
            if elapsed > cap:
                await jobs.update_job(
                    job_id, status=jobs.TIMEOUT,
                    error=f"wall-clock cap of {cap}s exceeded",
                    finished_at=_now(), wall_secs=round(elapsed, 1),
                    est_cost_usd=_actual_cost(elapsed, est_cost_usd),
                )
                return

            res = await runner.poll(handle)
            if res.state == "running":
                await asyncio.sleep(POLL_INTERVAL_S)
                continue

            elapsed = time.monotonic() - started
            if res.state == "failed":
                log_tail = (await runner.fetch_log(handle))[-2000:]
                await jobs.update_job(
                    job_id, status=jobs.FAILED,
                    error=f"job exited rc={res.rc}\n{log_tail}",
                    finished_at=_now(), wall_secs=round(elapsed, 1),
                    est_cost_usd=_actual_cost(elapsed, est_cost_usd),
                )
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
                await jobs.update_job(
                    job_id, status=jobs.FAILED, error=f"result parse/contract failed: {exc}",
                    finished_at=_now(), wall_secs=round(elapsed, 1),
                    est_cost_usd=_actual_cost(elapsed, est_cost_usd),
                )
                return
            await jobs.update_job(
                job_id, status=jobs.DONE, result=result,
                finished_at=_now(), wall_secs=round(elapsed, 1),
                est_cost_usd=_actual_cost(elapsed, est_cost_usd),
            )
            return
    except Exception as exc:
        logger.exception("[compute] driver crashed for job %s", job_id)
        try:
            await jobs.update_job(
                job_id, status=jobs.FAILED, error=str(exc), finished_at=_now(),
                wall_secs=round(time.monotonic() - started, 1),
            )
        except Exception:
            pass
    finally:
        if handle is not None:
            await runner.cleanup(handle)
