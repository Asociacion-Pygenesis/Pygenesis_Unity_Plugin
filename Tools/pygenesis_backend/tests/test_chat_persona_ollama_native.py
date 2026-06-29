"""PYGENESIS_CHAT_PERSONA=ollama_native — alinear chat del plugin con `ollama run`."""

from reasoning.chat_prompts import build_chat_system_prompt, chat_persona_mode


def test_ollama_native_empty_system_on_generic_question(monkeypatch):
    monkeypatch.setenv("PYGENESIS_CHAT_PERSONA", "ollama_native")
    assert chat_persona_mode() == "ollama_native"
    s = build_chat_system_prompt(last_user_message="¿Cómo guardo datos del jugador en JSON?")
    assert s == ""


def test_ollama_native_no_bridge_no_hint(monkeypatch):
    monkeypatch.setenv("PYGENESIS_CHAT_PERSONA", "ollama_native")
    s = build_chat_system_prompt(last_user_message="Hola")
    assert "Contexto operativo PyGenesis" not in s
    assert "Automatización PyGenesis" not in s
    assert "especialista senior" not in s


def test_ollama_native_includes_script_contract_when_asked(monkeypatch):
    monkeypatch.setenv("PYGENESIS_CHAT_PERSONA", "ollama_native")
    s = build_chat_system_prompt(last_user_message="Hazme un script completo PlayerSave.cs")
    assert "---PYGENESIS_CREATE_SCRIPT---" in s
    assert "Contexto operativo" not in s


def test_prepare_chat_omits_system_message_when_native_empty(monkeypatch):
    import services.chat_service as chat_service
    from config.models import AppSettings, LLMSettings
    from models import ChatMessage, ChatRequest

    monkeypatch.setenv("PYGENESIS_CHAT_PERSONA", "ollama_native")
    settings = AppSettings(llm=LLMSettings(provider="ollama", model="m"))
    req = ChatRequest(messages=[ChatMessage(role="user", content="¿Rigidbody o CharacterController?")])
    prep = chat_service._prepare_chat(settings, req)
    assert not any(m.get("role") == "system" for m in prep["api_messages"])
    assert len(prep["system_text"].strip()) == 0


def test_ollama_native_ignores_empty_assistant_and_history(monkeypatch):
    import services.chat_service as chat_service
    from config.models import AppSettings, LLMSettings
    from models import ChatMessage, ChatRequest

    monkeypatch.setenv("PYGENESIS_CHAT_PERSONA", "ollama_native")
    settings = AppSettings(llm=LLMSettings(provider="ollama", model="m"))
    req = ChatRequest(
        messages=[
            ChatMessage(role="user", content="pregunta antigua"),
            ChatMessage(role="assistant", content="respuesta antigua larga"),
            ChatMessage(role="user", content="pregunta actual"),
            ChatMessage(role="assistant", content=""),
        ]
    )
    prep = chat_service._prepare_chat(settings, req)
    assert prep["api_messages"] == [{"role": "user", "content": "pregunta actual"}]
