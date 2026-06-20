"""SPPARKS grain-growth parser + script-builder tests (no Daytona needed).

Validates parse_spparks_result against a synthetic LAMMPS-style dump: connected-
component grain counting (not distinct-spin), the site→type header rename, the
dimensionless-by-default / µm-with-domain behavior, and the qualitative
calibration contract. Also checks the script builder clamps + self-bootstraps.
"""
import pytest

from apps.api.compute.calibration import validate_calibration
from apps.api.ml.microstructure.grain_growth import (
    build_spparks_script,
    parse_spparks_result,
)


def _synthetic_dump(spin_col: str = "site") -> bytes:
    """4×4×2 grid, left half spin=10, right half spin=20 → exactly 2 grains."""
    lines = ["ITEM: TIMESTEP", "800", "ITEM: NUMBER OF ATOMS", "32",
             "ITEM: BOX BOUNDS", "0 4", "0 4", "0 2",
             f"ITEM: ATOMS id {spin_col} x y z"]
    aid = 1
    for z in range(2):
        for y in range(4):
            for x in range(4):
                spin = 10 if x < 2 else 20
                lines.append(f"{aid} {spin} {x}.5 {y}.5 {z}.5")
                aid += 1
    return ("\n".join(lines) + "\n").encode()


def test_grain_count_is_connected_components():
    res = parse_spparks_result({"voxels": _synthetic_dump()}, n_sweeps=800)
    assert res["grain_count"] == 2          # two connected regions, not 2 spins by luck
    assert res["grid"] == [4, 4, 2]
    assert res["calibration"] == "qualitative"
    assert res["png_base64"]
    # MC-time honesty warning is always present
    assert any("not physical time" in w.lower() or "not calibrated" in w.lower()
               for w in res["warnings"])
    validate_calibration(res)


def test_site_column_rename_handled():
    res = parse_spparks_result({"voxels": _synthetic_dump(spin_col="type")}, n_sweeps=800)
    assert res["grain_count"] == 2


def test_dimensionless_by_default_um_with_domain():
    bare = parse_spparks_result({"voxels": _synthetic_dump()}, n_sweeps=800)
    assert "mean_grain_size_um" not in bare
    assert bare["mean_grain_size_voxels"] == pytest.approx(3.126, abs=0.01)

    scaled = parse_spparks_result({"voxels": _synthetic_dump()}, n_sweeps=800, domain_um=4.0)
    assert scaled["voxel_um"] == pytest.approx(1.0, abs=1e-6)   # 4 µm / 4 voxels
    assert scaled["mean_grain_size_um"] == pytest.approx(3.126, abs=0.01)
    # even with a length scale, time stays uncalibrated → extra warning
    assert any("uncalibrated" in w.lower() for w in scaled["warnings"])


def test_empty_dump_raises():
    with pytest.raises(ValueError):
        parse_spparks_result({"voxels": b""}, n_sweeps=800)


def test_build_script_clamps_and_bootstraps():
    body = build_spparks_script({"grid": 9999, "sweeps": 99999})
    assert "0 64 0 64 0 64" in body          # grid clamped to MAX_GRID
    assert "run              2000.0" in body  # sweeps clamped to MAX_SWEEPS
    assert "command -v spk_serial" in body    # self-bootstrap guard
    assert "app_style        potts 1000" in body  # fixed nspins, NOT grid^3
    assert "set              site range 1 1000" in body
    assert "dump             voxels text" in body
