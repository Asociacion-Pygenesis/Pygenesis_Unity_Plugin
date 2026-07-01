"""Streaming de /chat: filtrado incremental del marcador y eventos delta/done."""

import services.chat_service as chat_service
from config.models import AppSettings, LLMSettings
from models import ChatMessage, ChatRequest
from services.chat_service import _stream_visible_upto, run_chat_stream


class _FakeStreamProvider:
    def __init__(self, pieces):
        self._pieces = pieces

    def chat_completion_stream(self, *, messages, temperature, max_tokens):
        for p in self._pieces:
            yield p


def _settings():
    return AppSettings(reasoning_mode="hybrid", llm=LLMSettings(provider="ollama", model="m"))


def _request(text="¿Cómo uso un Rigidbody?"):
    return ChatRequest(messages=[ChatMessage(role="user", content=text)], scene_name="X")


def test_stream_visible_upto_no_marker_retains_tail():
    full = "Hola mundo"
    safe, hidden = _stream_visible_upto(full, hidden=False)
    assert hidden is False
    # Retiene una cola para evitar mostrar el marcador partido.
    assert safe < len(full)


def test_stream_visible_upto_hides_from_marker():
    full = "Texto visible\n---PYGENESIS_CREATE_SCRIPT---\n{...}"
    safe, hidden = _stream_visible_upto(full, hidden=False)
    assert hidden is True
    assert full[:safe] == "Texto visible\n"


def test_run_chat_stream_emits_deltas_and_done(monkeypatch):
    pieces = ["Para ", "usar ", "un Rigidbody ", "añade el componente."]
    monkeypatch.setattr(chat_service, "build_provider", lambda llm: _FakeStreamProvider(pieces))

    events = list(run_chat_stream(_settings(), _request()))

    deltas = [e for e in events if e["type"] == "delta"]
    done = [e for e in events if e["type"] == "done"]
    assert deltas, "debe emitir al menos un fragmento"
    assert len(done) == 1
    streamed = "".join(e["text"] for e in deltas)
    assert "Rigidbody" in done[0]["content"]
    # El texto en streaming es un prefijo del contenido final (la cola se retiene hasta 'done').
    assert done[0]["content"].startswith(streamed)
    assert done[0]["metadata"]["model"] == "m"
    assert done[0]["metadata"]["create_script_in_response"] is False


def test_run_chat_stream_extracts_create_script(monkeypatch):
    pieces = [
        "Aquí tienes el script:\n\n```csharp\n",
        "using UnityEngine;\npublic class PlayerMove : MonoBehaviour {}\n",
        "```\n",
        "---PYGENESIS_CREATE_SCRIPT---\n",
        '{"fileName":"PlayerMove.cs"}\n',
        "---PYGENESIS_SCRIPT_END---\n",
    ]
    monkeypatch.setattr(chat_service, "build_provider", lambda llm: _FakeStreamProvider(pieces))

    events = list(run_chat_stream(_settings(), _request("Hazme un script de movimiento")))
    done = [e for e in events if e["type"] == "done"][0]

    # El bloque de marcadores no aparece en el contenido visible.
    assert "PYGENESIS_CREATE_SCRIPT" not in done["content"]
    assert done["metadata"]["create_script_in_response"] is True
    assert done["metadata"]["create_script"]["asset_path"] == "Assets/Scripts/PlayerMove.cs"

    # Ningún fragmento mostrado debe contener el marcador.
    for e in events:
        if e["type"] == "delta":
            assert "---PYGENESIS" not in e["text"]
