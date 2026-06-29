import json
import logging
import os
from typing import Any, Iterator, Optional

import httpx

from config.models import LLMSettings
from config.settings_loader import resolve_api_key
from providers.llm_client import post_chat_completions, raise_if_http_error
from providers.llm_http_errors import LLMProviderHttpError
from providers.qwen_thinking_strip import apply_redacted_thinking_strip

logger = logging.getLogger("pygenesis")

_IM_END = "<|" + "im" + "_" + "end" + "|>"
_IM_START = "<|" + "im" + "_" + "start" + "|>"


def _ollama_use_modelfile_defaults() -> bool:
    """ollama_native: no sobrescribir sampling del Modelfile (≈ ollama run)."""
    try:
        from reasoning.chat_prompts import chat_persona_mode

        return chat_persona_mode() == "ollama_native"
    except Exception:  # noqa: BLE001
        return False


def _merge_sampling_options(settings: LLMSettings, body: dict[str, Any], *, temperature: float) -> None:
    """temperature + top_p; repeat_penalty y top_k solo para backends tipo Ollama (API compatible OpenAI)."""
    prov = (settings.provider or "").strip().lower()
    if prov in ("ollama", "local") and _ollama_use_modelfile_defaults():
        body["temperature"] = temperature
        logger.debug("Ollama API: sampling del Modelfile (ollama_native); solo temperature en el body")
        return

    body["temperature"] = temperature
    body["top_p"] = settings.top_p
    prov = (settings.provider or "").strip().lower()
    if prov in ("ollama", "local") and settings.repeat_penalty is not None:
        body["repeat_penalty"] = settings.repeat_penalty
    if prov in ("ollama", "local"):
        raw_top_k = os.getenv("PYGENESIS_OLLAMA_TOP_K")
        if raw_top_k is None or not raw_top_k.strip():
            body["top_k"] = 40
        elif raw_top_k.strip().lower() not in ("", "none", "off", "false", "0"):
            try:
                body["top_k"] = int(raw_top_k.strip())
            except ValueError:
                logger.warning("PYGENESIS_OLLAMA_TOP_K=%r no es entero; se omite", raw_top_k)
        raw_pp = os.getenv("PYGENESIS_OLLAMA_PRESENCE_PENALTY")
        if raw_pp is not None and raw_pp.strip():
            try:
                body["presence_penalty"] = float(raw_pp.strip())
            except ValueError:
                logger.warning("PYGENESIS_OLLAMA_PRESENCE_PENALTY=%r no es numérico; se omite", raw_pp)


def _targets_ollama_http(settings: LLMSettings) -> bool:
    prov = (settings.provider or "").strip().lower()
    if prov in ("ollama", "local"):
        return True
    base = (settings.base_url or "").lower()
    return ":11434" in base


def _ollama_reasoning_effort_for_body() -> Optional[str]:
    raw = os.getenv("PYGENESIS_OLLAMA_REASONING_EFFORT")
    if raw is None:
        return "none"
    s = raw.strip().lower()
    if s in ("", "false", "off", "disable"):
        return None
    if s in ("none", "low", "medium", "high"):
        return s
    logger.warning("PYGENESIS_OLLAMA_REASONING_EFFORT=%r no es none|low|medium|high; se usa none", raw)
    return "none"


def _merge_ollama_reasoning_effort(settings: LLMSettings, body: dict[str, Any]) -> None:
    if not _targets_ollama_http(settings):
        return
    if _ollama_use_modelfile_defaults():
        return
    effort = _ollama_reasoning_effort_for_body()
    if effort is not None:
        body["reasoning_effort"] = effort


def _merge_ollama_stop_sequences(settings: LLMSettings, body: dict[str, Any]) -> None:
    """Tokens de parada opcionales para Ollama (evita que el modelo reabra turnos de chat)."""
    if not _targets_ollama_http(settings):
        return
    if _ollama_use_modelfile_defaults():
        # Stops ChatML del Modelfile; la API compatible a veces no los aplica igual que `ollama run`.
        body["stop"] = [_IM_END, _IM_START]
        return
    raw = os.getenv("PYGENESIS_OLLAMA_STOP")
    if raw is None:
        # Los stops van en Modelfile.pygenesis-unity; enviarlos también por API a veces corta
        # respuestas válidas antes de tiempo (~400 chars). Para forzar: PYGENESIS_OLLAMA_STOP=...
        return
    else:
        stops = [s.strip() for s in raw.split(",") if s.strip()]
        if raw.strip().lower() in ("", "none", "off", "false", "0"):
            return
    if stops:
        body["stop"] = stops


