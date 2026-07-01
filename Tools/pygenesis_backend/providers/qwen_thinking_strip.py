"""Quita el bloque thinking de Qwen3 del texto del asistente (ver filtrar_thinking_qwen.md)."""

from __future__ import annotations

import os
import re

_REDACTED_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
_REDACTED_INNER = re.compile(r"<think>(.*?)</think>", re.DOTALL)


def _extract_outer_json_object(s: str) -> str:
    """Delimitador tope `{` … `}` (una sola pieza); suficiente para salida JSON del LLM."""
    t = (s or "").strip()
    if not t:
        return ""
    i = t.find("{")
    j = t.rfind("}")
    if i == -1 or j <= i:
        return ""
    return t[i : j + 1].strip()


def _should_try_recover_json(cleaned: str) -> bool:
    """Si tras quitar bloques redacted no hay JSON plausible, buscar JSON *dentro* de esos bloques."""
    c = (cleaned or "").strip()
    if not c:
        return True
    if "{" not in c or "}" not in c:
        return True
    return len(c) < 60


def _recover_json_from_redacted_blocks(original: str) -> str:
    """
    Qwen/Ollama a veces envuelve el JSON útil dentro de <think>…</>.
    Un strip naive borra todo y queda solo un eco del system (p. ej. «responde en español»).
    """
    for m in _REDACTED_INNER.finditer(original or ""):
        inner = (m.group(1) or "").strip()
        if not inner:
            continue
        cand = _extract_outer_json_object(inner)
        if len(cand) >= 40:
            return cand
    return ""


def strip_redacted_thinking(texto: str) -> str:
    if not texto:
        return ""
    original = texto
    cleaned = _REDACTED_BLOCK.sub("", original).strip()
    if _should_try_recover_json(cleaned):
        recovered = _recover_json_from_redacted_blocks(original)
        if recovered:
            return recovered

    texto = cleaned
    if "</think>" not in texto:
        return texto.strip()

    parts = [p.strip() for p in texto.split("</think>") if p is not None]
    if not parts:
        return ""
    first = parts[0].strip()
    last = parts[-1].strip()
    # Caso habitual (Qwen): respuesta útil *después* del cierre.
    # Caso alternativo: solo hay `</think>` sin `<think>…>` emparejado:
    # todo el razonamiento va *antes* del cierre y después queda una línea corta (eco del system prompt).
    if len(parts) >= 2 and len(last) < 140 and len(first) > max(3 * max(len(last), 15), 200):
        return first
    return last


def apply_redacted_thinking_strip(texto: str) -> str:
    """
    Aplica strip_redacted_thinking salvo que PYGENESIS_STRIP_REDACTED_THINKING=false
    (útil para depurar o dejar ver el thinking en bruto en el plugin).
    """
    v = (os.getenv("PYGENESIS_STRIP_REDACTED_THINKING") or "true").strip().lower()
    if v in ("0", "false", "off", "no"):
        return (texto or "").strip()
    return strip_redacted_thinking(texto or "")
