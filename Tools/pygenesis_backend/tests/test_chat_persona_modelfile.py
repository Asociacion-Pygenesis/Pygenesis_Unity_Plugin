"""Modo PYGENESIS_CHAT_PERSONA=modelfile para modelos con persona propia en Ollama."""

from reasoning.chat_prompts import build_chat_system_prompt


def test_modelfile_persona_skips_builtin_header(monkeypatch):
    monkeypatch.setenv("PYGENESIS_CHAT_PERSONA", "modelfile")
    monkeypatch.setenv("PYGENESIS_CHAT_KNOWLEDGE", "off")
    s = build_chat_system_prompt(last_user_message="Hola")
    assert "especialista senior en desarrollo de videojuegos" not in s
    assert "Contexto operativo PyGenesis" in s
    assert "contrato de marcadores" in s or "contrato PYGENESIS" in s
    assert "---PYGENESIS_CREATE_SCRIPT---" not in s
    assert "Pygenesis AI" not in s or "Contexto operativo PyGenesis" in s


def test_modelfile_persona_omits_knowledge_on_scene_question(monkeypatch):
    monkeypatch.setenv("PYGENESIS_CHAT_PERSONA", "modelfile")
    monkeypatch.setenv("PYGENESIS_CHAT_KNOWLEDGE", "minimal")
    monkeypatch.setenv("PYGENESIS_CHAT_SCENE_CONTEXT", "always")
    s = build_chat_system_prompt(last_user_message="¿Qué luces hay en la escena?")
    assert "Fuentes oficiales" not in s
    assert "meta-comentarios" in s or "No cites manuales" in s


def test_builtin_persona_keeps_header(monkeypatch):
    monkeypatch.setenv("PYGENESIS_CHAT_PERSONA", "builtin")
    monkeypatch.setenv("PYGENESIS_CHAT_KNOWLEDGE", "off")
    s = build_chat_system_prompt(last_user_message="Hola")
    assert "especialista senior en desarrollo de videojuegos" in s