def _flatten_content_field(c: Any) -> str:
    """
    Convierte message.content (str o lista tipo OpenAI / Ollama) en texto plano.

    Omite intencionalmente los items de tipo reasoning/thinking: llegan sin etiquetas
    <think> y strip_redacted_thinking no podría filtrarlos.  La respuesta útil siempre
    está en los items type==text.
    """
    if isinstance(c, str):
        return c.strip()
    if isinstance(c, list):
        parts: list[str] = []
        for item in c:
            if isinstance(item, dict):
                typ = (item.get("type") or "text").strip().lower()
                # Saltar partes de razonamiento interno para no filtrar
                if typ in ("reasoning", "thinking", "internal_reasoning"):
                    continue
                piece = ""
                for k in ("text", "content"):
                    v = item.get(k)
                    if isinstance(v, str) and v.strip():
                        piece = v.strip()
                        break
                if piece:
                    parts.append(piece)
            elif isinstance(item, str):
                parts.append(item.strip())
        return "\n\n".join(p for p in parts if p).strip()
    return ""


def _normalize_assistant_content(message: Any) -> Optional[str]:
    """
    Unifica OpenAI / Ollama / Qwen thinking.

    Ollama con modelos tipo Qwen3 suele enviar el bloque largo en reasoning_content/thinking
    y en content solo un resumen o una línea; antes solo leíamos content y el chat en Unity
    quedaba truncado frente a la salida completa en consola (ollama run).
    """
    if not isinstance(message, dict):
        return None

    content_str = _flatten_content_field(message.get("content"))

    reasoning_parts: list[str] = []
    for key in ("reasoning_content", "reasoning", "thinking"):
        v = message.get(key)
        if isinstance(v, str) and v.strip():
            reasoning_parts.append(v.strip())
        elif isinstance(v, list) and v:
            # Ollama / algunos proxies: reasoning como lista de strings o dicts
            sub: list[str] = []
            for el in v:
                if isinstance(el, str) and el.strip():
                    sub.append(el.strip())
                elif isinstance(el, dict):
                    for k in ("text", "content", "reasoning", "thinking"):
                        t = el.get(k)
                        if isinstance(t, str) and t.strip():
                            sub.append(t.strip())
                            break
            if sub:
                reasoning_parts.append("\n".join(sub))
    r = "\n\n".join(reasoning_parts) if reasoning_parts else ""

    if r and content_str:
        # content_str es la respuesta real; r es el bloque de razonamiento procedente de campos
        # dedicados (reasoning_content / thinking / reasoning).  Nunca mezclamos ambos porque r
        # llega sin etiquetas <think> y strip_redacted_thinking no podría filtrarlo.
        # Solo usamos r como fallback si content_str es sospechosamente corto (eco del system prompt).
        if len(content_str) >= 40:
            return content_str
        return r
    if content_str:
        return content_str
    if r:
        return r
    return None


def _extract_assistant_text(choice: dict, payload: dict) -> str:
    msg = choice.get("message")
    text = _normalize_assistant_content(msg) if msg else None
    if text:
        return text
    legacy = choice.get("text")
    if isinstance(legacy, str) and legacy.strip():
        return legacy.strip()

    fr = choice.get("finish_reason")
    tool_calls = (msg or {}).get("tool_calls") if isinstance(msg, dict) else None
    preview = json.dumps(payload, ensure_ascii=False)[:2500]
    logger.error(
        "Respuesta LLM sin texto usable. finish_reason=%s tool_calls=%s choice_keys=%s payload[:2500]=%s",
        fr,
        bool(tool_calls),
        list(choice.keys()),
        preview,
    )
    hint = (
        "Si usas Ollama, suele pasar cuando el prompt supera num_ctx o el modelo devuelve solo tool_calls. "
        "Prueba: aumentar num_ctx al arrancar Ollama, reducir historial, "
        "PYGENESIS_CHAT_MAX_SYSTEM_CHARS más bajo, PYGENESIS_RAG_ENABLED=false o PYGENESIS_CHAT_KNOWLEDGE=minimal."
    )
    raise RuntimeError(f"LLM response content is empty (finish_reason={fr!r}). {hint}")


