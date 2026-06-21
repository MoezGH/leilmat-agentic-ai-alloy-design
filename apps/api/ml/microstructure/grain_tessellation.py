"""Neper synthetic-polycrystal job: bash builder + .tess/stats parser.

Neper (https://neper.info, GPLv3) is a *geometry/statistics* engine — it
generates a statistically representative polycrystal tessellation from
descriptors (grain count, morphology) and renders it.  It is NOT a physics
predictor of how a microstructure forms.  So results ship
``calibration="deterministic-geometry"``: genuinely quantitative for what
they claim (cell count, normalized size distribution), and explicitly
DIMENSIONLESS unless the caller supplies a physical domain edge length
(``domain_um``) to convert to µm + an ASTM grain number.

The job runs in a Daytona sandbox launched from the pre-baked Neper snapshot.
This module is pure string-building + parsing — no Daytona import — so it is
unit-testable against the real ``.tess`` the spike already produced.
"""
from __future__ import annotations

import base64
import math
from typing import Callable

MIN_GRAINS = 8
MAX_GRAINS = 2000
_VALID_MORPHO = {"voronoi", "graingrowth", "gg"}

_OUT = "/tmp/out"
ARTIFACTS = {"tess": f"{_OUT}.tess", "png": f"{_OUT}.png", "stats": f"{_OUT}.stcell"}

# Self-bootstrap: build Neper from source if the sandbox doesn't already have
# it.  This makes the feature work from the plain default image (~100 s first
# run) so shipping doesn't block on the snapshot; when launched from the
# pre-baked Neper snapshot, `command -v neper` succeeds and this is a no-op.
# (Skip libscotch-dev / OpenMPI — not needed for -T/-V; speeds the build.)
_NEPER_BOOTSTRAP = (
    "if ! command -v neper >/dev/null 2>&1; then\n"
    "  export DEBIAN_FRONTEND=noninteractive\n"
    "  SUDO=; if [ \"$(id -u)\" != 0 ] && command -v sudo >/dev/null 2>&1; then SUDO=sudo; fi\n"
    "  $SUDO apt-get update -qq\n"
    "  $SUDO apt-get install -y -qq build-essential cmake libgsl-dev libnlopt-dev povray git\n"
    "  cd /tmp && rm -rf neper && git clone --depth 1 https://github.com/neperfepx/neper.git\n"
    "  cd /tmp/neper/src && mkdir -p build && cd build\n"
    "  cmake .. >/dev/null && make -j4 >/dev/null && $SUDO make install >/dev/null\n"
    "  cd /tmp\n"
    "fi\n"
)


def _clamp_n(n) -> int:
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 100
    return max(MIN_GRAINS, min(MAX_GRAINS, n))


def build_neper_script(params: dict) -> str:
    """Emit the bash body that generates + renders a polycrystal.

    ``-statcell diameq`` writes one equivalent-diameter per cell (in units of
    the unit-cube edge) to ``out.stcell``; ``-V … -print`` renders ``out.png``
    via POV-Ray.  Default morphology is fast Voronoi; ``graingrowth`` produces
    realistic curved grains but is a slow optimizer (bounded by the wall cap).
    """
    n = _clamp_n(params.get("n_grains", 100))
    morpho = str(params.get("morpho", "voronoi")).lower()
    if morpho not in _VALID_MORPHO:
        morpho = "voronoi"
    return (
        _NEPER_BOOTSTRAP
        + f"neper -T -n {n} -morpho {morpho} -dim 3 -o {_OUT} -statcell diameq\n"
        + f"neper -V {_OUT}.tess -datacellcol id -imagesize 700:700 -print {_OUT}\n"
        + f"ls -la {_OUT}.*\n"
    )


def _count_cells_from_tess(tess: bytes | None) -> int:
    if not tess:
        return 0
    try:
        lines = tess.decode("utf-8", "replace").splitlines()
    except Exception:
        return 0
    for i, line in enumerate(lines):
        if line.strip() == "**cell" and i + 1 < len(lines):
            try:
                return int(lines[i + 1].strip())
            except ValueError:
                return 0
    return 0


