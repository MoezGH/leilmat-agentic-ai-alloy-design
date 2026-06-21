"""Build (once) a Daytona snapshot with DAMASK pre-installed.

    python -m apps.api.compute.snapshots.damask            # build + print id
    python -m apps.api.compute.snapshots.damask --check     # list existing

DAMASK (crystal-plasticity spectral/FFT solver) is heavy to build from source
because of its PETSc dependency.  conda-forge ships a *precompiled* grid solver
(``damask-grid``, PETSc bundled) plus the ``python-damask`` pre/post-processing
package, so the snapshot is a conda install rather than a multi-hour compile.

Baking it into a snapshot means each CPFEM stress-strain job launches in
seconds and runs ONLY the spectral solve.  After building, set in .env:
``DAYTONA_SNAPSHOT_DAMASK=leilmat-damask-v1``.  Unlike Neper/SPPARKS there is
NO runtime self-bootstrap fallback (the conda env is too large to install per
job), so the snapshot is required for the feature to run.

Reads DAYTONA_API_KEY from .env; never prints it.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import pathlib

SNAPSHOT_NAME = "leilmat-damask-v1"

# Base off miniforge (conda + conda-forge preconfigured) and install the
# precompiled grid solver + python API.  python-damask pulls numpy/scipy/h5py/
# pyyaml.  NO matplotlib here — the sandbox postprocesses the HDF5 to a small
# σ-ε CSV with python-damask, and the API container renders the flow-curve PNG
# (keeps the conda env under the Tier-2 10 GB/sandbox disk cap).
_BUILD_COMMANDS = [
    "mamba --version || conda --version",
    "mamba install -y -c conda-forge damask-grid python-damask",
    "mamba clean -y --all || true",                       # shrink the layer
    # Hard verification — the binary AND the python API must both be present.
    "command -v DAMASK_grid",
    "DAMASK_grid --help 2>&1 | head -3 || true",
    "python -c \"import damask, numpy, h5py, yaml; print('python-damask', damask.version)\"",
    "du -sh /opt/conda 2>/dev/null || true",              # report env size
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
    # miniforge3 = conda + mamba + conda-forge default channel, no manual setup.
    image = Image.base("condaforge/miniforge3:latest").run_commands(*_BUILD_COMMANDS)
    print(f"[snapshot] building {SNAPSHOT_NAME} (conda install of DAMASK ~5-15 min)…")
    await d.snapshot.create(
        CreateSnapshotParams(
            name=SNAPSHOT_NAME,
            image=image,
            # Tier-2 ceilings: 4 vCPU and 10 GB disk per sandbox (both hard
            # limits). The trimmed conda env must fit in 10 GB.
            resources=Resources(cpu=4, memory=8, disk=10),
        ),
        on_logs=lambda line: print("   ", line.rstrip()),
        timeout=2400,
    )
    print(f"\n[snapshot] done. Set in .env:\n    DAYTONA_SNAPSHOT_DAMASK={SNAPSHOT_NAME}")
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
