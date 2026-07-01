"""Extracción de texto del asistente (content + reasoning Ollama/Qwen)."""

from providers import openai_compatible as oc
from providers.qwen_thinking_strip import strip_redacted_thinking


def test_merge_reasoning_and_content_for_qwen_split():
    msg = {
        "reasoning_content": "Okay… </think>\nAquí va la explicación larga del Rigidbody.",
        "content": "Resumen una línea.",
    }
    raw = oc._normalize_assistant_content(msg)
    assert raw is not None
    cleaned = strip_redacted_thinking(raw)
    assert "explicación larga" in cleaned
    assert "Okay" not in cleaned or "explicación" in cleaned


def test_content_only_when_no_reasoning():
    msg = {"content": "Solo esto."}
    assert oc._normalize_assistant_content(msg) == "Solo esto."


def test_reasoning_only():
    msg = {"content": "", "reasoning_content": "Piensa… luego responde."}
    assert oc._normalize_assistant_content(msg) == "Piensa… luego responde."


def test_dedupe_when_content_is_substring_of_reasoning():
    msg = {
        "reasoning_content": "Prefacio largo\nRespuesta final.",
        "content": "Respuesta final.",
    }
    assert oc._normalize_assistant_content(msg) == "Prefacio largo\nRespuesta final."


def test_content_array_with_reasoning_then_text_parts():
    """Ollama puede poner la respuesta larga en partes type=reasoning del array content."""
    msg = {
        "content": [
            {
                "type": "reasoning",
                "reasoning": "Análisis largo… </think>\nAquí la respuesta útil para Unity.",
            },
            {"type": "text", "text": "Respondes en C# y en Unity."},
        ]
    }
    raw = oc._normalize_assistant_content(msg)
    assert raw is not None
    cleaned = strip_redacted_thinking(raw)
    assert "respuesta útil" in cleaned
    assert "Respondes en C#" in cleaned or "respuesta útil" in cleaned

