"""Carga bloqueante del LLM al arrancar el backend (hasta primera respuesta del modelo)."""

from __future__ import annotations

import logging
import os

from config.models import AppSettings
from config.settings_loader import load_settings
from providers.factory import build_provider
from providers.qwen_thinking_strip import apply_redacted_thinking_strip
from services.chat_passthrough import is_bridge_provider

logger = logging.getLogger("pygenesis")


def _effective_reasoning_mode(settings: AppSettings) -> str:
    for key in ("PYGENESIS_REASONING_MODE", "PYGENESIS_REASONING"):
        raw = os.environ.get(key)
        if raw and str(raw).strip():
            return str(raw).strip().lower()
    return (settings.reasoning_mode or "rules").strip().lower()


def run_blocking_llm_startup(settings: AppSettings | None = None) -> tuple[str | None, str | None]:
    """
    En modo `rules` no usa LLM.
    En `llm` / `hybrid` hace una petición corta para cargar el modelo y validar respuesta.

    Returns:
        (preview, None) si ok — texto corto para /health.
        (None, mensaje_error) si falla.
    """
    if settings is None:
        settings = load_settings()

    mode = _effective_reasoning_mode(settings)
    if mode == "rules":
        return ("(motor rules, sin LLM)", None)

    try:
        provider = build_provider(settings.llm)
        if is_bridge_provider(settings):
            health_fn = getattr(provider, "health", None)
            if callable(health_fn):
                h = health_fn()
                if (h or {}).get("status") not in ("ok", "unknown"):
                    return (
                        None,
                        f"Puente de inferencia no disponible: {h!r}. "
                        "Arranca Tools/pygenesis_inference/start_bridge.ps1",
                    )
            complete_fn = getattr(provider, "bridge_complete", None)
            if callable(complete_fn):
                raw = complete_fn(user_message="Di únicamente la palabra: listo.", max_tokens=32)
            else:
                raw = provider.generate_json(
                    system_prompt="Responde en una sola palabra en español.",
                    user_prompt="Di únicamente la palabra: listo.",
                )
        else:
            raw = provider.generate_json(
                system_prompt=(
                    "Eres Pygenesis AI, asistente de Unity. Responde en una sola frase corta en español, "
                    "sin bloques de razonamiento ni JSON."
                ),
                user_prompt="Di únicamente la palabra: listo.",
            )
        cleaned = apply_redacted_thinking_strip(raw or "").strip()
        if not cleaned:
            return (
                None,
                "El LLM devolvió texto vacío tras quitar thinking; revisa Ollama, num_ctx o el modelo.",
            )

        preview = cleaned.replace("\n", " ")
        if len(preview) > 500:
            preview = preview[:497] + "..."
        logger.info("LLM arranque OK (%d caracteres útiles)", len(cleaned))
        return (preview, None)
    except Exception as ex:
        logger.exception("LLM arranque fallido: %s", ex)
        return (None, str(ex))


def run_llm_warmup() -> str | None:
    """Compatibilidad: misma lógica que el arranque bloqueante, sin lanzar."""
    preview, err = run_blocking_llm_startup()
    if err:
        logger.warning("run_llm_warmup: %s", err)
    return preview
