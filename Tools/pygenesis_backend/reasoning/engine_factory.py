# reasoning/engine_factory.py
from __future__ import annotations
import os
import logging
from typing import Any, Mapping

from reasoning.engine import ReasoningEngine

logger = logging.getLogger("pygenesis")

# Nombre de variable de entorno (prioridad sobre settings.reasoning_mode)
ENV_REASONING_MODE = "PYGENESIS_REASONING_MODE"


def _resolved_reasoning_mode(settings: Any) -> str:
    env = os.getenv(ENV_REASONING_MODE)
    if env:
        return env.strip().lower()
    if isinstance(settings, Mapping):
        return str(settings.get("reasoning_mode", "hybrid")).strip().lower()
    rm = getattr(settings, "reasoning_mode", "hybrid")
    return str(rm or "hybrid").strip().lower()


def create_engine(settings: Any, provider) -> ReasoningEngine:
    """
    Instancia el motor de razonamiento según reasoning_mode en settings.

    Modos:
      - "rules"  → solo reglas, sin LLM
      - "llm"    → solo LLM, con fallback a reglas si falla
      - "hybrid" → reglas como prefiltro + LLM refinador (recomendado)
    """
    mode = _resolved_reasoning_mode(settings)

    logger.info("Creating reasoning engine: mode=%s", mode)

    if mode == "rules":
        from reasoning.rules_engine import RulesEngine
        return RulesEngine()

    if mode == "llm":
        from reasoning.llm_engine import LLMEngine
        from reasoning.rules_engine import RulesEngine
        fallback = RulesEngine()
        return LLMEngine(provider, fallback=fallback)

    if mode == "hybrid":
        from reasoning.llm_engine import LLMEngine
        from reasoning.hybrid_engine import HybridEngine
        from reasoning.rules_engine import RulesEngine
        fallback = RulesEngine()
        llm = LLMEngine(provider, fallback=fallback)
        return HybridEngine(llm_engine=llm)

    logger.warning("Unknown reasoning_mode '%s', defaulting to hybrid", mode)
    from reasoning.llm_engine import LLMEngine
    from reasoning.hybrid_engine import HybridEngine
    llm = LLMEngine(provider)
    return HybridEngine(llm_engine=llm)


# Alias por compatibilidad con imports antiguos (`reasoning.__init__`, etc.)
build_reasoning_engine = create_engine