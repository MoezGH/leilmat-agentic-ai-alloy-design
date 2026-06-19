"""SPPARKS Monte-Carlo Potts grain-growth job: bash builder + dump parser.

SPPARKS (Sandia, GPL) evolves a 3D Potts model — the canonical mesoscale model
of curvature-driven GRAIN GROWTH. Unlike Neper (a static synthetic geometry),
this simulates grains *coarsening over Monte-Carlo time*. That is exactly why
it ships ``calibration="qualitative"``:

  MC sweeps are NOT physical seconds and the lattice constant is dimensionless,
  so the coarsening STATE (and thus absolute grain size) is not calibrated to a
  physical anneal. Honest claims: statistical morphology, grain COUNT, grain-
  size DISTRIBUTION shape, equiaxed coarsening trend. NOT: physical µm/time/ASTM.

Recipe (build + input script) was researched and adversarially verified against
the official SPPARKS docs + examples/potts/in.potts. The SPPARKS image dump is
deliberately NOT used (PNG is impossible from SPPARKS; .jpg needs a fragile
build flag that can abort the whole run) — we render the PNG ourselves with
matplotlib from the voxel field. Pure string-building + parsing; no Daytona
import, so it is unit-testable against a synthetic dump.
"""
from __future__ import annotations

import base64
import io
from typing import Callable

MIN_GRID = 16
MAX_GRID = 128       # caps dump size (N^3 sites) + runtime
MIN_SWEEPS = 50
MAX_SWEEPS = 5000

ARTIFACTS = {"voxels": "/tmp/grain_final.txt"}

# Stock source build (no JPEG patch → works on any arch, no image-dump abort).
# Idempotent: skips when spk_serial already exists (e.g. a warm snapshot).
_SPPARKS_BOOTSTRAP = (
    "if ! command -v spk_serial >/dev/null 2>&1 && [ ! -x /opt/spparks/src/spk_serial ]; then\n"
    "  export DEBIAN_FRONTEND=noninteractive\n"
    "  SUDO=; if [ \"$(id -u)\" != 0 ] && command -v sudo >/dev/null 2>&1; then SUDO=sudo; fi\n"
    "  $SUDO apt-get update -qq\n"
    "  $SUDO apt-get install -y -qq build-essential g++ make git\n"
    "  $SUDO rm -rf /opt/spparks\n"
    "  $SUDO git clone --depth 1 https://github.com/spparks/spparks.git /opt/spparks\n"
    "  $SUDO chown -R \"$(id -u)\":\"$(id -g)\" /opt/spparks\n"
    # -j4 (NOT $(nproc)): nproc reports the HOST's cores, not the sandbox's
    # small allocation — 64 parallel g++ OOM-kills the container (the build
    # dies and the sandbox loses its IP). Bounded parallelism builds reliably.
    "  cd /opt/spparks/src && make -j4 serial\n"
    "  $SUDO ln -sf /opt/spparks/src/spk_serial /usr/local/bin/spk_serial\n"
    "fi\n"
    "command -v spk_serial >/dev/null 2>&1 || sudo ln -sf /opt/spparks/src/spk_serial /usr/local/bin/spk_serial\n"
)


def _clamp(v, lo, hi, default):
    try:
        v = int(v)
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


def _input_script(grid: int, sweeps: int) -> str:
    q = grid ** 3  # Q >= site count → every site starts a distinct grain
    return (
        f"seed             56789\n"
        f"app_style        potts {q}\n"
        f"dimension        3\n"
        f"lattice          sc/26n 1.0\n"
        f"region           box block 0 {grid} 0 {grid} 0 {grid}\n"
        f"create_box       box\n"
        f"create_sites     box\n"
        f"set              site range 1 {q}\n"
        f"sweep            random\n"
        f"sector           yes\n"
        f"temperature      0.0\n"
        f"diag_style       energy\n"
        f"stats            100.0\n"
        f"dump             voxels text {sweeps}.0 /tmp/dump.potts.*.txt id site x y z\n"
        f"dump_modify      voxels sort id\n"
        f"run              {sweeps}.0\n"
    )


