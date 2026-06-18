"""Async cloud-compute tier for LeilMat's heavy simulations.

Phase-0 foundation that lets the API offload work that cannot fit in a
synchronous web request (Neper tessellation today; SPPARKS / ExaCA later)
onto ephemeral cloud sandboxes (Daytona), poll them to completion, and
download the artifacts.

Pieces:
  * ``runner``       — provider-agnostic ``CloudRunner`` + ``DaytonaRunner``.
  * ``jobs``         — the ``ComputeJob`` SQLAlchemy row + async CRUD.
  * ``orchestrator`` — submit/poll/cleanup lifecycle + cost guardrails.
  * ``reaper``       — background sweep of orphaned sandboxes + stuck rows.

The whole subsystem is DARK unless ``settings.daytona_api_key`` is set.
"""
