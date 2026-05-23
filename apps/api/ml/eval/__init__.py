"""
Validation harness for the property prediction models.

Tracks the scientific spine of LeilMat:
- Track B (yield strength): held-out canonical alloys + leave-one-out CV
- Track A (M3GNet formation energy): canonical alloy energies vs. DFT references
- Track C (conformal prediction): empirical coverage of uncertainty bands

Run the full scorecard:
    python -m apps.api.ml.eval.scorecard

Run pytest tests (regression-gate CI):
    pytest apps/api/ml/eval/
"""
