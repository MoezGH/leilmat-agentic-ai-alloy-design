"""
RAG pipeline: PDF ingestion → ChromaDB → retrieval for grounded LLM answers.

No papers ship with the repository (they are third-party and copyrighted).
``preload_papers()`` ingests any ``*.pdf`` found in ``$LEILMAT_PAPERS_DIR``
(default: ``./Alloys Design``) and is a no-op when that directory is absent.
It is NOT called automatically at startup — invoke it explicitly, or ingest
individual files through the chat router's upload endpoint.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from apps.api.config import settings

PAPERS_DIR = Path(os.environ.get(
    "LEILMAT_PAPERS_DIR",
    Path(__file__).parent.parent.parent.parent / "Alloys Design",
))
COLLECTION_NAME = "alloy_literature"

_client: chromadb.ClientAPI | None = None
_collection: Any = None


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    _client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    _collection = _client.get_or_create_collection(COLLECTION_NAME, embedding_function=ef)
    return _collection


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def ingest_pdf(pdf_path: str | Path, source_label: str | None = None) -> int:
    """Parse a PDF and upsert chunks into ChromaDB. Returns number of chunks ingested."""
    from pypdf import PdfReader

    path = Path(pdf_path)
    label = source_label or path.stem
    reader = PdfReader(str(path))
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    chunks = _chunk_text(full_text)

    collection = _get_collection()
    ids, docs, metas = [], [], []
    for i, chunk in enumerate(chunks):
        chunk_id = hashlib.md5(f"{label}:{i}:{chunk[:50]}".encode()).hexdigest()
        ids.append(chunk_id)
        docs.append(chunk)
        metas.append({"source": label, "chunk_index": i})

    collection.upsert(ids=ids, documents=docs, metadatas=metas)
    return len(chunks)


def retrieve(query: str, n_results: int = 5) -> list[dict[str, Any]]:
    """Retrieve the most relevant chunks for a query."""
    collection = _get_collection()
    results = collection.query(query_texts=[query], n_results=n_results)
    chunks = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        chunks.append({"text": doc, "source": meta.get("source", "unknown")})
    return chunks


def preload_papers():
    """Ingest the reference papers if not already indexed."""
    if not PAPERS_DIR.exists():
        return
    collection = _get_collection()
    existing_sources = set()
    try:
        existing = collection.get(limit=1000)
        existing_sources = {m.get("source") for m in existing.get("metadatas", [])}
    except Exception:
        pass

    for pdf in PAPERS_DIR.glob("*.pdf"):
        label = pdf.stem[:60]
        if label not in existing_sources:
            try:
                n = ingest_pdf(pdf, label)
                print(f"Ingested {n} chunks from {pdf.name}")
            except Exception as e:
                print(f"Failed to ingest {pdf.name}: {e}")
