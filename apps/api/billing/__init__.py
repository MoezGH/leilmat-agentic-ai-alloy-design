"""LeilMat billing integration with LeilAI-5's central wallet.

This package owns the sub-app side of the credit system:

* ``usage`` — per-request caller identity (contextvar) + the shared
  ``maybe_deduct_credits`` helper that POSTs to LeilAI-5's
  ``/billing/credits/deduct`` after each cost-bearing LLM call.

The pre-flight credit *check* lives in ``apps.api.middleware.credits``;
this package is the *deduct* half.
"""
