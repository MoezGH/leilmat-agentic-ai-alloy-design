"""The ``ComputeJob`` row + async CRUD helpers.

Cloud-job state MUST be shared, not in-process: production runs
``uvicorn --workers=2``, so a poll (`GET /jobs/{id}`) can land on a different
worker than the one running the job.  An in-memory dict would be invisible
across workers.  This table lives in the backend Postgres (`database_url`),
created by ``init_db()`` — the ``Base``/``init_db`` scaffold in
``apps/api/data/database.py`` was kept for exactly this.

Backend-owned (not Supabase/RLS) because the API is the trusted mediator that
holds the Daytona key; the browser only ever talks to the API.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, String, func, select
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.data.database import AsyncSessionLocal, Base

# Job lifecycle states.
QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
TIMEOUT = "timeout"
ACTIVE_STATES = (QUEUED, RUNNING)


class ComputeJob(Base):
    """A single cloud-sandbox compute job (e.g. a Neper tessellation)."""

    __tablename__ = "compute_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=QUEUED, index=True)
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    sandbox_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    est_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    wall_secs: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Caller email (from the JWT claim at submit) for the completion email.
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notify_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_public_dict(self) -> dict:
        """Shape the frontend polls — never leaks sandbox internals."""
        return {
            "job_id": self.id,
            "kind": self.kind,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


# ── async CRUD ─────────────────────────────────────────────────────────

async def create_job(kind: str, params: dict, user_id: str | None,
                     user_email: str | None = None) -> ComputeJob:
    job = ComputeJob(
        id=str(uuid.uuid4()),
        user_id=user_id,
        user_email=user_email,
        kind=kind,
        status=QUEUED,
        params=params or {},
    )
    async with AsyncSessionLocal() as s:
        s.add(job)
        await s.commit()
        await s.refresh(job)
    return job


async def get_job(job_id: str) -> ComputeJob | None:
    async with AsyncSessionLocal() as s:
        return await s.get(ComputeJob, job_id)


async def update_job(job_id: str, **fields) -> None:
    async with AsyncSessionLocal() as s:
        job = await s.get(ComputeJob, job_id)
        if job is None:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        await s.commit()


async def count_active_jobs() -> int:
    async with AsyncSessionLocal() as s:
        res = await s.execute(
            select(func.count()).select_from(ComputeJob).where(ComputeJob.status.in_(ACTIVE_STATES))
        )
        return int(res.scalar() or 0)


async def daily_cost_usd() -> float:
    """Sum of estimated cost for jobs created since UTC-midnight today."""
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    async with AsyncSessionLocal() as s:
        res = await s.execute(
            select(func.coalesce(func.sum(ComputeJob.est_cost_usd), 0.0)).where(
                ComputeJob.created_at >= start
            )
        )
        return float(res.scalar() or 0.0)


async def active_job_ids() -> set[str]:
    async with AsyncSessionLocal() as s:
        res = await s.execute(select(ComputeJob.id).where(ComputeJob.status.in_(ACTIVE_STATES)))
        return {row[0] for row in res.all()}


async def list_running_jobs() -> list[ComputeJob]:
    async with AsyncSessionLocal() as s:
        res = await s.execute(select(ComputeJob).where(ComputeJob.status == RUNNING))
        return list(res.scalars().all())


async def list_recent_jobs(user_id: str | None, limit: int = 20) -> list[ComputeJob]:
    """A user's recent jobs (running + finished), newest first — for the
    header Jobs tray + on-load re-attach."""
    async with AsyncSessionLocal() as s:
        q = select(ComputeJob).order_by(ComputeJob.created_at.desc()).limit(limit)
        if user_id:
            q = q.where(ComputeJob.user_id == user_id)
        res = await s.execute(q)
        return list(res.scalars().all())
