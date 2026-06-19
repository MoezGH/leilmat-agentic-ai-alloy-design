"""Provider-agnostic cloud-sandbox runner + a Daytona implementation.

Everything Daytona-specific lives behind the ``CloudRunner`` interface so a
future outage / price change / second provider doesn't ripple through the
codebase.  The lifecycle encoded here is exactly the one the de-risk spike
(2026-06-18) proved works:

    create (from snapshot) → create_session → execute_session_command(
        run_async=True) → poll a job-written rc-file → fs.download_file →
        delete

Two hard-won lessons from the spike are baked in:

1. **Completion is signalled by a job-written rc-file, never the SDK's async
   ``exit_code``** — that field only reliably populates on success (it stayed
   ``null`` forever on a non-zero exit).  Every job body is wrapped so its true
   exit code lands in ``RC_PATH``; :meth:`poll` reads that.
2. **Pipelines must not mask failures** — the wrapper sets ``set -o pipefail``
   (a ``| tail`` once swallowed an apt failure and the job ran on regardless).

The runner holds no durable state; the orchestrator drives the loop and
persists job state to Postgres.  Sandboxes are tagged ``{LABEL_KEY: job_id}``
so the reaper can sweep orphans without touching the user's other sandboxes.
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Paths inside the sandbox the wrapper writes to.
RC_PATH = "/tmp/leilmat_job.rc"
LOG_PATH = "/tmp/leilmat_job.log"
_SESSION_ID = "leilmat-job"


def wrap_job_script(body: str) -> str:
    """Wrap a plain bash body so its true exit code lands in ``RC_PATH``.

    The body runs under ``set -e`` + ``set -o pipefail`` inside a function so
    that a failure returns from the function (rather than killing the shell
    before we can record the code).  All stdout/stderr is captured to
    ``LOG_PATH`` for post-mortem download.
    """
    return (
        "run_job() {\n"
        "  set -e\n"
        "  set -o pipefail\n"
        f"{body}\n"
        "}\n"
        f"run_job > {LOG_PATH} 2>&1\n"
        f"echo $? > {RC_PATH}\n"
    )


@dataclass
class JobHandle:
    """Opaque per-job reference the orchestrator threads through the runner."""
    sandbox_id: str
    session_id: str
    cmd_id: str | None
    _sandbox: object  # provider SDK sandbox object


@dataclass
class PollResult:
    state: str          # "running" | "done" | "failed"
    rc: int | None = None


class CloudRunner(ABC):
    """Minimal surface every cloud-sandbox provider must implement."""

    @abstractmethod
    async def submit(self, body: str, *, job_id: str, snapshot: str | None = None) -> JobHandle:
        ...

    @abstractmethod
    async def poll(self, handle: JobHandle) -> PollResult:
        ...

    @abstractmethod
    async def download(self, handle: JobHandle, remote_path: str) -> bytes | None:
        ...

    @abstractmethod
    async def fetch_log(self, handle: JobHandle) -> str:
        ...

    @abstractmethod
    async def cleanup(self, handle: JobHandle) -> None:
        ...

    @abstractmethod
    async def sweep_orphans(self, alive_job_ids: set[str]) -> int:
        ...

    async def aclose(self) -> None:  # pragma: no cover - optional
        return None


class DaytonaRunner(CloudRunner):
    """Daytona-backed runner using the ``daytona`` async SDK (~v0.184)."""

    LABEL_KEY = "leilmat"

    # Non-snapshot sandboxes are created from this base image WITH explicit
    # resources — the platform default allocation is too CPU-throttled for
    # heavier jobs (a SPPARKS Monte-Carlo run crawled at the default tier).
    DEFAULT_IMAGE = "debian:13"

    def __init__(
        self,
        api_key: str,
        *,
        default_snapshot: str | None = None,
        wall_cap_s: int = 900,
        create_timeout_s: int = 180,
        cpu: int = 4,
        memory: int = 8,
        disk: int = 10,
    ) -> None:
        self._api_key = api_key
        self._default_snapshot = default_snapshot or None
        self._wall_cap_s = wall_cap_s
        self._create_timeout_s = create_timeout_s
        self._cpu = cpu
        self._memory = memory
        self._disk = disk
        self._client = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self):
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    # Lazy import so importing this module (e.g. in tests)
                    # doesn't hard-require the SDK to be installed.
                    from daytona import AsyncDaytona, DaytonaConfig
                    self._client = AsyncDaytona(DaytonaConfig(api_key=self._api_key))
        return self._client

    async def submit(self, body: str, *, job_id: str, snapshot: str | None = None) -> JobHandle:
        from daytona import CreateSandboxFromSnapshotParams, SessionExecuteRequest

        d = await self._get_client()
        snap = snapshot or self._default_snapshot

        # Snapshot path = fast (toolchain pre-baked).  But custom snapshots can
        # land on a constrained runner pool ("No available runners"); when that
        # happens, fall back to the default image — the job body self-bootstraps
        # its toolchain, so it still completes (just slower).  The snapshot is a
        # latency optimization, never a hard dependency.
        sandbox = None
        if snap:
            try:
                sandbox = await d.create(
                    CreateSandboxFromSnapshotParams(snapshot=snap),
                    timeout=self._create_timeout_s,
                )
            except Exception as exc:
                logger.warning(
                    "[daytona] snapshot '%s' launch failed (%s) — falling back "
                    "to default image (self-bootstrap)", snap, exc,
                )
                sandbox = None
        if sandbox is None:
            # Non-snapshot create: explicit resources so the sandbox gets real
            # CPU/RAM (the platform default tier is too throttled for heavy
            # builds + Monte-Carlo runs).
            from daytona import CreateSandboxFromImageParams, Resources
            sandbox = await d.create(
                CreateSandboxFromImageParams(
                    image=self.DEFAULT_IMAGE,
                    resources=Resources(cpu=self._cpu, memory=self._memory, disk=self._disk),
                ),
                timeout=self._create_timeout_s,
            )

        # Tag for the reaper, and set an autostop backstop so even a fully
        # orphaned sandbox self-stops well after the wall-clock cap.
        try:
            await sandbox.set_labels({self.LABEL_KEY: job_id})
        except Exception as exc:  # pragma: no cover
            logger.warning("[daytona] set_labels failed for %s: %s", job_id, exc)
        try:
            autostop_min = max(5, (self._wall_cap_s // 60) + 5)
            await sandbox.set_autostop_interval(autostop_min)
        except Exception as exc:  # pragma: no cover
            logger.warning("[daytona] set_autostop failed for %s: %s", job_id, exc)

        await sandbox.process.create_session(_SESSION_ID)
        resp = await sandbox.process.execute_session_command(
            _SESSION_ID,
            SessionExecuteRequest(command=wrap_job_script(body), run_async=True),
            timeout=self._wall_cap_s,
        )
        cmd_id = (
            getattr(resp, "cmd_id", None)
            or getattr(resp, "command_id", None)
            or getattr(resp, "id", None)
        )
        return JobHandle(
            sandbox_id=getattr(sandbox, "id", "?"),
            session_id=_SESSION_ID,
            cmd_id=cmd_id,
            _sandbox=sandbox,
        )

    @staticmethod
    def _exec_text(resp) -> str:
        return (getattr(resp, "result", None) or getattr(resp, "stdout", "") or "") or ""

    async def poll(self, handle: JobHandle) -> PollResult:
        # Read the job-written rc-file. Empty == still running.  This is the
        # robust signal; the SDK's async exit_code is unreliable on failure.
        # Transient exec errors (Daytona API hiccups while the sandbox is busy
        # compiling) are treated as "still running" — a real completion writes
        # the rc-file and a later poll catches it; the wall-clock cap bounds a
        # genuinely dead sandbox.
        try:
            r = await handle._sandbox.process.exec(f"cat {RC_PATH} 2>/dev/null", timeout=30)
        except Exception as exc:
            logger.debug("[daytona] poll transient exec error (treating as running): %s", exc)
            return PollResult("running", None)
        out = self._exec_text(r).strip()
        if out == "":
            return PollResult("running", None)
        try:
            rc = int(out.split()[0])
        except (ValueError, IndexError):
            rc = 1
        return PollResult("done" if rc == 0 else "failed", rc)

    async def download(self, handle: JobHandle, remote_path: str) -> bytes | None:
        try:
            return await handle._sandbox.fs.download_file(remote_path)
        except Exception as exc:
            logger.warning("[daytona] download %s failed: %s", remote_path, exc)
            return None

    async def fetch_log(self, handle: JobHandle) -> str:
        try:
            r = await handle._sandbox.process.exec(f"cat {LOG_PATH} 2>/dev/null", timeout=30)
            return self._exec_text(r)
        except Exception:  # pragma: no cover
            return ""

    async def cleanup(self, handle: JobHandle) -> None:
        try:
            d = await self._get_client()
            await d.delete(handle._sandbox)
        except Exception as exc:
            logger.warning("[daytona] cleanup of %s failed: %s", handle.sandbox_id, exc)

    async def sweep_orphans(self, alive_job_ids: set[str]) -> int:
        """Delete sandboxes we own (carry our LABEL_KEY) that are no longer
        tracked by a live job and are still consuming resources.

        Only ever touches sandboxes whose label KEY is ``LABEL_KEY`` — the
        user's unrelated sandboxes (different label keys) are never deleted.
        """
        d = await self._get_client()
        swept = 0
        try:
            async for s in d.list():
                labels = getattr(s, "labels", {}) or {}
                job_id = labels.get(self.LABEL_KEY)
                if job_id is None or job_id in alive_job_ids:
                    continue
                state = str(getattr(s, "state", "")).lower()
                # Only reap things still costing money; leave already
                # stopped/archived/destroyed sandboxes alone.
                if any(tok in state for tok in ("start", "running", "creat", "pending", "error")):
                    try:
                        await d.delete(s)
                        swept += 1
                        logger.info("[daytona] reaped orphan sandbox %s (job %s)",
                                    getattr(s, "id", "?"), job_id)
                    except Exception as exc:  # pragma: no cover
                        logger.warning("[daytona] reap delete failed: %s", exc)
        except Exception as exc:  # pragma: no cover
            logger.warning("[daytona] sweep_orphans failed: %s", exc)
        return swept

    async def aclose(self) -> None:  # pragma: no cover
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass


# ── Process-wide singleton ─────────────────────────────────────────────
_RUNNER: CloudRunner | None = None


def get_runner() -> CloudRunner | None:
    """Return the shared runner, or ``None`` when cloud compute is dark
    (no ``DAYTONA_API_KEY`` configured)."""
    global _RUNNER
    if _RUNNER is not None:
        return _RUNNER
    from apps.api.config import settings
    if not settings.daytona_api_key:
        return None
    _RUNNER = DaytonaRunner(
        settings.daytona_api_key,
        default_snapshot=settings.daytona_snapshot_neper or None,
        wall_cap_s=settings.daytona_job_wall_cap_s,
    )
    return _RUNNER


async def aclose_runner() -> None:
    """Close the shared runner's client (called from the app lifespan)."""
    global _RUNNER
    if _RUNNER is not None:
        await _RUNNER.aclose()
        _RUNNER = None