def _parse_seeds(tess: bytes | None) -> list[list[float]]:
    """Extract the Voronoi seed coordinates from a Neper ``.tess`` ``*seed``
    block (``<id> x y z weight``, already normalized to the unit cube).

    These let the CPFEM stress-strain feature rebuild the *identical* Voronoi
    tessellation in DAMASK (``GeomGrid.from_Voronoi_tessellation``) — i.e. run
    the user's actual grain structure, not a fresh random one.
    """
    if not tess:
        return []
    try:
        lines = tess.decode("utf-8", "replace").splitlines()
    except Exception:
        return []
    seeds: list[list[float]] = []
    grab = False
    for line in lines:
        s = line.strip()
        if s == "*seed":
            grab = True
            continue
        if grab:
            if s.startswith("*"):           # next subsection → seed block done
                break
            p = s.split()
            if len(p) >= 4:
                try:
                    seeds.append([round(float(p[1]), 5), round(float(p[2]), 5),
                                  round(float(p[3]), 5)])
                except ValueError:
                    continue
    return seeds


def _parse_diameq(stats: bytes | None) -> list[float]:
    if not stats:
        return []
    out: list[float] = []
    for line in stats.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(float(line.split()[0]))
        except ValueError:
            continue
    return out


def parse_neper_result(
    downloaded: dict[str, bytes | None],
    *,
    n_requested: int | None = None,
    morpho: str = "voronoi",
    domain_um: float | None = None,
) -> dict:
    """Turn downloaded artifacts into the result dict the card renders."""
    import numpy as np

    tess = downloaded.get("tess")
    png = downloaded.get("png")
    stats = downloaded.get("stats")
    warnings: list[str] = []

    dia = _parse_diameq(stats)
    grain_count = len(dia) or _count_cells_from_tess(tess)
    if grain_count == 0:
        raise ValueError("Neper produced no cells (empty .tess and .stcell).")

    arr = np.asarray(dia, dtype=float) if dia else np.asarray([])

    def _hist(values):
        bins = min(20, max(5, grain_count // 5))
        counts, edges = np.histogram(values, bins=bins)
        return {"bin_edges": [round(float(e), 5) for e in edges],
                "counts": [int(c) for c in counts]}

    result: dict = {
        "grain_count": int(grain_count),
        "morpho": morpho,
        "dimensionality": "3D",
        "mean_grain_size_normalized": round(float(arr.mean()), 5) if arr.size else None,
        "std_grain_size_normalized": round(float(arr.std()), 5) if arr.size else None,
        "size_distribution_normalized": _hist(arr) if arr.size else None,
        "png_base64": base64.b64encode(png).decode("ascii") if png else None,
        "source": "neper",
        "calibration": "deterministic-geometry",
        "warnings": warnings,
        # Voronoi seeds (unit-cube coords) — the bridge to CPFEM stress-strain:
        # let that feature rebuild THIS exact tessellation as its RVE.
        "seeds": _parse_seeds(tess),
    }

    if domain_um and arr.size:
        d_um = arr * float(domain_um)
        mean_um = float(d_um.mean())
        # ASTM E112 grain number, same form as apps/api/ml/calphad/ttt.py:256.
        astm = 1.0 + math.log2(64.5 ** 2 / max(mean_um, 1.0) ** 2)
        result["domain_um"] = float(domain_um)
        result["mean_grain_size_um"] = round(mean_um, 3)
        result["astm_grain_number"] = round(astm, 2)
        result["size_distribution_um"] = _hist(d_um)
    else:
        warnings.append(
            "Grain sizes are DIMENSIONLESS (fraction of the unit-cube edge). "
            "Supply domain_um (physical cube edge in µm) to get absolute size "
            "in µm and an ASTM grain number."
        )

    if png is None:
        warnings.append("Render PNG missing — tessellation succeeded but visualization failed.")
    if n_requested and grain_count != n_requested:
        warnings.append(f"Requested {n_requested} grains; tessellation has {grain_count}.")

    return result


def make_tessellation_job(params: dict) -> tuple[str, dict, Callable[[dict], dict]]:
    """Return ``(body, artifacts, parse)`` ready to hand to ``submit_job``."""
    n = _clamp_n(params.get("n_grains", 100))
    morpho = str(params.get("morpho", "voronoi")).lower()
    if morpho not in _VALID_MORPHO:
        morpho = "voronoi"
    domain_um = params.get("domain_um")
    body = build_neper_script({"n_grains": n, "morpho": morpho})

    def _parse(downloaded: dict) -> dict:
        return parse_neper_result(
            downloaded, n_requested=n, morpho=morpho, domain_um=domain_um
        )

    return body, ARTIFACTS, _parse
