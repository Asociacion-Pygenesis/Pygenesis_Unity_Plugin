import json
import os
from pathlib import Path

from config.llm_providers import apply_llm_provider_defaults
from config.models import AppSettings

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parent / "settings.json"
DOTENV_PATH = BACKEND_ROOT / ".env"


def _load_dotenv_for_local_development() -> None:
    """Carga variables desde `.env` si existe (solo desarrollo; opcional si falta python-dotenv)."""
    if not DOTENV_PATH.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    # override=False: variables ya definidas en el entorno tienen prioridad
    load_dotenv(DOTENV_PATH, override=False)


def load_settings() -> AppSettings:
    _load_dotenv_for_local_development()
    if DEFAULT_SETTINGS_PATH.exists():
        with DEFAULT_SETTINGS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        settings = AppSettings(**data)
    else:
        settings = AppSettings()

    # Overrides por variables de entorno si existen
    reasoning_mode = os.getenv("PYGENESIS_REASONING_MODE") or os.getenv("PYGENESIS_REASONING")
    if reasoning_mode:
        settings.reasoning_mode = reasoning_mode.strip()

    provider = os.getenv("PYGENESIS_LLM_PROVIDER")
    if provider:
        settings.llm.provider = provider.strip()

    model = os.getenv("PYGENESIS_LLM_MODEL")
    if model:
        settings.llm.model = model.strip()

    base_url = os.getenv("PYGENESIS_LLM_BASE_URL")
    if base_url:
        settings.llm.base_url = base_url.strip()

    bridge_url = os.getenv("PYGENESIS_BRIDGE_URL")
    if bridge_url and bridge_url.strip():
        settings.llm.base_url = bridge_url.strip()

    api_key_env = os.getenv("PYGENESIS_LLM_API_KEY_ENV")
    if api_key_env:
        settings.llm.api_key_env = api_key_env.strip()

    timeout_seconds = os.getenv("PYGENESIS_LLM_TIMEOUT_SECONDS")
    if timeout_seconds:
        try:
            settings.llm.timeout_seconds = int(timeout_seconds)
        except ValueError:
            pass

    temperature = os.getenv("PYGENESIS_LLM_TEMPERATURE")
    if temperature:
        try:
            settings.llm.temperature = float(temperature)
        except ValueError:
            pass

    top_p = os.getenv("PYGENESIS_LLM_TOP_P")
    if top_p:
        try:
            settings.llm.top_p = float(top_p)
        except ValueError:
            pass

    repeat_penalty = os.getenv("PYGENESIS_LLM_REPEAT_PENALTY")
    if repeat_penalty is not None:
        repeat_penalty = repeat_penalty.strip()
        if repeat_penalty == "" or repeat_penalty.lower() in ("none", "null"):
            settings.llm.repeat_penalty = None
        else:
            try:
                settings.llm.repeat_penalty = float(repeat_penalty)
            except ValueError:
                pass

    use_json_fmt = os.getenv("PYGENESIS_LLM_USE_JSON_RESPONSE_FORMAT")
    if use_json_fmt is not None:
        settings.llm.use_json_response_format = use_json_fmt.strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    max_tok = os.getenv("PYGENESIS_LLM_MAX_TOKENS")
    if max_tok is not None:
        max_tok = max_tok.strip()
        if max_tok == "" or max_tok.lower() in ("none", "null"):
            settings.llm.max_tokens = None
        else:
            try:
                settings.llm.max_tokens = int(max_tok)
            except ValueError:
                pass

    chat_max = os.getenv("PYGENESIS_LLM_CHAT_MAX_TOKENS")
    if chat_max is not None:
        chat_max = chat_max.strip()
        if chat_max == "" or chat_max.lower() in ("none", "null"):
            settings.llm.chat_max_tokens = None
        else:
            try:
                settings.llm.chat_max_tokens = int(chat_max)
            except ValueError:
                pass

    hist = os.getenv("PYGENESIS_CHAT_MAX_HISTORY_MESSAGES")
    if hist:
        try:
            settings.llm.chat_max_history_messages = max(1, int(hist.strip()))
        except ValueError:
            pass

    chat_temp = os.getenv("PYGENESIS_LLM_CHAT_TEMPERATURE")
    if chat_temp is not None:
        chat_temp = chat_temp.strip()
        if chat_temp == "" or chat_temp.lower() in ("none", "null"):
            settings.llm.chat_temperature = None
        else:
            try:
                settings.llm.chat_temperature = float(chat_temp)
            except ValueError:
                pass

    apply_llm_provider_defaults(settings.llm)
    return settings


def resolve_api_key(env_var_name: str) -> str:
    if not env_var_name:
        return ""
    return os.environ.get(env_var_name, "").strip()