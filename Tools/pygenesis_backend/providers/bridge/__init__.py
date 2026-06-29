"""Puente de inferencia PyGenesis (llama.cpp, sin Ollama)."""

from providers.bridge.config import BridgeConfig, load_bridge_config
from providers.bridge.llama_cpp_bridge import LlamaCppBridgeProvider

__all__ = ["BridgeConfig", "LlamaCppBridgeProvider", "load_bridge_config"]