class OpenAICompatibleProvider:
    def __init__(self, settings: LLMSettings):
        self.settings = settings

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> str:
        api_key = resolve_api_key(self.settings.api_key_env)

        headers = {
            "Content-Type": "application/json",
        }

        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        body: dict[str, Any] = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        _merge_sampling_options(self.settings, body, temperature=self.settings.temperature)
        _merge_ollama_reasoning_effort(self.settings, body)
        _merge_ollama_stop_sequences(self.settings, body)
        if self.settings.max_tokens is not None and self.settings.max_tokens > 0:
            body["max_tokens"] = self.settings.max_tokens
        if self.settings.use_json_response_format:
            body["response_format"] = {"type": "json_object"}

        url = f"{self.settings.base_url.rstrip('/')}/chat/completions"

        # Lectura larga para inferencia local (Ollama/CPU); conexión corta si el host no responde.
        read_s = float(self.settings.timeout_seconds)
        timeout = httpx.Timeout(connect=30.0, read=read_s, write=60.0, pool=30.0)

        try:
            response = post_chat_completions(url=url, headers=headers, body=body, timeout=timeout)
        except httpx.TimeoutException as ex:
            raise LLMProviderHttpError(
                "Tiempo de espera del LLM agotado (conexión o lectura). "
                f"timeout_seconds configurado={read_s:.0f}. "
                "Prueba: subir PYGENESIS_LLM_TIMEOUT_SECONDS solo si el modelo lo necesita; "
                "reducir max_tokens; modo hybrid; o no usar analyze_scene en dos pasadas "
                "(PYGENESIS_SCENE_TWO_PASS=1 duplica llamadas).",
                status_code=504,
            ) from ex

        raise_if_http_error(response)
        payload = response.json()

        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response has no choices")

        return apply_redacted_thinking_strip(_extract_assistant_text(choices[0], payload))

    def chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> str:
        """Chat multi-turn compatible con OpenAI; no usa response_format json_object."""
        api_key = resolve_api_key(self.settings.api_key_env)

        headers = {
            "Content-Type": "application/json",
        }

        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        body: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
        }
        _merge_sampling_options(self.settings, body, temperature=temperature)
        _merge_ollama_reasoning_effort(self.settings, body)
        _merge_ollama_stop_sequences(self.settings, body)
        if max_tokens is not None and max_tokens > 0:
            body["max_tokens"] = max_tokens

        url = f"{self.settings.base_url.rstrip('/')}/chat/completions"

        read_s = float(self.settings.timeout_seconds)
        timeout = httpx.Timeout(connect=30.0, read=read_s, write=60.0, pool=30.0)

        try:
            response = post_chat_completions(url=url, headers=headers, body=body, timeout=timeout)
        except httpx.TimeoutException as ex:
            raise LLMProviderHttpError(
                "Tiempo de espera del LLM agotado (conexión o lectura). "
                f"timeout_seconds configurado={read_s:.0f}. "
                "Prueba: subir PYGENESIS_LLM_TIMEOUT_SECONDS; acortar historial de chat; "
                "o bajar chat_max_tokens.",
                status_code=504,
            ) from ex

        raise_if_http_error(response)
        payload = response.json()

        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response has no choices")

        return apply_redacted_thinking_strip(_extract_assistant_text(choices[0], payload))

    def chat_completion_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> Iterator[str]:
        """
        Igual que chat_completion pero en streaming (SSE compatible con OpenAI/Ollama).
        Produce los fragmentos de texto (delta.content) según los genera el modelo.

        Solo se emite delta.content; el bloque de razonamiento (delta.reasoning_content /
        thinking) se omite a propósito para no mostrar el "pensamiento" del modelo en el chat.
        """
        api_key = resolve_api_key(self.settings.api_key_env)

        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        body: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "stream": True,
        }
        _merge_sampling_options(self.settings, body, temperature=temperature)
        _merge_ollama_reasoning_effort(self.settings, body)
        _merge_ollama_stop_sequences(self.settings, body)
        if max_tokens is not None and max_tokens > 0:
            body["max_tokens"] = max_tokens

        url = f"{self.settings.base_url.rstrip('/')}/chat/completions"
        read_s = float(self.settings.timeout_seconds)
        timeout = httpx.Timeout(connect=30.0, read=read_s, write=60.0, pool=30.0)

        def _generate() -> Iterator[str]:
            finish_reason: Optional[str] = None
            try:
                with httpx.Client(timeout=timeout) as client:
                    with client.stream("POST", url, headers=headers, json=body) as response:
                        if response.status_code != 200:
                            response.read()
                            raise_if_http_error(response)
                        for raw_line in response.iter_lines():
                            if not raw_line:
                                continue
                            line = raw_line.strip()
                            if not line.startswith("data:"):
                                continue
                            data = line[len("data:") :].strip()
                            if not data:
                                continue
                            if data == "[DONE]":
                                break
                            try:
                                obj = json.loads(data)
                            except json.JSONDecodeError:
                                continue
                            choices = obj.get("choices") or []
                            if not choices:
                                continue
                            fr = choices[0].get("finish_reason")
                            if isinstance(fr, str) and fr:
                                finish_reason = fr
                            delta = choices[0].get("delta") or {}
                            piece = delta.get("content")
                            if isinstance(piece, str) and piece:
                                yield piece
            except httpx.TimeoutException as ex:
                raise LLMProviderHttpError(
                    "Tiempo de espera del LLM agotado durante el streaming. "
                    f"timeout_seconds configurado={read_s:.0f}.",
                    status_code=504,
                ) from ex
            if finish_reason:
                logger.info("Chat stream LLM finish_reason=%s", finish_reason)

        return _generate()