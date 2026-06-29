"""Recorte del historial de chat por caracteres."""

from models import ChatMessage
from services import chat_service


def test_truncate_history_drops_oldest_when_over_char_limit(monkeypatch):
    monkeypatch.setenv("PYGENESIS_CHAT_MAX_HISTORY_CHARS", "200")
    msgs = [
        ChatMessage(role="user", content="A" * 200),
        ChatMessage(role="assistant", content="B" * 200),
        ChatMessage(role="user", content="pregunta reciente"),
        ChatMessage(role="assistant", content="respuesta reciente"),
    ]
    out = chat_service._truncate_history(msgs, max_messages=24)
    assert len(out) == 2
    assert out[0].content == "pregunta reciente"
    assert out[1].content == "respuesta reciente"
