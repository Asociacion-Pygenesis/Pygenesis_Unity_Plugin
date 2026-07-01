from config.models import LLMSettings
from providers.bridge.llama_cpp_bridge import LlamaCppBridgeProvider
from providers.openai_compatible import OpenAICompatibleProvider


def build_provider(settings: LLMSettings):
    provider = settings.provider.strip().lower()

    if provider in ("pygenesis_bridge", "bridge", "llama_cpp", "llamacpp"):
        return LlamaCppBridgeProvider(settings)

    if provider in {
        "openai",
        "openai_compatible",
        "gemini",
        "google",
        "ollama",
        "local",
    }:
        return OpenAICompatibleProvider(settings)

    raise ValueError(f"Unsupported LLM provider: {settings.provider}")