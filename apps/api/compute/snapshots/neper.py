"""Build (once) a Daytona snapshot with Neper + POV-Ray pre-compiled.

Run manually whenever the recipe changes:

    python -m apps.api.compute.snapshots.neper            # build + print id
    python -m apps.api.compute.snapshots.neper --check     # just list existing

The Neper source build takes ~100 s; baking it into a snapshot amortizes that
so each tessellation job launches in ~1 s and runs only the ~6 s tessellation.
After building, copy the printed name into ``.env`` as
``DAYTONA_SNAPSHOT_NEPER=<name>`` so the runner launches from it.  The feature
still works WITHOUT a snapshot (the job self-bootstraps Neper) — this is purely
a latency/cost optimization.

Reads ``DAYTONA_API_KEY`` from ``.env``; never prints it.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import pathlib

# Bump the version suffix whenever the build recipe below changes so old
# snapshots don't get silently reused.
SNAPSHOT_NAME = "leilmat-neper-v1"

_BUILD_COMMANDS = [
    "export DEBIAN_FRONTEND=noninteractive",
    "apt-get update -qq",
    # libscotch-dev/OpenMPI deliberately omitted — not needed for -T/-V.
    "apt-get install -y -qq build-essential cmake libgsl-dev libnlopt-dev povray git",
    "cd /tmp && git clone --depth 1 https://github.com/neperfepx/neper.git",
    "cd /tmp/neper/src && mkdir -p build && cd build && cmake .. && make -j4 && make install",
    "neper --version",
]


def _load_env() -> None:
    env = pathlib.Path(__file__).resolve().parents[4] / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


async def _build() -> None:
    from daytona import AsyncDaytona, CreateSnapshotParams, Image, Resources

    d = AsyncDaytona()
    image = Image.base("debian:13").run_commands(*_BUILD_COMMANDS)
    print(f"[snapshot] building {SNAPSHOT_NAME} (Neper source build ~2-3 min)…")
    await d.snapshot.create(
        CreateSnapshotParams(
            name=SNAPSHOT_NAME,
            image=image,
            resources=Resources(cpu=2, memory=4, disk=8),
        ),
        on_logs=lambda line: print("   ", line.rstrip()),
        timeout=900,
    )
    print(f"\n[snapshot] done. Set in .env:\n    DAYTONA_SNAPSHOT_NEPER={SNAPSHOT_NAME}")
    await d.close()


async def _check() -> None:
    from daytona import AsyncDaytona

    d = AsyncDaytona()
    snaps = await d.snapshot.list()
    items = getattr(snaps, "items", None) or getattr(snaps, "snapshots", None) or snaps
    print("[snapshot] existing snapshots:")
    for s in items or []:
        print("   ", getattr(s, "name", s))
    await d.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="list snapshots, don't build")
    args = ap.parse_args()
    _load_env()
    if not os.environ.get("DAYTONA_API_KEY"):
        raise SystemExit("DAYTONA_API_KEY not found in .env")
    asyncio.run(_check() if args.check else _build())


if __name__ == "__main__":
    main()
