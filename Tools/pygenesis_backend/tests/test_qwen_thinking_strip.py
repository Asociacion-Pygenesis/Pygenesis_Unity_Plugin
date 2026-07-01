"""Filtrado de bloques thinking de Qwen3."""

from providers.qwen_thinking_strip import apply_redacted_thinking_strip, strip_redacted_thinking


def test_apply_strip_can_be_disabled(monkeypatch):
    monkeypatch.setenv("PYGENESIS_STRIP_REDACTED_THINKING", "false")
    raw = "think</think>keep"
    assert apply_redacted_thinking_strip(raw) == raw


def test_strip_loose_close_tag():
    raw = "Okay… </think> Usa Rigidbody.AddForce."
    assert strip_redacted_thinking(raw) == "Usa Rigidbody.AddForce."


def test_strip_pair_tags():
    raw = "<think>x</think>Respuesta."
    assert strip_redacted_thinking(raw) == "Respuesta."


def test_json_only_inside_redacted_block_recovered():
    """Si el modelo mete el JSON dentro del bloque thinking, no podemos borrarlo entero."""
    inner = '{"summary":"ok","issues":[],"plan":[],"execution_policy":{},"metadata":{}}'
    raw = f"<think>\n{inner}\n</think>\nresponde en español"
    out = strip_redacted_thinking(raw)
    assert '"summary"' in out
    assert out.strip().startswith("{")
    assert "responde en español" not in out


def test_long_thinking_before_loose_close_tag_short_echo_after():
    """Sin <think> de apertura: el cierre separa razonamiento largo de una línea corta (eco del prompt)."""
    thinking = "Aquí va la explicación larga sobre Rigidbody en Unity. " * 12
    raw = thinking + "</think>\nRespondes en español, salvo que el usuario pida otro idioma"
    out = strip_redacted_thinking(raw)
    assert "Rigidbody" in out
    assert "Respondes en español" not in out
