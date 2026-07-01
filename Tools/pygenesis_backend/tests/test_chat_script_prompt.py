"""Contrato PYGENESIS en system prompt."""

from reasoning.chat_prompts import build_chat_system_prompt


def test_general_question_omits_marker_literals(monkeypatch):
    monkeypatch.setenv("PYGENESIS_CHAT_PERSONA", "modelfile")
    s = build_chat_system_prompt(last_user_message="¿Cómo reduzco GC en botones UI?")
    assert "---PYGENESIS_CREATE_SCRIPT---" not in s


def test_script_request_also_uses_hint_only(monkeypatch):
    monkeypatch.setenv("PYGENESIS_CHAT_PERSONA", "modelfile")
    s = build_chat_system_prompt(last_user_message="Hazme un script completo de movimiento 2D")
    assert "---PYGENESIS_CREATE_SCRIPT---" not in s
    assert "no narres" in s.lower() or "No narres" in s
