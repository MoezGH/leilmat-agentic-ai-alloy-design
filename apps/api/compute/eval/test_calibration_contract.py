"""CI honesty gate + Neper parser tests.

Guards two things:
  1. The cloud calibration contract — vocabulary + the ``"validated"`` gate.
  2. The Neper ``.tess``/stats parser — cell counting, dimensionless-by-default
     sizing, and µm/ASTM only when a physical domain is supplied — and that its
     output satisfies the contract.
"""
import math
import os

import pytest

from apps.api.compute.calibration import (
    ALLOWED_CALIBRATIONS,
    CalibrationContractError,
    validate_calibration,
)
from apps.api.ml.microstructure.grain_tessellation import (
    build_neper_script,
    parse_neper_result,
)

# A tiny PNG (1×1) so the parser has bytes to base64-encode.
_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
_TESS = b"***tess\n **format\n   3.5\n **cell\n  4\n  *crysym\n   triclinic\n"
_STATS = b"0.50\n0.62\n0.48\n0.70\n"  # 4 equivalent diameters (unit-cube units)


# ── calibration contract ───────────────────────────────────────────────

def test_allowed_calibrations_pass():
    for cal in ALLOWED_CALIBRATIONS:
        validate_calibration({"calibration": cal})  # must not raise


def test_missing_calibration_rejected():
    with pytest.raises(CalibrationContractError):
        validate_calibration({"grain_count": 100})


def test_unknown_calibration_rejected():
    with pytest.raises(CalibrationContractError):
        validate_calibration({"calibration": "totally-legit-trust-me"})


def test_validated_requires_thermal_and_irf():
    # bare "validated" is forbidden — compute cost can't earn the label
    with pytest.raises(CalibrationContractError):
        validate_calibration({"calibration": "validated"})
    with pytest.raises(CalibrationContractError):
        validate_calibration({"calibration": "validated", "coupled_thermal": True})
    # only allowed with BOTH a coupled thermal field and a named IRF
    validate_calibration({
        "calibration": "validated",
        "coupled_thermal": True,
        "irf_source": "AdditiveFOAM 316L (Smith 2021)",
    })


# ── Neper parser ───────────────────────────────────────────────────────

def test_parse_dimensionless_by_default():
    res = parse_neper_result(
        {"tess": _TESS, "png": _PNG, "stats": _STATS},
        n_requested=4, morpho="voronoi",
    )
    assert res["grain_count"] == 4
    assert res["calibration"] == "deterministic-geometry"
    assert res["mean_grain_size_normalized"] == pytest.approx(0.575, abs=1e-3)
    # no physical domain → no µm/ASTM, and a clear dimensionless warning
    assert "mean_grain_size_um" not in res
    assert any("DIMENSIONLESS" in w for w in res["warnings"])
    assert res["png_base64"]
    validate_calibration(res)  # parser output honors the contract


def test_parse_with_domain_gives_um_and_astm():
    res = parse_neper_result(
        {"tess": _TESS, "png": _PNG, "stats": _STATS},
        n_requested=4, morpho="voronoi", domain_um=100.0,
    )
    assert res["domain_um"] == 100.0
    assert res["mean_grain_size_um"] == pytest.approx(57.5, abs=0.1)
    expected_astm = 1.0 + math.log2(64.5 ** 2 / 57.5 ** 2)
    assert res["astm_grain_number"] == pytest.approx(round(expected_astm, 2), abs=0.05)


def test_cell_count_falls_back_to_tess_header():
    res = parse_neper_result({"tess": _TESS, "png": None, "stats": None},
                             n_requested=4, morpho="voronoi")
    assert res["grain_count"] == 4
    assert any("Render PNG missing" in w for w in res["warnings"])


def test_build_script_clamps_and_self_bootstraps():
    body = build_neper_script({"n_grains": 99999, "morpho": "nonsense"})
    assert "-n 2000" in body          # clamped to MAX_GRAINS
    assert "-morpho voronoi" in body  # bad morpho → safe default
    assert "command -v neper" in body  # self-bootstrap guard present


@pytest.mark.skipif(
    not os.path.exists("/tmp/neper_spike.tess"),
    reason="real spike .tess only present on the dev box that ran the spike",
)
def test_parse_real_spike_tess():
    with open("/tmp/neper_spike.tess", "rb") as f:
        tess = f.read()
    res = parse_neper_result({"tess": tess, "png": None, "stats": None},
                             n_requested=100, morpho="voronoi")
    assert res["grain_count"] == 100
    validate_calibration(res)
