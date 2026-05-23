"""
POST /api/chat/local   — Local AI: selection-aware in-canvas suggestions (compact context)
POST /api/chat/global  — Global AI: full session reasoning + RAG (long context)
POST /api/chat/ingest  — Ingest a PDF into the RAG pipeline
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

import openai
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.api.config import settings

router = APIRouter()

LOCAL_SYSTEM = """You are an expert materials scientist embedded in a visual design canvas.
The user selected a canvas element. Return 2-3 concise, actionable suggestions specific to that selection.

Respond ONLY with a JSON array. Each suggestion has these fields:
- action: short imperative (max 8 words)
- detail: one-sentence explanation with reasoning
- type: "composition" | "property" | "explore" | "constraint"
- executable: { op: ..., ... }  — what the system runs when user clicks Apply

Executable ops (pick the one that fits the suggestion):
- {"op": "set_element", "element": "Si", "value": 3.5}
    → set Si percentage to 3.5 (renormalises other elements)
- {"op": "delta_element", "element": "Mg", "delta": 1.5}
    → increment Mg by +1.5 percentage points (use negative for decrement)
- {"op": "set_target", "name": "density_g_cm3" | "melting_point_K", "value": 2.8}
    → adjust an inverse-design target
- {"op": "sweep", "vary": "Mg", "from": 0, "to": 15, "steps": 8}
    → generate N compositions varying one element, predicts each (DYNAMIC EXPLORATION)

Prefer "sweep" for explore-type suggestions. Prefer "set_element" or "delta_element" for composition tweaks.
Be specific about percentages, ranges, and expected effects. Ground claims in real materials science."""

GLOBAL_SYSTEM = """You are an expert materials scientist and alloy design assistant. You have full visibility into
the user's design session: their goals, constraints, explored compositions, bookmarked candidates, and rejected options.

Answer with depth and precision. When you cite specific values (formation energies, yield strength ranges, phase boundaries),
ground them in the retrieved literature or known materials science data. If uncertain, say so.

Format citations as [Source: <paper name>] inline.

For the "Global Scan" button, proactively identify the top 3 cross-cutting insights across the session:
patterns the user may have missed, contradictions between constraints, unexplored composition spaces, etc."""


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


async def _stream_llm(system: str, user_message: str, retrieved_chunks: list[dict] | None = None) -> AsyncIterator[str]:
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
    )
    async for chunk in stream:
        if not chunk.choices:
            continue
        text = chunk.choices[0].delta.content
        if text:
            yield f"data: {json.dumps({'text': text})}\n\n"
    yield "data: [DONE]\n\n"


# ── Local AI ────────────────────────────────────────────────────────────────

class LocalAIRequest(BaseModel):
    selected_element: dict[str, Any]   # {type, data, canvas_summary}
    user_question: str | None = None
    session_id: str | None = None


@router.post("/local")
async def local_ai(req: LocalAIRequest):
    context = _build_local_context(req.selected_element)
    user_msg = req.user_question or "Suggest improvements for this selected element."

    return StreamingResponse(
        _stream_llm(LOCAL_SYSTEM, f"{context}\n\nUser: {user_msg}"),
        media_type="text/event-stream",
    )


# ── Global AI ───────────────────────────────────────────────────────────────

class GlobalAIRequest(BaseModel):
    session: dict[str, Any]            # full session state
    user_message: str
    use_rag: bool = True
    session_id: str | None = None


@router.post("/global")
async def global_ai(req: GlobalAIRequest):
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
        _stream_llm(GLOBAL_SYSTEM, user_msg, retrieved_chunks=retrieved if retrieved else None),
        media_type="text/event-stream",
    )


# ── Global Scan ─────────────────────────────────────────────────────────────

class GlobalScanRequest(BaseModel):
    session: dict[str, Any]


@router.post("/scan")
async def global_scan(req: GlobalScanRequest):
    """Proactively analyzes the session and surfaces top 3 insights."""
    session_ctx = _build_global_context(req.session)
    user_msg = (
        f"{session_ctx}\n\n"
        "Perform a Global Scan. Identify the top 3 most important insights, patterns, or gaps "
        "across this design session that the user may have missed. Be specific and actionable."
    )
    return StreamingResponse(
        _stream_llm(GLOBAL_SYSTEM, user_msg),
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
