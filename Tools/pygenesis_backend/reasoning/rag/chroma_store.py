"""Cliente Chroma persistente y nombre de colección compartidos."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from reasoning.rag.paths import BACKEND_ROOT

COLLECTION_NAME = "pygenesis_docs"


def default_chroma_path() -> Path:
    override = (os.getenv("PYGENESIS_RAG_CHROMA_PATH") or "").strip()
    if override:
        return Path(override)
    return BACKEND_ROOT / "data" / "chroma_rag"


def get_collection():
    """Colección Chroma; None si chromadb no está instalado."""
    try:
        import chromadb
    except ImportError:
        return None

    path = str(default_chroma_path())
    client = chromadb.PersistentClient(path=path)
    try:
        return client.get_collection(name=COLLECTION_NAME)
    except Exception:
        return None


def get_or_create_collection() -> Any:
    import chromadb

    path = str(default_chroma_path())
    default_chroma_path().mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=path)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "PyGenesis allowlisted docs"},
    )


def collection_count(collection: Optional[Any]) -> int:
    if collection is None:
        return 0
    try:
        return int(collection.count())
    except Exception:
        return 0
