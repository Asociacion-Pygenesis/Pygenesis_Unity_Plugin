#!/usr/bin/env python3
"""
Descarga URLs permitidas, trocea texto y construye el índice Chroma local.

Lista blanca: reasoning/rag/allowlist.py (docs.unity3d.com, learn.microsoft.com, docs.microsoft.com).

Uso (desde Tools/pygenesis_backend):
  pip install -r requirements.txt
  python scripts/build_rag_index.py
  python scripts/build_rag_index.py --reset
  python scripts/build_rag_index.py --seeds config/rag_seed_urls.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from reasoning.rag.allowlist import assert_allowed_url, is_allowed_url  # noqa: E402
from reasoning.rag.chroma_store import COLLECTION_NAME, default_chroma_path, get_or_create_collection  # noqa: E402
from reasoning.rag.html_chunk import chunk_text, html_to_text  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("build_rag_index")

USER_AGENT = "PyGenesisRAG/1.0 (+local indexer; contact: project maintainer)"


def load_seeds(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    urls = data.get("urls") or []
    if not isinstance(urls, list):
        raise ValueError("El JSON debe contener una lista 'urls'.")
    out: list[str] = []
    for u in urls:
        if isinstance(u, str) and u.strip():
            out.append(u.strip())
    return out


def fetch_html(url: str, timeout: float = 60.0) -> str:
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


def reset_collection(client_path: Path) -> None:
    import chromadb

    client_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(client_path))
    try:
        client.delete_collection(name=COLLECTION_NAME)
        logger.info("Colección anterior eliminada: %s", COLLECTION_NAME)
    except Exception as e:
        logger.info("No había colección previa o no se pudo borrar: %s", e)


def main() -> int:
    parser = argparse.ArgumentParser(description="Construir índice RAG (Chroma) desde URLs permitidas.")
    parser.add_argument(
        "--seeds",
        type=Path,
        default=BACKEND_ROOT / "config" / "rag_seed_urls.json",
        help="JSON con clave 'urls' (lista de strings).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Borra la colección existente antes de indexar.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.4,
        help="Pausa entre peticiones HTTP (segundos).",
    )
    args = parser.parse_args()

    seeds_path = args.seeds
    if not seeds_path.is_file():
        logger.error("No existe el fichero de seeds: %s", seeds_path)
        return 1

    urls = load_seeds(seeds_path)
    if not urls:
        logger.error("Lista de URLs vacía.")
        return 1

    chroma_path = default_chroma_path()
    logger.info("Chroma path: %s", chroma_path)

    if args.reset:
        reset_collection(chroma_path)

    collection = get_or_create_collection()

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for url in urls:
        if not is_allowed_url(url):
            logger.warning("Omitido (no permitido): %s", url)
            continue
        try:
            assert_allowed_url(url)
            logger.info("Descargando %s", url)
            html = fetch_html(url)
            text, title = html_to_text(html)
            if not text or len(text) < 80:
                logger.warning("Texto muy corto, se omite: %s", url)
                continue
            chunks = chunk_text(text, size=900, overlap=120)
            for idx, ch in enumerate(chunks):
                cid = hashlib.sha256(f"{url}\n{idx}".encode("utf-8")).hexdigest()[:40]
                ids.append(cid)
                documents.append(ch)
                metadatas.append(
                    {
                        "source_url": url,
                        "chunk_index": idx,
                        "title": (title or "")[:240],
                    }
                )
            time.sleep(max(args.sleep, 0.0))
        except Exception as e:
            logger.exception("Fallo indexando %s: %s", url, e)

    if not ids:
        logger.error("No se indexó ningún fragmento. Revisa URLs y conexión.")
        return 1

    # Chroma recomienda add en lotes; para tamaños moderados un único add vale.
    batch = 80
    for i in range(0, len(ids), batch):
        collection.add(
            ids=ids[i : i + batch],
            documents=documents[i : i + batch],
            metadatas=metadatas[i : i + batch],
        )

    logger.info("Indexación terminada: %d fragmentos en %s", len(ids), chroma_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
