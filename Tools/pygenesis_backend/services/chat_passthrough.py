"""Modo passthrough: texto del modelo sin anti-bucle ni extract_script; sí quita citas [Fuente…]."""

from __future__ import annotations

import os

from config.models import AppSettings

_BRIDGE_PROVIDERS = frozenset({"pygenesis_bridge", "bridge", "llama_cpp", "llamacpp"})


def _targets_bridge_url(settings: AppSettings) -> bool:
    bridge_url = (os.getenv("PYGENESIS_BRIDGE_URL") or "").strip().lower()
    base = (settings.llm.base_url or "").strip().lower()
    for url in (bridge_url, base):
        if not url:
            continue
        if ":8081" in url or url.rstrip("/").endswith("8081"):
            return True
    return False


def chat_passthrough_enabled(settings: AppSettings) -> bool:
    """
    True = sin anti-bucle ni extract_script en visible; sí elimina citas [Fuente…] del fine-tune.
    Unity conserva el texto streameado (ya sin cita inicial); `done.content` trae el texto limpio.

    Activación:
      - PYGENESIS_LLM_PROVIDER=pygenesis_bridge (defecto passthrough)
      - PYGENESIS_BRIDGE_URL / base_url en puerto 8081 (llama-server)
      - PYGENESIS_CHAT_POSTPROCESS=off|passthrough
    """
    raw = (os.getenv("PYGENESIS_CHAT_POSTPROCESS") or "").strip().lower()
    if raw in ("on", "1", "true", "yes", "full"):
        return False
    if raw in ("off", "0", "false", "no", "passthrough"):
        return True
    prov = (settings.llm.provider or "").strip().lower()
    if prov in _BRIDGE_PROVIDERS:
        return True
    return _targets_bridge_url(settings)


def is_bridge_provider(settings: AppSettings) -> bool:
    prov = (settings.llm.provider or "").strip().lower()
    if prov in _BRIDGE_PROVIDERS:
        return True
    return _targets_bridge_url(settings)
