"""
SQLAlchemy engine + Base — kept around as a forward-compatibility hook.

**As of Phase E (2026-05-24), LeilMat does NOT persist user data through
SQLAlchemy.**  User-owned design sessions live in **Supabase Postgres**
via the ``design_sessions`` table + row-level security, accessed
directly from the frontend through ``apps/web/services/sessionService.ts``.
This mirrors LeilFlowsheet's projects-table pattern.

What stays in this file:
  * ``engine`` / ``AsyncSessionLocal`` — async SQLAlchemy infrastructure
    available if a future feature needs a *backend-owned* table
    (audit logs, analytics, model-cache metadata, …) that doesn't
    belong in Supabase.
  * ``Base`` — DeclarativeBase parent for any such future ORM models.
  * ``init_db()`` — startup hook called from ``apps/api/main.py`` lifespan;
    today it creates zero tables because no model imports ``Base``.
    Left in place so adding a new ORM model is a one-line import diff
    rather than re-wiring the lifespan.

What got removed in Phase E:
  * ``apps/api/data/models.py`` and its three SQLAlchemy classes
    (``DesignSession`` / ``SavedComposition`` / ``ChatMessage``).  Those
    tables were never created (init_db silently failed because no
    Postgres was running) and Supabase now owns that data.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from apps.api.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Startup hook — creates any tables registered against Base.

    Today no model imports Base, so this is a no-op.  Kept wired up so
    a future ORM model lands without touching ``apps/api/main.py``.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
