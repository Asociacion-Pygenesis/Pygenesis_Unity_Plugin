"""Tests de chat: capacidades estáticas y validación de historial."""

import pytest

from models import ChatMessage, ChatRequest
from reasoning.chat_prompts import get_capabilities_payload
from services.chat_service import run_chat


def test_capabilities_payload_structure():
    d = get_capabilities_payload()
    assert d["assistant"] == "Pygenesis AI"
    assert "greeting" in d and len(d["greeting"]) > 10
    assert isinstance(d["capabilities"], list)
    assert len(d["capabilities"]) >= 7
    ids = {c["id"] for c in d["capabilities"]}
    assert "objects_scenes" in ids
    assert "official_docs" in ids
    assert "rag_allowlist" in ids
    assert "csharp" in ids
    assert "create_script_assets" in ids


def test_chat_requires_at_least_one_user_message():
    from config.settings_loader import load_settings

    settings = load_settings()
    req = ChatRequest(messages=[ChatMessage(role="assistant", content="solo asistente")])
    with pytest.raises(ValueError, match="user"):
        run_chat(settings, req)
