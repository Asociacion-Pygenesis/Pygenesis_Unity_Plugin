"""Tests del cargador de conocimiento documentado (Manual Unity, C#)."""

import os

import pytest

from reasoning.chat_prompts import build_chat_system_prompt
from reasoning.knowledge_loader import build_knowledge_block


def test_knowledge_block_auto_contains_manual_link():
    text = build_knowledge_block(user_message="hola")
    assert "docs.unity3d.com/Manual" in text
    assert "learn.microsoft.com/dotnet/csharp" in text


def test_knowledge_block_prefab_matches_unity_file():
    t = build_knowledge_block(user_message="mi prefab no guarda")
    assert "unity_manual_guide.md" in t or "prefab" in t.lower()


def test_knowledge_block_off_returns_empty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PYGENESIS_CHAT_KNOWLEDGE", "off")
    assert build_knowledge_block(user_message="physics") == ""


def test_build_chat_system_prompt_includes_docs_index(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PYGENESIS_CHAT_PERSONA", "builtin")
    monkeypatch.setenv("PYGENESIS_CHAT_KNOWLEDGE", "minimal")
    s = build_chat_system_prompt(last_user_message="¿Cómo uso un Rigidbody?")
    assert "ScriptReference" in s or "docs.unity3d.com" in s


def test_minimal_mode_only_index(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PYGENESIS_CHAT_KNOWLEDGE", "minimal")
    t = build_knowledge_block(user_message="prefab scene")
    assert "docs.unity3d.com" in t
    assert "unity_manual_guide" not in t.lower()
