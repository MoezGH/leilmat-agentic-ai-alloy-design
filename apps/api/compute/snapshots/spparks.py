"""Build (once) a Daytona snapshot with SPPARKS pre-compiled.

    python -m apps.api.compute.snapshots.spparks            # build + print id
    python -m apps.api.compute.snapshots.spparks --check     # list existing

The SPPARKS source build takes several minutes on a small sandbox; baking it
into a snapshot means each grain-growth job launches in ~1-2 s and runs ONLY
the Monte-Carlo sweep (no build). After building, set in .env:
``DAYTONA_SNAPSHOT_SPPARKS=leilmat-spparks-v1``. The grow job still works
WITHOUT the snapshot (it self-bootstraps SPPARKS) — this is pure speed-up.

Reads DAYTONA_API_KEY from .env; never prints it. Uses make -j4 (NOT $(nproc):
the host reports 64 cores and 64 parallel g++ OOM-kills the small sandbox).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import pathlib

# mpi-v1: SPPARKS built with MPI (spk_mpi) + -O3. MPI gives near-linear
# multi-core speedup via spatial domain decomposition — the real lever for
# big grids (the Potts sweep is O(nspins) per site, so parallelism, not -O,
# is what scales). OpenMPI is the MPI provider.
SNAPSHOT_NAME = "leilmat-spparks-mpi-v3"

_BUILD_COMMANDS = [
    "export DEBIAN_FRONTEND=noninteractive",
    "apt-get update -qq",
    "apt-get install -y -qq build-essential g++ make git libopenmpi-dev openmpi-bin",
    "git clone --depth 1 https://github.com/spparks/spparks.git /opt/spparks",
    # Bump optimization (-O → -O3) AND disable JPEG (the MPI Makefile compiles
    # dump_image with -DSPPARKS_JPEG but doesn't link -ljpeg → link error; we
    # render PNGs ourselves and never use SPPARKS image dumps, so strip it).
    "sed -i '/^CCFLAGS/s/-O /-O3 /' /opt/spparks/src/MAKE/Makefile.mpi",
    "sed -i 's/-DSPPARKS_JPEG//g' /opt/spparks/src/MAKE/Makefile.mpi",
    "grep -E '^CCFLAGS|JPEG' /opt/spparks/src/MAKE/Makefile.mpi",
    "cd /opt/spparks/src && make -j4 mpi",
    "ln -sf /opt/spparks/src/spk_mpi /usr/local/bin/spk_mpi",
    "command -v spk_mpi && mpirun --version | head -1",
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
    print(f"[snapshot] building {SNAPSHOT_NAME} (SPPARKS source build ~3-6 min)…")
    await d.snapshot.create(
        CreateSnapshotParams(
            name=SNAPSHOT_NAME,
            image=image,
            resources=Resources(cpu=4, memory=8, disk=10),
        ),
        on_logs=lambda line: print("   ", line.rstrip()),
        timeout=1200,
    )
    print(f"\n[snapshot] done. Set in .env:\n    DAYTONA_SNAPSHOT_SPPARKS={SNAPSHOT_NAME}")
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
