from typing import Optional

from pydantic import BaseModel, Field


class LLMSettings(BaseModel):
    provider: str = Field(
        default="openai_compatible",
        description="openai | openai_compatible | gemini | google | ollama | local (Gemini: API OpenAI-compatible de Google).",
    )
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_seconds: int = 60
    temperature: float = 0.2
    top_p: float = 0.9
    # Ollama / backends locales suelen aceptarlo; OpenAI oficial ignora claves extra — no se envía salvo ollama|local.
    repeat_penalty: Optional[float] = 1.18
    # Si false, no se envía response_format json_object (útil en servidores locales sin soporte OpenAI).
    use_json_response_format: bool = True
    # Limita tokens de salida (inferencia local lenta si el modelo intenta generar demasiado).
    max_tokens: Optional[int] = 2048
    # Modo conversacional (/chat)
    chat_max_tokens: Optional[int] = 2048
    chat_max_history_messages: int = 24
    # Si None, en chat se usa `temperature`.
    chat_temperature: Optional[float] = None


class AppSettings(BaseModel):
    reasoning_mode: str = "rules"
    llm: LLMSettings = Field(default_factory=LLMSettings)
