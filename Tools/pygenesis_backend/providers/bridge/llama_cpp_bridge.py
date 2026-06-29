"""
Proveedor llama.cpp (llama-server) — passthrough sin Ollama.

Habla con llama-server en modo OpenAI-compatible pero el body lo construye
solo desde model_config.yaml (system + user, sampling del config).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Iterator, Optional

import httpx

from config.models import LLMSettings
from providers.bridge.config import (
    BridgeConfig,
    bridge_inject_system_prompt,
    bridge_minimal_api_body,
    load_bridge_config,
)
from providers.llm_client import post_chat_completions, raise_if_http_error
from providers.llm_http_errors import LLMProviderHttpError
from providers.openai_compatible import _extract_assistant_text
from providers.qwen_thinking_strip import apply_redacted_thinking_strip

logger = logging.getLogger("pygenesis")


def _bridge_base_url(settings: LLMSettings, config: BridgeConfig) -> str:
    raw = (os.getenv("PYGENESIS_BRIDGE_URL") or settings.base_url or config.base_url).strip()
    if not raw:
        return config.base_url
    return raw.rstrip("/")


def _last_user_message(messages: list[dict[str, Any]]) -> str:
    for m in reversed(messages):
        if (m.get("role") or "").strip().lower() == "user":
            return str(m.get("content") or "").strip()
    return ""


def _optional_system_from_messages(messages: list[dict[str, Any]]) -> Optional[str]:
    """Si el caller envió system explícito (p. ej. contrato script), respetarlo."""
    for m in messages:
        if (m.get("role") or "").strip().lower() == "system":
            text = str(m.get("content") or "").strip()
            if text:
                return text
    return None


class LlamaCppBridgeProvider:
    """Puente PyGenesis → llama-server. Compatible con chat_service existente."""

    def __init__(self, settings: LLMSettings, config: Optional[BridgeConfig] = None):
        self.settings = settings
        self.config = config or load_bridge_config()
        self.base_url = _bridge_base_url(settings, self.config)
        logger.info(
            "PyGenesis bridge: model=%s url=%s config=%s inject_system=%s minimal_api=%s",
            self.config.model_id,
            self.base_url,
            self.config.inference_root,
            bridge_inject_system_prompt(),
            bridge_minimal_api_body(),
        )

    def _passthrough_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        user = _last_user_message(messages)
        if not user:
            raise ValueError("Se requiere al menos un mensaje user para el puente de inferencia.")
        explicit_system: Optional[str] = None
        if bridge_inject_system_prompt():
            explicit_system = _optional_system_from_messages(messages)
        return self.config.build_messages(user, system_override=explicit_system)

    def _build_body(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: Optional[float],
        max_tokens: Optional[int],
        stream: bool,
    ) -> dict[str, Any]:
        passthrough = self._passthrough_messages(messages)
        if bridge_minimal_api_body():
            return {
                "model": self.config.model_id,
                "messages": passthrough,
                "stream": stream,
            }
        s = self.config.sampling
        body: dict[str, Any] = {
            "model": self.config.model_id,
            "messages": passthrough,
            "stream": stream,
            "temperature": s.temperature if temperature is None else temperature,
            "top_p": s.top_p,
            "top_k": s.top_k,
            "repeat_penalty": s.repeat_penalty,
            "presence_penalty": s.presence_penalty,
        }
        if self.config.stop:
            body["stop"] = list(self.config.stop)
        limit = max_tokens if max_tokens is not None else s.num_predict
        if limit and limit > 0:
            body["max_tokens"] = limit
        return body

    def _timeout(self) -> httpx.Timeout:
        read_s = float(self.settings.timeout_seconds)
        return httpx.Timeout(connect=30.0, read=read_s, write=60.0, pool=30.0)

    def _chat_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def health(self) -> dict:
        """GET /health del llama-server (si existe) o HEAD al completions."""
        root = self.base_url.replace("/v1", "").rstrip("/")
        try:
            with httpx.Client(timeout=httpx.Timeout(5.0)) as client:
                for path in ("/health", "/v1/models", "/"):
                    r = client.get(f"{root}{path}")
                    if r.status_code < 500:
                        return {"status": "ok", "http": r.status_code, "path": path}
        except httpx.HTTPError as ex:
            return {"status": "error", "detail": str(ex)}
        return {"status": "unknown"}

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self.chat_completion(messages=messages, temperature=None, max_tokens=self.settings.max_tokens)

    def chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> str:
        body = self._build_body(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        url = self._chat_url()
        timeout = self._timeout()
        try:
            response = post_chat_completions(url=url, headers={"Content-Type": "application/json"}, body=body, timeout=timeout)
        except httpx.TimeoutException as ex:
            raise LLMProviderHttpError(
                f"Puente llama.cpp: tiempo de espera agotado (timeout={self.settings.timeout_seconds}s).",
                status_code=504,
            ) from ex
        raise_if_http_error(response)
        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("Puente llama.cpp: respuesta sin choices")
        return apply_redacted_thinking_strip(_extract_assistant_text(choices[0], payload))

    def chat_completion_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> Iterator[str]:
        body = self._build_body(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        url = self._chat_url()
        timeout = self._timeout()

        def _generate() -> Iterator[str]:
            finish_reason: Optional[str] = None
            try:
                with httpx.Client(timeout=timeout) as client:
                    with client.stream(
                        "POST",
                        url,
                        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
                        json=body,
                    ) as response:
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
                            if not data or data == "[DONE]":
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
                    "Puente llama.cpp: tiempo de espera agotado durante streaming.",
                    status_code=504,
                ) from ex
            if finish_reason:
                logger.info("Bridge stream finish_reason=%s", finish_reason)

        return _generate()

    # API directa del protocolo InferenceBridge
    def bridge_complete(
        self,
        *,
        user_message: str,
        system_override: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        msgs = self.config.build_messages(user_message, system_override=system_override)
        return self.chat_completion(messages=msgs, temperature=self.config.sampling.temperature, max_tokens=max_tokens)

    def bridge_complete_stream(
        self,
        *,
        user_message: str,
        system_override: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        msgs = self.config.build_messages(user_message, system_override=system_override)
        return self.chat_completion_stream(
            messages=msgs,
            temperature=self.config.sampling.temperature,
            max_tokens=max_tokens,
        )
