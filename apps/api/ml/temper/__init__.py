"""
apps.api.ml.temper
===================

Sprint 4 — temper as a model input.

Yields the temper as a structured feature that gets concatenated to the
Magpie composition features at training and prediction time.  This is
the difference between 6061-O (55 MPa) and 6061-T6 (276 MPa) — same
composition, 5× different YS.

Public API
----------
from apps.api.ml.temper.encoding import (
    canonicalise_temper, encode_temper, default_temper_for_family,
    TEMPER_VOCABULARY,
)
"""
