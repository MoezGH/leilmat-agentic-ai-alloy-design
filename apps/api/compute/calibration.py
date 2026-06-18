"""The cloud-compute honesty contract.

Operationalizes the 878857b honesty pass for the cloud tier: a 6-hour H100 run
is exactly as uncalibrated as a 30-second local sim, so compute cost must not
launder the calibration label.  Every cloud-job result must carry a
``calibration`` tag from a fixed vocabulary, and the strongest label
``"validated"`` is forbidden unless the result was produced from a coupled
thermal field AND a named per-alloy interfacial-response function.

This is enforced two ways:
  * at runtime — the orchestrator calls :func:`validate_calibration` before
    marking a job done (a violating result fails the job rather than shipping);
  * in CI — ``eval/test_calibration_contract.py`` asserts the vocabulary and
    the ``"validated"`` gate, so a new cloud feature can't quietly overclaim.
"""
from __future__ import annotations

ALLOWED_CALIBRATIONS = frozenset({
    "deterministic-geometry",        # Neper: exact geometry/statistics
    "quantitative-characterization", # pyMKS-style: exact characterization of given data
    "qualitative",                   # topology/trend only (Potts, dendrite, ExaCA default)
    "literature-correlation",        # screening via published correlations
})


class CalibrationContractError(ValueError):
    """A cloud result violated the calibration honesty contract."""


def validate_calibration(result: dict) -> None:
    """Raise :class:`CalibrationContractError` if ``result`` overclaims.

    Rules:
      * a ``calibration`` tag is mandatory;
      * ``"validated"`` is allowed ONLY with ``coupled_thermal is True`` and a
        truthy ``irf_source`` (experimentally-grounded thermal + response fn);
      * every other tag must be in :data:`ALLOWED_CALIBRATIONS`.
    """
    cal = result.get("calibration")
    if not cal:
        raise CalibrationContractError("result is missing a 'calibration' tag")
    if cal == "validated":
        if not (result.get("coupled_thermal") is True and result.get("irf_source")):
            raise CalibrationContractError(
                "'validated' requires coupled_thermal=True AND a named irf_source; "
                "compute cost alone does not earn the label"
            )
        return
    if cal not in ALLOWED_CALIBRATIONS:
        raise CalibrationContractError(
            f"calibration {cal!r} is not in the allowed vocabulary "
            f"{sorted(ALLOWED_CALIBRATIONS)}"
        )
