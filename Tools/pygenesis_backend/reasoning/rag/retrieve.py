"""Recuperación semántica para inyectar en el system prompt del chat."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, Tuple

from reasoning.rag.chroma_store import collection_count, default_chroma_path, get_collection

logger = logging.getLogger("pygenesis")

_lock = threading.Lock()


def _rag_enabled() -> bool:
    v = (os.getenv("PYGENESIS_RAG_ENABLED") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def retrieve_rag_context(user_message: str) -> Tuple[str, Dict[str, Any]]:
    """
    Devuelve (texto_para_system_prompt, metadata).
    Si RAG está desactivado, la colección no existe o está vacía, devuelve ("", {}).
    """
    if not _rag_enabled():
        return "", {}

    q = (user_message or "").strip()
    if len(q) < 3:
        return "", {"rag_skipped": "query_too_short"}

    try:
        top_k = int((os.getenv("PYGENESIS_RAG_TOP_K") or "5").strip())
    except ValueError:
        top_k = 5
    top_k = max(1, min(top_k, 20))

    try:
        max_chars = int((os.getenv("PYGENESIS_RAG_MAX_CHARS") or "8000").strip())
    except ValueError:
        max_chars = 8000
    max_chars = max(500, min(max_chars, 50000))

    with _lock:
        coll = get_collection()
        if coll is None:
            logger.info("RAG: sin colección Chroma en %s (ejecuta scripts/build_rag_index.py)", default_chroma_path())
            return "", {"rag_skipped": "no_collection"}
        if collection_count(coll) == 0:
            return "", {"rag_skipped": "empty_collection"}

        try:
            results = coll.query(query_texts=[q], n_results=top_k)
        except Exception as e:
            logger.warning("RAG query falló: %s", e)
            return "", {"rag_error": str(e)}

    docs = results.get("documents") or []
    metas = results.get("metadatas") or []
    if not docs or not docs[0]:
        return "", {"rag_skipped": "no_hits"}

    row_docs = docs[0]
    row_meta = metas[0] if metas and metas[0] else [{}] * len(row_docs)

    parts: list[str] = [
        "--- Fragmentos recuperados (RAG; fuentes de la lista blanca) ---",
        "Uso interno: no cites al inicio de la respuesta. Menciona la URL solo si el usuario pide documentación.",
    ]
    total = 0
    used = 0
    for i, doc in enumerate(row_docs):
        if not doc or not str(doc).strip():
            continue
        meta = row_meta[i] if i < len(row_meta) else {}
        url = (meta or {}).get("source_url") or "?"
        title = (meta or {}).get("title") or ""
        header = f"[{used + 1}] {title}\nOrigen: {url}"
        block = f"{header}\n{doc.strip()}"
        if total + len(block) + 2 > max_chars:
            break
        parts.append(block)
        total += len(block) + 2
        used += 1

    if used == 0:
        return "", {"rag_skipped": "no_hits_after_trim"}

    text = "\n\n".join(parts)
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"

    return text, {
        "rag_chunks": used,
        "rag_chars": len(text),
        "rag_store": str(default_chroma_path()),
    }
