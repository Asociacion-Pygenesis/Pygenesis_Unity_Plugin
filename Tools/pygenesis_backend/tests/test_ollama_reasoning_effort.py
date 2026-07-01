"""Ollama /v1/chat/completions: reasoning_effort para modelos thinking (Qwen 3)."""

import os

import pytest

from config.models import LLMSettings
from providers import openai_compatible as oc


def test_targets_ollama_by_provider():
    s = LLMSettings(provider="ollama", base_url="http://x/v1")
    assert oc._targets_ollama_http(s) is True


def test_targets_ollama_by_port_on_openai_compatible():
    s = LLMSettings(
        provider="openai_compatible",
        base_url="http://127.0.0.1:11434/v1",
    )
    assert oc._targets_ollama_http(s) is True


def test_not_targets_openai():
    s = LLMSettings(provider="openai_compatible", base_url="https://api.openai.com/v1")
    assert oc._targets_ollama_http(s) is False


@pytest.mark.parametrize(
    "env_val,expected",
    [
        (None, "none"),
        ("none", "none"),
        ("HIGH", "high"),
        ("", None),
        ("off", None),
        ("false", None),
    ],
)
def test_reasoning_effort_env(monkeypatch, env_val, expected):
    if env_val is None:
        monkeypatch.delenv("PYGENESIS_OLLAMA_REASONING_EFFORT", raising=False)
    else:
        monkeypatch.setenv("PYGENESIS_OLLAMA_REASONING_EFFORT", env_val)
    assert oc._ollama_reasoning_effort_for_body() == expected
