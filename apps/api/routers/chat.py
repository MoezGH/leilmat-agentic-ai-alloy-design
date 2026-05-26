"""
POST /api/chat/local   — Local AI: selection-aware in-canvas suggestions (compact context)
POST /api/chat/global  — Global AI: full session reasoning + RAG (long context)
POST /api/chat/ingest  — Ingest a PDF into the RAG pipeline

Note: ``from __future__ import annotations`` was removed here because the
slowapi ``@limiter.limit`` decorator wraps the route, and FastAPI's
Pydantic-schema introspection can't resolve forward-ref type hints from
the wrapper's module namespace.  All Pydantic models in this file are
defined before they're referenced, so eager evaluation is safe.
"""
import json
import logging
import time
from typing import Any, AsyncIterator

import openai
from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from fastapi.responses import StreamingResponse

from apps.api.rate_limit import limiter, LLM_LIMIT
from pydantic import BaseModel

from apps.api.config import settings
from apps.api.ml.llm_budget import BUDGET

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic request models — hoisted ABOVE the route decorators so the
# slowapi limiter wrapper doesn't trip Pydantic's forward-ref resolution
# under ``from __future__ import annotations``.
class LocalAIRequest(BaseModel):
    selected_element: dict[str, Any]   # {type, data, canvas_summary}
    user_question: str | None = None
    session_id: str | None = None


class GlobalAIRequest(BaseModel):
    session: dict[str, Any]            # full session state
    user_message: str
    use_rag: bool = True
    session_id: str | None = None


class GlobalScanRequest(BaseModel):
    session: dict[str, Any]

LOCAL_SYSTEM = """You are an expert materials scientist embedded in a visual design canvas.
The user selected a single canvas element (a property bar, composition slider, phase region, etc.) and
wants targeted, atomic suggestions specific to that selection.

Respond in TWO parts, in this exact order:

1. PROSE — 2-4 short sentences (≤ 80 words total) explaining what you'd
   change and why.  Ground claims in real materials science.  No bullet
   lists, no markdown headers — just compact paragraphs.

2. ACTIONS BLOCK — a fenced JSON list of 2-4 clickable actions the user
   can apply with one click.  Each action runs an atomic mutation on the
   canvas: shift one slider, adjust a target, or sweep a range.

Format the actions block EXACTLY like this (language tag must be ``actions``):

```actions
[
  { "op": "delta_element", "element": "Mg", "delta": 1.5,
    "label": "Bump Mg +1.5 pp for solid-solution strengthening" },
  { "op": "set_element", "element": "Si", "value": 3.5,
    "label": "Pull Si to 3.5% near the Al-Si eutectic" },
  { "op": "sweep", "vary": "Mg", "from": 0, "to": 15, "steps": 8,
    "label": "Sweep Mg from 0-15% and predict each point" }
]
```

Allowed ``op`` values for Local AI (keep the suggestion atomic — Local
AI nudges one element/target at a time; bulk reshapes belong to Global AI):

* ``set_element``     { "element": "<sym>", "value": <pct> }
* ``delta_element``   { "element": "<sym>", "delta": <pct> }
* ``set_target``      { "name": "density_g_cm3"|"melting_point_K", "value": <num> }
* ``sweep``           { "vary": "<sym>", "from": <pct>, "to": <pct>, "steps": <n> }

Rules:
1. ALWAYS include a short, action-oriented ``label`` (sentence-case, ≤ 60 chars).
2. Prefer ``delta_element`` over ``set_element`` for "small nudge"
   suggestions — preserves the user's existing baseline.
3. Prefer ``sweep`` when the right answer is "explore a range" rather
   than "set one value."  Sweep is more expensive but more informative.
4. Emit 2-4 actions.  Fewer is usually correct for Local AI's narrower
   context.
5. If the selection is purely informational (an explanation, a
   comparison, a question), omit the actions block — prose only is fine.
6. The actions block MUST be the LAST thing in your response.
"""