def build_spparks_script(params: dict) -> str:
    grid = _clamp(params.get("grid", 64), MIN_GRID, MAX_GRID, 64)
    sweeps = _clamp(params.get("sweeps", 1500), MIN_SWEEPS, MAX_SWEEPS, 1500)
    script = _input_script(grid, sweeps)
    return (
        _SPPARKS_BOOTSTRAP
        + "cd /tmp\n"
        + "cat > /tmp/in.grain <<'SPKEOF'\n"
        + script
        + "SPKEOF\n"
        + "spk_serial < /tmp/in.grain\n"
        # Each timestep is its own file (the '*' in the dump path); grab the
        # newest = the coarsened final state. Sidesteps filename-format guessing
        # and the "parsed the initial fine state" trap.
        + "cp \"$(ls -t /tmp/dump.potts.*.txt | head -1)\" /tmp/grain_final.txt\n"
        + "ls -la /tmp/grain_final.txt\n"
    )


# ── parsing ────────────────────────────────────────────────────────────

_SPIN_COL_NAMES = ("site", "spin", "i1", "type")


def _parse_dump(text: str):
    """Parse a SPPARKS/LAMMPS-style text dump → (spin, x, y, z) lists.

    Robust to the 'site'→'type' column rename and to coordinate offsets.
    """
    import numpy as np

    lines = text.splitlines()
    spin_i = x_i = y_i = z_i = None
    rows = []
    in_atoms = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("ITEM:"):
            if s.startswith("ITEM: ATOMS"):
                cols = s[len("ITEM: ATOMS"):].split()
                for name in _SPIN_COL_NAMES:
                    if name in cols:
                        spin_i = cols.index(name)
                        break
                x_i, y_i, z_i = cols.index("x"), cols.index("y"), cols.index("z")
                in_atoms = True
            else:
                in_atoms = False  # a new (non-ATOMS) section ends the block
            continue
        if in_atoms and s:
            rows.append(s.split())
    if spin_i is None or not rows:
        raise ValueError("SPPARKS dump: no parseable ATOMS block / spin column")

    arr = np.array(rows)
    spin = arr[:, spin_i].astype(np.int64)
    x = arr[:, x_i].astype(float)
    y = arr[:, y_i].astype(float)
    z = arr[:, z_i].astype(float)
    return spin, x, y, z


def _to_voxel_grid(spin, x, y, z):
    """Map (x,y,z)→spin onto a dense 3D array via coordinate rank (offset-safe)."""
    import numpy as np

    def rank(vals):
        uniq = np.unique(vals)
        idx = {v: i for i, v in enumerate(uniq)}
        return np.array([idx[v] for v in vals]), len(uniq)

    ix, nx = rank(x)
    iy, ny = rank(y)
    iz, nz = rank(z)
    grid = np.zeros((nx, ny, nz), dtype=np.int64)
    grid[ix, iy, iz] = spin
    return grid


def _count_grains_and_sizes(grid):
    """Grain count + per-grain voxel counts via per-spin connected components
    (6-connectivity). Counting distinct spin values would be wrong: a finite Q
    lets distant grains share a spin, and a spin can fragment."""
    import numpy as np
    from scipy import ndimage

    struct = ndimage.generate_binary_structure(3, 1)  # 6-connectivity
    total = 0
    sizes: list[int] = []
    for spin in np.unique(grid):
        mask = grid == spin
        lab, n = ndimage.label(mask, structure=struct)
        if n:
            total += int(n)
            comp = ndimage.sum(np.ones_like(mask), lab, index=range(1, n + 1))
            sizes.extend(int(c) for c in comp)
    return total, np.asarray(sizes, dtype=float)


