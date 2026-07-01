"""Extracción de texto HTML y troceado para indexación."""

from __future__ import annotations

import re
from typing import Tuple

from bs4 import BeautifulSoup


def html_to_text(html: str) -> Tuple[str, str]:
    """
    Devuelve (texto_plano, título aproximado desde <title> o vacío).
    """
    soup = BeautifulSoup(html, "lxml")
    title = ""
    t = soup.find("title")
    if t and t.string:
        title = t.string.strip()

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, title


def chunk_text(text: str, *, size: int = 900, overlap: int = 120) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    step = max(size - overlap, 1)
    i = 0
    n = len(text)
    while i < n:
        piece = text[i : i + size].strip()
        if piece:
            chunks.append(piece)
        i += step
    return chunks