GLOBAL_SYSTEM = """You are an expert materials scientist and alloy design assistant. You have full visibility into
the user's design session: their goals, constraints, explored compositions, bookmarked candidates, and rejected options.

Answer with depth and precision. When you cite specific values (formation energies, yield strength ranges, phase boundaries),
ground them in the retrieved literature or known materials science data. If uncertain, say so.

Format citations as [Source: <paper name>] inline.

For the "Global Scan" button, proactively identify the top 3 cross-cutting insights across the session:
patterns the user may have missed, contradictions between constraints, unexplored composition spaces, etc.

═══ AGENTIC ACTIONS ═══════════════════════════════════════════════════

Whenever you make a concrete design recommendation (a composition, a target,
a goal, a sweep direction), END YOUR RESPONSE with a fenced JSON block of
clickable actions that apply your suggestion to the canvas in one click.
Without this block the user has to manually translate your prose into
slider movements, which is bad UX.

Format the block EXACTLY like this — language tag must be ``actions``:

```actions
[
  { "op": "set_phase_system", "elements": ["Al","Mg","Si"],
    "label": "Use the Al-Mg-Si system" },
  { "op": "set_composition", "composition": {"Al": 99.0, "Mg": 0.5, "Si": 0.5},
    "label": "Start near pure Al (Mg 0.5%, Si 0.5%)" },
  { "op": "set_goals", "goals": {"primary": "maximize electrical resistivity"},
    "label": "Goal: high electrical resistivity" },
  { "op": "set_target", "name": "density_g_cm3", "value": 2.8,
    "label": "Cap density at 2.8 g/cm³" },
  { "op": "run_predict",
    "label": "Predict properties now" }
]
```

Allowed ``op`` values, with payload shapes:

* ``set_composition``    { "composition": {"<el>": <pct>, ...} }      Bulk-replace composition (whole canvas).
* ``set_element``        { "element": "<sym>", "value": <pct> }       Set one element; renormalise others.
* ``delta_element``      { "element": "<sym>", "delta": <pct> }       Bump one element by ±N pp.
* ``set_phase_system``   { "elements": ["<sym>", ...] }                Change which elements the canvas tracks.
* ``set_target``         { "name": "density_g_cm3"|"melting_point_K", "value": <num>, "optimize": "min"|"max" }
* ``set_goals``          { "goals": {"primary": "<text>", ...} }      Free-form session goals.
* ``set_constraints``    { "constraints": {"<key>": <val>, ...} }     Free-form session constraints.
* ``sweep``              { "vary": "<sym>", "from": <pct>, "to": <pct>, "steps": <n> }   Auto-explore range.
* ``run_predict``        no payload                                    Trigger the Predict Properties button.
* ``run_optimization``   no payload                                    Trigger the Run Optimization button.

Rules:
1. ALWAYS include a short, action-oriented ``label`` (sentence-case, ≤ 60 chars).
2. Order actions in the sequence the user should apply them — usually:
   phase system → composition → goals/constraints → predict/optimize.
3. Emit 2-6 actions per response. Fewer feels useless; more is overwhelming.
4. Compositions must sum close to 100% (the frontend renormalises but small
   gaps look sloppy).
5. If the user is asking a pure-knowledge question (no design intent), omit
   the actions block entirely — prose only is fine.
6. The block MUST be the LAST thing in your response. Anything after the
   closing ``` is dropped.
"""


def _build_local_context(selected_element: dict[str, Any]) -> str:
    return f"""Selected canvas element:
Type: {selected_element.get('type', 'unknown')}
Data: {json.dumps(selected_element.get('data', {}), indent=2)}
Canvas summary: {json.dumps(selected_element.get('canvas_summary', {}), indent=2)}"""


def _build_global_context(session: dict[str, Any]) -> str:
    return f"""Full design session:
Goals: {json.dumps(session.get('goals', {}), indent=2)}
Constraints: {json.dumps(session.get('constraints', {}), indent=2)}
Explored compositions ({len(session.get('compositions', []))} total):
{json.dumps(session.get('compositions', [])[:20], indent=2)}
Bookmarked: {json.dumps([c for c in session.get('compositions', []) if c.get('bookmarked')], indent=2)}
Rejected: {json.dumps([c for c in session.get('compositions', []) if c.get('rejected')], indent=2)}
Conversation so far: {len(session.get('messages', []))} messages"""


