"""Reintento en segundo plano del warmup LLM cuando el arranque inicial falla."""

from __future__ import annotations

import asyncio
import logging
import os

from config.settings_loader import load_settings
from services.llm_warmup import run_blocking_llm_startup

logger = logging.getLogger("pygenesis")

DEFAULT_RETRY_SECONDS = 15


def warmup_retry_interval_seconds() -> float:
    raw = os.getenv("PYGENESIS_LLM_WARMUP_RETRY_SECONDS", "").strip()
    if not raw:
        return float(DEFAULT_RETRY_SECONDS)
    try:
        value = float(raw)
    except ValueError:
        return float(DEFAULT_RETRY_SECONDS)
    return max(5.0, value)


def warmup_retry_enabled() -> bool:
    raw = os.getenv("PYGENESIS_LLM_WARMUP_RETRY", "on").strip().lower()
    return raw not in ("0", "false", "no", "off")


async def apply_llm_warmup(app) -> bool:
    """Ejecuta warmup bloqueante y actualiza app.state. Devuelve True si llm_ready."""
    settings = load_settings()
    preview, err = await asyncio.to_thread(run_blocking_llm_startup, settings)
    if err:
        app.state.llm_warmup_error = err
        app.state.llm_ready = False
        return False
    app.state.llm_warmup_preview = preview
    app.state.llm_warmup_error = None
    app.state.llm_ready = True
    return True


async def llm_warmup_retry_loop(app, stop_event: asyncio.Event) -> None:
    """Reintenta warmup hasta éxito o cancelación al apagar el servidor."""
    interval = warmup_retry_interval_seconds()
    logger.info(
        "Warmup LLM falló al arrancar; reintentos cada %.0f s (PYGENESIS_LLM_WARMUP_RETRY_SECONDS).",
        interval,
    )
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            return
        except asyncio.TimeoutError:
            pass
        if getattr(app.state, "llm_ready", False):
            return
        logger.info("Reintentando warmup LLM…")
        if await apply_llm_warmup(app):
            logger.info("LLM listo tras reintento automático.")
            return
        err = getattr(app.state, "llm_warmup_error", None)
        if err:
            logger.warning("Warmup LLM sigue fallando: %s", err)