def _render_slice_png(grid) -> str:
    """Render a mid-depth slice with a shuffled colormap keyed on connected
    component (so two far grains sharing a spin don't render as one blob)."""
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from scipy import ndimage

    sl = grid[:, :, grid.shape[2] // 2]
    struct2 = ndimage.generate_binary_structure(2, 1)
    relabeled = np.zeros_like(sl, dtype=np.int64)
    nxt = 0
    for spin in np.unique(sl):
        lab, n = ndimage.label(sl == spin, structure=struct2)
        lab[lab > 0] += nxt
        relabeled += lab
        nxt += n

    rng = np.random.default_rng(0)
    colors = rng.random((nxt + 1, 3))
    colors[0] = [0.04, 0.05, 0.09]  # background
    cmap = ListedColormap(colors)

    fig, ax = plt.subplots(figsize=(4, 4), dpi=150)
    ax.imshow(relabeled, cmap=cmap, interpolation="nearest")
    ax.axis("off")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def parse_spparks_result(
    downloaded: dict[str, bytes | None],
    *,
    n_sweeps: int,
    domain_um: float | None = None,
) -> dict:
    import numpy as np

    raw = downloaded.get("voxels")
    if not raw:
        raise ValueError("SPPARKS produced no voxel dump.")
    spin, x, y, z = _parse_dump(raw.decode("utf-8", "replace"))
    grid = _to_voxel_grid(spin, x, y, z)
    nx, ny, nz = grid.shape

    grain_count, sizes = _count_grains_and_sizes(grid)
    d_eq = (6.0 * sizes / np.pi) ** (1.0 / 3.0) if sizes.size else np.asarray([])

    def _hist(values):
        bins = min(20, max(5, grain_count // 5))
        counts, edges = np.histogram(values, bins=bins)
        return {"bin_edges": [round(float(e), 4) for e in edges],
                "counts": [int(c) for c in counts]}

    warnings = [
        "Monte-Carlo Potts grain growth: MC sweeps are NOT physical time and the "
        "lattice is dimensionless — the coarsening state and absolute grain size "
        "are not calibrated to a physical anneal. Statistical morphology, grain "
        "count and size-distribution shape are the honest readouts.",
    ]

    result: dict = {
        "grain_count": int(grain_count),
        "n_sweeps": int(n_sweeps),
        "grid": [int(nx), int(ny), int(nz)],
        "dimensionality": "3D",
        "method": "Monte-Carlo Potts grain growth (SPPARKS)",
        "mean_grain_size_voxels": round(float(d_eq.mean()), 3) if d_eq.size else None,
        "size_distribution_voxels": _hist(d_eq) if d_eq.size else None,
        "png_base64": _render_slice_png(grid),
        "source": "spparks_potts",
        "calibration": "qualitative",
        "warnings": warnings,
    }

    if domain_um and d_eq.size:
        voxel_um = float(domain_um) / max(nx, 1)
        result["domain_um"] = float(domain_um)
        result["voxel_um"] = round(voxel_um, 4)
        result["mean_grain_size_um"] = round(float(d_eq.mean()) * voxel_um, 3)
        warnings.append(
            "µm sizes use the supplied domain edge as a length scale, but the "
            "coarsening STATE remains uncalibrated (no physical time mapping); "
            "treat absolute µm sizes as indicative only."
        )
    return result


def make_grain_growth_job(params: dict) -> tuple[str, dict, Callable[[dict], dict]]:
    grid = _clamp(params.get("grid", 64), MIN_GRID, MAX_GRID, 64)
    sweeps = _clamp(params.get("sweeps", 1500), MIN_SWEEPS, MAX_SWEEPS, 1500)
    domain_um = params.get("domain_um")
    body = build_spparks_script({"grid": grid, "sweeps": sweeps})

    def _parse(downloaded: dict) -> dict:
        return parse_spparks_result(downloaded, n_sweeps=sweeps, domain_um=domain_um)

    return body, ARTIFACTS, _parse