async def _stream_llm(
    system: str,
    user_message: str,
    retrieved_chunks: list[dict] | None = None,
    endpoint_label: str = "chat",
) -> AsyncIterator[str]:
    # Daily-budget gate.  If we're over cap, emit a single-event "exhausted"
    # marker so the frontend can render a friendly message instead of a
    # blank streaming buffer.
    if not BUDGET.can_spend():
        yield f"data: {json.dumps({'text': '⚠ The daily AI quota has been reached. Live insights resume after UTC midnight; the deterministic numeric layers remain available.'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    if not settings.openrouter_api_key:
        yield f"data: {json.dumps({'text': '⚠ AI is not configured (OPENROUTER_API_KEY missing).'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    client = openai.AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )

    full_user = user_message
    if retrieved_chunks:
        citations = "\n\n".join(
            f"[Source: {c['source']}]\n{c['text']}" for c in retrieved_chunks
        )
        full_user = f"Relevant literature:\n{citations}\n\n---\n\n{user_message}"

    t0 = time.perf_counter()
    last_usage = None
    stream = await client.chat.completions.create(
        model=settings.llm_model,
        max_tokens=2048,
        stream=True,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": full_user},
        ],
        # DeepSeek V4 Pro is a reasoning model — disable reasoning so all output goes to `content`
        extra_body={"reasoning": {"exclude": True}},
        # Ask OpenRouter to attach usage on the final chunk so we can
        # charge the budget + log cost.
        stream_options={"include_usage": True},
    )
    async for chunk in stream:
        # The terminal chunk carries .usage with prompt/completion/cost; it
        # has no choices.delta.content, so the existing text-only emit
        # below ignores it correctly.
        if getattr(chunk, "usage", None):
            last_usage = chunk.usage
        if not chunk.choices:
            continue
        text = chunk.choices[0].delta.content
        if text:
            yield f"data: {json.dumps({'text': text})}\n\n"

    elapsed_s = time.perf_counter() - t0

    # Post-stream: charge the budget + emit structured cost log.
    cost_reported = getattr(last_usage, "cost", None) if last_usage else None
    prompt_tokens = int(getattr(last_usage, "prompt_tokens", 0) or 0) if last_usage else 0
    completion_tokens = int(getattr(last_usage, "completion_tokens", 0) or 0) if last_usage else 0
    cost_charged = BUDGET.charge(
        endpoint=endpoint_label,
        cost_usd=cost_reported,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model=settings.llm_model,
    )
    logger.info(
        "[llm_cost] endpoint=%s model=%s prompt=%d completion=%d "
        "cost_usd=%.4f reported=%s elapsed_s=%.2f",
        endpoint_label, settings.llm_model,
        prompt_tokens, completion_tokens,
        cost_charged,
        f"{cost_reported:.6f}" if cost_reported is not None else "missing",
        elapsed_s,
    )

    yield "data: [DONE]\n\n"


# ── Local AI ────────────────────────────────────────────────────────────────

@router.post("/local")
@limiter.limit(LLM_LIMIT)
async def local_ai(request: Request, req: LocalAIRequest):
    context = _build_local_context(req.selected_element)
    user_msg = req.user_question or "Suggest improvements for this selected element."

    return StreamingResponse(
        _stream_llm(LOCAL_SYSTEM, f"{context}\n\nUser: {user_msg}",
                    endpoint_label="chat_local"),
        media_type="text/event-stream",
    )


# ── Global AI ───────────────────────────────────────────────────────────────

@router.post("/global")
@limiter.limit(LLM_LIMIT)
async def global_ai(request: Request, req: GlobalAIRequest):
    retrieved: list[dict] = []
    if req.use_rag:
        # Fail fast if ChromaDB isn't reachable — don't let it stall the LLM call
        try:
            import socket
            with socket.create_connection((settings.chroma_host, settings.chroma_port), timeout=0.3):
                pass
            from apps.api.rag.pipeline import retrieve
            retrieved = retrieve(req.user_message, n_results=4)
        except Exception as exc:
            print(f"[rag] skipping retrieval: {exc}")

    session_ctx = _build_global_context(req.session)
    user_msg = f"{session_ctx}\n\nUser question: {req.user_message}"

    return StreamingResponse(
        _stream_llm(GLOBAL_SYSTEM, user_msg,
                    retrieved_chunks=retrieved if retrieved else None,
                    endpoint_label="chat_global"),
        media_type="text/event-stream",
    )


# ── Global Scan ─────────────────────────────────────────────────────────────


@router.post("/scan")
@limiter.limit(LLM_LIMIT)
async def global_scan(request: Request, req: GlobalScanRequest):
    """Proactively analyzes the session and surfaces top 3 insights."""
    session_ctx = _build_global_context(req.session)
    user_msg = (
        f"{session_ctx}\n\n"
        "Perform a Global Scan. Identify the top 3 most important insights, patterns, or gaps "
        "across this design session that the user may have missed. Be specific and actionable."
    )
    return StreamingResponse(
        _stream_llm(GLOBAL_SYSTEM, user_msg, endpoint_label="chat_scan"),
        media_type="text/event-stream",
    )


# ── PDF Ingestion ────────────────────────────────────────────────────────────

@router.post("/ingest")
async def ingest_pdf(file: UploadFile = File(...)):
    """Upload and ingest a PDF into the RAG knowledge base."""
    import tempfile, os
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from apps.api.rag.pipeline import ingest_pdf as _ingest
        n_chunks = _ingest(tmp_path, source_label=file.filename)
        return {"filename": file.filename, "chunks_ingested": n_chunks}
    finally:
        os.unlink(tmp_path)
