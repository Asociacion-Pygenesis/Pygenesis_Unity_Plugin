"""
Extrae metadatos para crear un .cs en Unity desde la respuesta del asistente.

El modelo debe añadir (solo si el usuario pidió un script completo):

---PYGENESIS_CREATE_SCRIPT---
{"fileName":"Nombre.cs"}
---PYGENESIS_SCRIPT_END---

y un bloque ```csharp ... ``` con el código fuente.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger("pygenesis")

MARKER_START = "---PYGENESIS_CREATE_SCRIPT---"
MARKER_END = "---PYGENESIS_SCRIPT_END---"
MAX_SCRIPT_CHARS = 500_000

# Bloques ```csharp ... ```, ``` c# ... ```, etc. (modelos externos suelen variar espacios e idiomas).
_FENCE_CSHARP = re.compile(r"```\s*(?:csharp|c#|cs)\s*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)
# Misma etiqueta pero sin salto de línea obligatorio (una sola línea tras el tag).
_FENCE_CSHARP_INLINE = re.compile(r"```\s*(?:csharp|c#|cs)\s+(.+?)```", re.DOTALL | re.IGNORECASE)
_FENCE_GENERIC = re.compile(r"```\s*\r?\n(.*?)```", re.DOTALL)

# Solo nombre de archivo seguro bajo Assets/Scripts/
_SAFE_CS_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.cs$")


def _looks_like_csharp(source: str) -> bool:
    t = source.strip()
    if len(t) < 8:
        return False
    keys = (
        "using ",
        "namespace ",
        "class ",
        "struct ",
        "interface ",
        "MonoBehaviour",
        "ScriptableObject",
        "[SerializeField]",
        "#region",
        "public void ",
        "void Start(",
    )
    return any(k in t for k in keys)


def _collect_code_blocks(full_text: str) -> list[str]:
    """Extrae candidatos de código C# del markdown (orden: etiquetados csharp, luego ``` genéricos plausibles)."""
    blocks: list[str] = []
    for pat in (_FENCE_CSHARP, _FENCE_CSHARP_INLINE):
        blocks.extend(s.strip() for s in pat.findall(full_text) if s.strip())
    if blocks:
        return blocks
    generic = [s.strip() for s in _FENCE_GENERIC.findall(full_text) if s.strip()]
    csharp_like = [s for s in generic if _looks_like_csharp(s)]
    return csharp_like if csharp_like else generic


def _sanitize_filename(name: str) -> Optional[str]:
    if not name or not isinstance(name, str):
        return None
    base = name.strip().replace("\\", "/").split("/")[-1]
    if not _SAFE_CS_NAME.match(base):
        return None
    return base


def extract_script_creation(raw: str) -> tuple[str, Optional[dict[str, Any]]]:
    """
    Devuelve (contenido_visible_para_el_usuario, metadata create_script o None).
    Si hay creación válida, el contenido visible elimina el bloque de marcadores.
    """
    if not raw or not raw.strip():
        return raw, None

    text = raw
    start = text.find(MARKER_START)
    end = text.find(MARKER_END)

    if start == -1 or end == -1 or end <= start:
        return raw.strip(), None

    # El system prompt del chat incluye los marcadores como documentación; modelos locales
    # a veces los repiten al inicio sin un bloque útil real → "visible" queda en una línea
    # y se pierde el resto de la respuesta (p. ej. solo "Respondes en C# y en Unity.").
    provisional_visible = (text[:start].rstrip() + "\n" + text[end + len(MARKER_END) :].lstrip()).strip()
    total_len = len(text.strip())
    vis_len = len(provisional_visible)
    before = text[:start]
    markers_at_beginning = start < 40 or (start < 100 and "```" not in before)
    if markers_at_beginning and vis_len < max(160, int(total_len * 0.35)):
        logger.warning(
            "PYGENESIS_CREATE_SCRIPT ignorado (eco de marcadores al inicio; visible=%d de %d, start=%d)",
            vis_len,
            total_len,
            start,
        )
        return text.strip(), None

    if (
        total_len > 900
        and start < 120
        and vis_len < min(320, int(total_len * 0.12))
    ):
        logger.warning(
            "PYGENESIS_CREATE_SCRIPT ignorado (marcadores tempranos y texto visible muy corto: "
            "total=%d visible=%d start=%d); se devuelve la respuesta completa.",
            total_len,
            vis_len,
            start,
        )
        return text.strip(), None

    visible = provisional_visible
    json_blob = text[start + len(MARKER_START) : end].strip()

    if json_blob.startswith("```"):
        jm = re.match(
            r"^```(?:json)?\s*\r?\n?(.*?)```\s*$",
            json_blob,
            re.DOTALL | re.IGNORECASE,
        )
        if jm:
            json_blob = jm.group(1).strip()

    try:
        data = json.loads(json_blob)
    except json.JSONDecodeError as e:
        logger.warning("PYGENESIS_CREATE_SCRIPT JSON inválido: %s", e)
        return visible, None

    fname = data.get("fileName") or data.get("file_name")
    safe = _sanitize_filename(fname) if isinstance(fname, str) else None
    if not safe:
        logger.warning("fileName inválido o inseguro en PYGENESIS_CREATE_SCRIPT: %r", fname)
        return visible, None

    blocks = _collect_code_blocks(text)
    if not blocks:
        logger.warning("PYGENESIS_CREATE_SCRIPT sin bloque de código ``` reconocible (csharp/c#/``` genérico)")
        return visible, None

    code = blocks[-1].strip()
    if len(code) > MAX_SCRIPT_CHARS:
        logger.warning("Script demasiado largo (%d chars), omitiendo create_script", len(code))
        return visible, None

    asset_path = f"Assets/Scripts/{safe}"
    return visible, {
        "asset_path": asset_path,
        "content": code,
    }
