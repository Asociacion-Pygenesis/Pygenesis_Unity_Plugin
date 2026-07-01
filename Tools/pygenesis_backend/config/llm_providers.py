"""
Convenciones para proveedores LLM externos (OpenAI, Gemini API compatible con OpenAI).

Gemini expone un endpoint compatible con la API de chat de OpenAI:
https://ai.google.dev/gemini-api/docs/openai
"""

from __future__ import annotations

import os

from config.models import LLMSettings

# Endpoint OpenAI-compatible oficial de Google (Gemini).
GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"

OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"

# Modelos por defecto razonables para MVP (sobrescribibles por settings / env).
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_OLLAMA_MODEL = "pygenesis-unity"
DEFAULT_BRIDGE_BASE_URL = "http://127.0.0.1:8081/v1"


def _env_explicit(name: str) -> bool:
    return os.getenv(name) is not None and os.getenv(name, "").strip() != ""


def apply_llm_provider_defaults(llm: LLMSettings) -> None:
    """
    Ajusta base_url, api_key_env y a veces el modelo según `llm.provider`
    cuando el usuario no fijó explícitamente la variable de entorno correspondiente.

    Prioridad: variables PYGENESIS_LLM_* en el entorno > settings.json > defaults del proveedor.
    """
    p = (llm.provider or "openai_compatible").strip().lower()

    if p in ("gemini", "google"):
        if not _env_explicit("PYGENESIS_LLM_BASE_URL"):
            llm.base_url = GEMINI_OPENAI_BASE_URL
        if not _env_explicit("PYGENESIS_LLM_API_KEY_ENV"):
            llm.api_key_env = "GEMINI_API_KEY"
        if not _env_explicit("PYGENESIS_LLM_MODEL"):
            m = (llm.model or "").strip()
            if not m or m.startswith("gpt-") or m.startswith("o1") or m.startswith("o3"):
                llm.model = DEFAULT_GEMINI_MODEL
        return

    if p in ("ollama", "local"):
        if not _env_explicit("PYGENESIS_LLM_MODEL"):
            m = (llm.model or "").strip()
            if not m:
                llm.model = DEFAULT_OLLAMA_MODEL
        return

    if p in ("pygenesis_bridge", "bridge", "llama_cpp", "llamacpp"):
        if not _env_explicit("PYGENESIS_LLM_BASE_URL"):
            llm.base_url = DEFAULT_BRIDGE_BASE_URL
        if not _env_explicit("PYGENESIS_LLM_MODEL"):
            m = (llm.model or "").strip()
            if not m:
                llm.model = DEFAULT_OLLAMA_MODEL
        llm.use_json_response_format = False
        return

    if p in ("openai", "openai_compatible"):
        if not _env_explicit("PYGENESIS_LLM_API_KEY_ENV"):
            if (llm.api_key_env or "").upper() == "GEMINI_API_KEY" or not (llm.api_key_env or "").strip():
                llm.api_key_env = "OPENAI_API_KEY"
        if not _env_explicit("PYGENESIS_LLM_BASE_URL"):
            if GEMINI_OPENAI_BASE_URL in (llm.base_url or ""):
                llm.base_url = OPENAI_DEFAULT_BASE_URL
        if not _env_explicit("PYGENESIS_LLM_MODEL"):
            m = (llm.model or "").strip()
            if m.startswith("gemini-"):
                llm.model = DEFAULT_OPENAI_MODEL
