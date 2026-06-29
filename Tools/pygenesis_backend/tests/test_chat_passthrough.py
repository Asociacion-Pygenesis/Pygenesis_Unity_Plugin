"""Chat en modo passthrough (puente PyGenesis)."""

import services.chat_service as chat_service
from config.models import AppSettings, LLMSettings
from models import ChatMessage, ChatRequest
from services.chat_passthrough import chat_passthrough_enabled
from services.chat_service import run_chat, run_chat_stream


class _FakeStreamProvider:
    def __init__(self, pieces):
        self._pieces = pieces

    def chat_completion_stream(self, *, messages, temperature, max_tokens):
        for p in self._pieces:
            yield p

    def chat_completion(self, *, messages, temperature, max_tokens):
        return "".join(self._pieces)


def test_passthrough_enabled_for_bridge_provider(monkeypatch):
    monkeypatch.delenv("PYGENESIS_CHAT_POSTPROCESS", raising=False)
    s = AppSettings(llm=LLMSettings(provider="pygenesis_bridge"))
    assert chat_passthrough_enabled(s) is True


def test_passthrough_disabled_when_postprocess_on(monkeypatch):
    monkeypatch.setenv("PYGENESIS_CHAT_POSTPROCESS", "on")
    s = AppSettings(llm=LLMSettings(provider="pygenesis_bridge"))
    assert chat_passthrough_enabled(s) is False


def test_passthrough_enabled_for_bridge_url(monkeypatch):
    monkeypatch.delenv("PYGENESIS_CHAT_POSTPROCESS", raising=False)
    monkeypatch.setenv("PYGENESIS_BRIDGE_URL", "http://127.0.0.1:8081/v1")
    s = AppSettings(llm=LLMSettings(provider="ollama", base_url="http://127.0.0.1:8081/v1"))
    assert chat_passthrough_enabled(s) is True


def test_run_chat_stream_passthrough_strips_leading_source(monkeypatch):
    monkeypatch.setenv("PYGENESIS_CHAT_POSTPROCESS", "passthrough")
    pieces = ["[Fuente manual: x]\n\n", "1. ARQUITECTURA\n", "más texto."]
    monkeypatch.setattr(chat_service, "build_provider", lambda llm: _FakeStreamProvider(pieces))

    events = list(
        run_chat_stream(
            AppSettings(llm=LLMSettings(provider="ollama", model="m")),
            ChatRequest(messages=[ChatMessage(role="user", content="hola")]),
        )
    )
    deltas = [e for e in events if e["type"] == "delta"]
    done = [e for e in events if e["type"] == "done"][0]

    visible = "".join(d["text"] for d in deltas)
    assert "[Fuente manual" not in visible
    assert visible.startswith("1. ARQUITECTURA")
    assert "más texto." in visible
    assert done["content"] == visible.strip()
    assert done["metadata"]["passthrough"] is True
    assert done["metadata"]["raw_chars"] == len("".join(pieces))


def test_run_chat_passthrough_strips_source(monkeypatch):
    monkeypatch.setenv("PYGENESIS_CHAT_POSTPROCESS", "off")
    text = "[Fuente manual Unity — Rigidbody]\n\n1. ARQUITECTURA: intro."
    monkeypatch.setattr(
        chat_service,
        "build_provider",
        lambda llm: _FakeStreamProvider([text]),
    )
    resp = run_chat(
        AppSettings(llm=LLMSettings(provider="pygenesis_bridge", model="m")),
        ChatRequest(messages=[ChatMessage(role="user", content="hola")]),
    )
    assert resp.content == "1. ARQUITECTURA: intro."
    assert resp.metadata["passthrough"] is True


def test_run_chat_passthrough_no_finalize(monkeypatch):
    monkeypatch.setenv("PYGENESIS_CHAT_POSTPROCESS", "off")
    text = "Respuesta cruda con Felicidades al final"
    monkeypatch.setattr(
        chat_service,
        "build_provider",
        lambda llm: _FakeStreamProvider([text]),
    )
    resp = run_chat(
        AppSettings(llm=LLMSettings(provider="pygenesis_bridge", model="m")),
        ChatRequest(messages=[ChatMessage(role="user", content="hola")]),
    )
    assert resp.content == text
    assert resp.metadata["passthrough"] is True
    assert "Felicidades" in resp.content
