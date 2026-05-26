"""
POST /api/report/generate — build a multi-page PDF report from a
LeilMat design session and stream it back to the browser.

The endpoint is intentionally **synchronous + streaming-binary**: the
client posts the full session payload (composition, properties,
intervals, simulation results, messages) and receives a single
``application/pdf`` response.  We don't store the PDF server-side —
the user's browser handles the download via a blob URL.

Why server-side rather than browser-side?
─────────────────────────────────────────
Three reasons that all matter:

  1. ReportLab + matplotlib give us pixel-perfect, deterministic
     layout.  Browser-print-to-PDF varies across Chrome/Firefox/Safari
     and depends on the user's print stylesheet.

  2. The matplotlib charts (radar, Pareto, KWN kinetics) re-render
     at 150 dpi for the report — sharper than the live frontend Plotly
     canvas at the same physical size.  Building them on the server
     means we don't ship a second charting bundle to the client.

  3. Provenance footnotes need access to the model registry (training
     count, CV MAE, conformal-CI methodology).  That info lives on the
     api, not in the browser bundle.

Auth
────
Gated through the existing ``AuthMiddleware`` opt-in list — see
``apps/api/middleware/auth.py``'s ``ENFORCED_PREFIXES``.  The endpoint
itself doesn't call the LLM and doesn't deduct credits in v1; future
versions may add an AI-generated executive summary, at which point the
credit-deduct middleware picks it up automatically.

Rate limit: slow-tier (4 / min / IP) since each call spawns matplotlib
figures + may render a Pareto chart with dozens of points.

NOTE: this file intentionally does NOT use ``from __future__ import
annotations``.  Combining it with the Pydantic-2 + FastAPI ``Body(...)``
annotation produces a ``PydanticUserError: TypeAdapter[...
ForwardRef('ReportRequest')] is not fully defined`` at request time
(Pydantic can't auto-resolve the forward-ref under ``Body``).  Plain
type hints work fine; the routing modules elsewhere in this repo make
the same trade-off.
"""
import logging
from typing import Any

from fastapi          import APIRouter, Body, Request
from fastapi.responses import Response
from pydantic         import BaseModel

from apps.api.config           import settings  # noqa: F401  (parity with siblings)
from apps.api.ml.report.pdf    import build_pdf
from apps.api.rate_limit       import limiter, HEAVY_COMPUTE_LIMIT

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Request schema ───────────────────────────────────────────────────
# Everything is optional — the builder degrades gracefully and just
# omits the section if its inputs are missing.  This keeps the wire
# contract loose: future frontend additions don't require coordinated
# backend deploys.

class ReportRequest(BaseModel):
    # Identification
    alloy_name:  str | None = None
    designer:    str | None = None
    session_id:  str | None = None

    # Canvas state
    composition: dict[str, float]  = {}
    temper:      str | None        = None
    # ``properties`` is intentionally typed loosely (``Any``) because the
    # Zustand store on the canvas mirrors the /api/predict response shape,
    # which carries structured predictions like
    # ``{"value": 62.2, "source": "...", "uncertainty": 0.02}`` alongside
    # plain scalars and even the composition echo.  The PDF builder
    # normalises everything via ``_extract_scalar`` (see ml/report/pdf.py).
    # Pre-loosening this avoided a 422-cascade in the field.
    properties:  dict[str, Any] = {}
    # Each entry: [lower, upper] tuple from the conformal-CI calibration.
    # Also lax-typed for the same reason — older payloads sometimes carry
    # ``null`` or a dict shape from a partial response.
    property_intervals: dict[str, Any] = {}

    # Session context
    goals:       dict[str, str]    = {}
    constraints: dict[str, Any]    = {}
    messages:    list[dict[str, Any]] = []

    # Simulation results, keyed by bucket (phase / scheil / ttt /
    # microstructure / precipitation / inverse) — matches the
    # ``simulationResults`` field on the Zustand store.
    simulation_results: dict[str, Any] = {}

    # Convenience extras passed by older clients.
    stable_phases: list[dict[str, Any]] = []


# ─── Endpoint ─────────────────────────────────────────────────────────

@router.post("/generate", responses={200: {"content": {"application/pdf": {}}}})
@limiter.limit(HEAVY_COMPUTE_LIMIT)
async def generate_report(
    request: Request,
    # Explicit Body(...) because slowapi's @limiter.limit wrapper can
    # erase the Pydantic-vs-query parameter inference FastAPI normally
    # does — without this the endpoint 422s with
    # ``{"detail":[{"type":"missing","loc":["query","req"]…}]}``.
    req: ReportRequest = Body(...),
) -> Response:
    """Render the report and stream it back as application/pdf."""
    payload = req.model_dump()
    try:
        pdf_bytes = build_pdf(payload)
    except Exception as exc:                                            # noqa: BLE001
        # Surface the failure with the request path so the auth-mode
        # warnings + error logs line up in production.
        logger.exception("PDF report build failed: %s", exc)
        return Response(
            content=f"PDF generation failed: {exc}".encode("utf-8"),
            status_code=500,
            media_type="text/plain",
        )

    # Build a stable, downloadable filename.  Slug the alloy name with
    # the session ID to keep collisions at zero.
    slug = (req.alloy_name or "design").lower().strip().replace(" ", "-")
    sid  = req.session_id or "session"
    fname = f"leilmat-{slug}-{sid[:8]}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{fname}"',
            "Cache-Control":       "no-store",
        },
    )
