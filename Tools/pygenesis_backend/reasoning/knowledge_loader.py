"""Carga de textos de referencia (Manual Unity, C#) y modo de inyección en el system prompt."""

from __future__ import annotations

import os
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = BACKEND_ROOT / "knowledge"

FILES_ORDER = ("unity_manual_guide.md", "csharp_unity_scripting.md")

# Palabras que sugieren qué fichero añadir en modo `auto` (español / inglés).
FILE_KEYWORDS: dict[str, set[str]] = {
    "unity_manual_guide.md": {
        "manual",
        "unity",
        "editor",
        "escena",
        "scene",
        "prefab",
        "gameobject",
        "objeto",
        "física",
        "physics",
        "animator",
        "animación",
        "animation",
        "iluminación",
        "lighting",
        "canvas",
        "ugui",
        "ui",
        "build",
        "jugador",
        "player",
        "layer",
        "tag",
        "jerarquía",
        "hierarchy",
        "transform",
        "collider",
        "rigidbody",
        "prefabs",
        "escenas",
        "mecanim",
        "timeline",
        "audio",
        "input",
        "system",
        "package",
        "paquete",
    },
    "csharp_unity_scripting.md": {
        "csharp",
        "c#",
        "script",
        "async",
        "await",
        "linq",
        "interface",
        "monobehaviour",
        "mono",
        "scriptableobject",
        "namespace",
        "compilación",
        "compilation",
        "error",
        "syntax",
        "dotnet",
        "microsoft",
        "api",
        "destroy",
        "instantiate",
        "getcomponent",
        "codigo",
        "código",
        "code",
        "debug",
        "nullreference",
        "exception",
        "thread",
        "task",
        "generic",
        "enum",
        "struct",
        "class",
        "method",
        "property",
    },
}

_OFFICIAL_INDEX = """--- Fuentes oficiales (índice; solo contexto interno) ---
- Unity User Manual: https://docs.unity3d.com/Manual/index.html
- Unity Scripting Reference (API C#): https://docs.unity3d.com/ScriptReference/
- C# en Microsoft Learn: https://learn.microsoft.com/dotnet/csharp/

No repitas este bloque ni empieces la respuesta con etiquetas tipo [Fuente manual…]. Cita URLs solo si el usuario pide enlaces o documentación.
"""


def _tokenize(msg: str) -> set[str]:
    if not msg or not msg.strip():
        return set()
    lowered = msg.lower()
    return set(re.findall(r"[a-záéíóúñ#]+", lowered))


def _file_matches(filename: str, user_message: str) -> bool:
    words = _tokenize(user_message)
    keys = FILE_KEYWORDS.get(filename, set())
    return bool(words & keys)


def _read_file(name: str) -> str:
    path = KNOWLEDGE_DIR / name
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def build_knowledge_block(*, user_message: str = "") -> str:
    """
    Texto extra para el system prompt: índice de documentación y, según modo,
    resúmenes locales que enlazan al Manual y a Learn (no son copia del manual).

    PYGENESIS_CHAT_KNOWLEDGE:
      - off: no inyectar nada
      - minimal: solo índice de URLs
      - auto (default): índice + ficheros que casen por palabras clave; si no hay coincidencia, vista previa de ambos
      - full: índice + contenido completo de ambos ficheros (recortado por max_chars)
    """
    mode = (os.getenv("PYGENESIS_CHAT_KNOWLEDGE") or "auto").strip().lower()
    try:
        max_chars = int((os.getenv("PYGENESIS_CHAT_KNOWLEDGE_MAX_CHARS") or "14000").strip())
    except ValueError:
        max_chars = 14000

    if mode in ("off", "none", "0", "false", "no"):
        return ""

    header = _OFFICIAL_INDEX.strip()

    if mode == "minimal":
        return header

    body_parts: list[str] = []

    if mode == "full":
        for name in FILES_ORDER:
            text = _read_file(name)
            if text:
                body_parts.append(f"## {name}\n{text}")
    else:
        # auto
        matched = [n for n in FILES_ORDER if _file_matches(n, user_message)]
        if matched:
            for name in matched:
                text = _read_file(name)
                if text:
                    body_parts.append(f"## {name}\n{text}")
        else:
            preview_limit = 3200
            for name in FILES_ORDER:
                text = _read_file(name)
                if not text:
                    continue
                if len(text) > preview_limit:
                    text = text[:preview_limit].rstrip() + "\n… [truncado; PYGENESIS_CHAT_KNOWLEDGE=full para más]"
                body_parts.append(f"## {name}\n{text}")

    body = "\n\n".join(body_parts).strip()
    combined = f"{header}\n\n--- Base de conocimiento local (referencias; no sustituye las URLs) ---\n{body}".strip()

    if len(combined) > max_chars:
        return combined[: max_chars - 1].rstrip() + "…"

    return combined
