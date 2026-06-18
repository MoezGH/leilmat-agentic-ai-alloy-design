"""Background reaper — the cost backstop.

Every ``interval_s`` it:
  1. Marks rows stuck in ``running`` well past the wall-clock cap as
     ``timeout`` (e.g. the worker driving them died), so they stop blocking
     the concurrency cap.
  2. Sweeps any sandbox we own (carries the runner's label) that no live job
     references — deleting orphans that would otherwise burn money.

Started from the FastAPI ``lifespan`` only when ``DAYTONA_API_KEY`` is set.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from apps.api.compute import jobs
from apps.api.compute.runner import get_runner
from apps.api.config import settings

logger = logging.getLogger(__name__)


async def _sweep_once() -> None:
    runner = get_runner()
    if runner is None:
        return

    # 1) Time out rows stuck running far past the cap (driver presumed dead).
    cap = settings.daytona_job_wall_cap_s
    now = datetime.now(timezone.utc)
    for job in await jobs.list_running_jobs():
        started = job.started_at or job.created_at
        if started is None:
            continue
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if (now - started).total_seconds() > cap * 2:
            await jobs.update_job(
                job.id, status=jobs.TIMEOUT,
                error="reaper: job exceeded 2× wall-clock cap (driver presumed dead)",
                finished_at=now,
            )
            logger.warning("[reaper] timed out stuck job %s", job.id)

    # 2) Sweep orphaned sandboxes (those not referenced by a live job).
    alive = await jobs.active_job_ids()
    swept = await runner.sweep_orphans(alive)
    if swept:
        logger.info("[reaper] swept %d orphaned sandbox(es)", swept)


async def reap_loop(interval_s: int = 300) -> None:
    logger.info("[reaper] started (every %ds)", interval_s)
    while True:
        try:
            await _sweep_once()
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover
            logger.exception("[reaper] sweep failed")
        await asyncio.sleep(interval_s)
