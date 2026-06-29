"""Defaults de proveedores OpenAI / Gemini."""

import json
from pathlib import Path

import pytest

from config.llm_providers import (
    DEFAULT_OLLAMA_MODEL,
    GEMINI_OPENAI_BASE_URL,
    apply_llm_provider_defaults,
)
from config.models import LLMSettings


def test_apply_gemini_defaults_overrides_openai_json_fields(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PYGENESIS_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("PYGENESIS_LLM_MODEL", raising=False)
    monkeypatch.delenv("PYGENESIS_LLM_API_KEY_ENV", raising=False)
    llm = LLMSettings(
        provider="gemini",
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
    )
    apply_llm_provider_defaults(llm)
    assert llm.base_url == GEMINI_OPENAI_BASE_URL
    assert llm.api_key_env == "GEMINI_API_KEY"
    assert "gemini" in llm.model.lower()


def test_apply_ollama_default_model_when_empty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PYGENESIS_LLM_MODEL", raising=False)
    llm = LLMSettings(
        provider="ollama",
        model="",
        base_url="http://127.0.0.1:11434/v1",
    )
    apply_llm_provider_defaults(llm)
    assert llm.model == DEFAULT_OLLAMA_MODEL


def test_apply_ollama_keeps_explicit_model_from_json(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PYGENESIS_LLM_MODEL", raising=False)
    llm = LLMSettings(
        provider="ollama",
        model="custom-model",
        base_url="http://127.0.0.1:11434/v1",
    )
    apply_llm_provider_defaults(llm)
    assert llm.model == "custom-model"


def test_apply_openai_keeps_ollama_base_from_json(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PYGENESIS_LLM_BASE_URL", raising=False)
    llm = LLMSettings(
        provider="openai_compatible",
        model="mistral",
        base_url="http://127.0.0.1:11434/v1",
        api_key_env="OPENAI_API_KEY",
    )
    apply_llm_provider_defaults(llm)
    assert llm.base_url == "http://127.0.0.1:11434/v1"


def test_explicit_env_base_url_not_overwritten(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PYGENESIS_LLM_BASE_URL", "https://custom.example/v1")
    # Tras merge en load_settings, base_url ya sería custom; apply no debe pisarla.
    llm = LLMSettings(
        provider="gemini",
        model="gemini-1.5-flash",
        base_url="https://custom.example/v1",
    )
    apply_llm_provider_defaults(llm)
    assert llm.base_url == "https://custom.example/v1"


def test_load_settings_applies_gemini_when_provider_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from config import settings_loader

    monkeypatch.setattr(settings_loader, "_load_dotenv_for_local_development", lambda: None)
    monkeypatch.setenv("PYGENESIS_LLM_PROVIDER", "gemini")
    monkeypatch.delenv("PYGENESIS_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("PYGENESIS_LLM_MODEL", raising=False)
    monkeypatch.delenv("PYGENESIS_LLM_API_KEY_ENV", raising=False)

    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "reasoning_mode": "rules",
                "llm": {
                    "provider": "openai_compatible",
                    "model": "gpt-4o-mini",
                    "base_url": "https://api.openai.com/v1",
                    "api_key_env": "OPENAI_API_KEY",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_loader, "DEFAULT_SETTINGS_PATH", settings_path)

    s = settings_loader.load_settings()
    assert GEMINI_OPENAI_BASE_URL in s.llm.base_url
    assert s.llm.api_key_env == "GEMINI_API_KEY"
