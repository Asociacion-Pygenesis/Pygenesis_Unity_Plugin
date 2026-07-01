"""POST a /chat/completions con reintentos ante 429/503 (rate limit, sobrecarga)."""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Any

import httpx

from providers.llm_http_errors import LLMProviderHttpError, map_upstream_status_to_client

logger = logging.getLogger("pygenesis")


def _retry_max() -> int:
    try:
        return max(0, int((os.getenv("PYGENESIS_LLM_RETRY_MAX") or "4").strip()))
    except ValueError:
        return 4


def _retry_delay_base() -> float:
    try:
        return float((os.getenv("PYGENESIS_LLM_RETRY_DELAY_SEC") or "2.0").strip())
    except ValueError:
        return 2.0


def post_chat_completions(
    *,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout: httpx.Timeout,
) -> httpx.Response:
    """
    POST JSON; si la API responde 429 o 503, reintenta hasta PYGENESIS_LLM_RETRY_MAX veces
    con backoff exponencial (útil con Gemini / OpenAI cuando hay rate limit).
    """
    max_retries = _retry_max()
    base_delay = _retry_delay_base()

    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=body)
        attempt = 0
        while response.status_code in (429, 503) and attempt < max_retries:
            delay = base_delay * (2**attempt) + random.uniform(0, 0.9)
            logger.warning(
                "API LLM HTTP %s (%s); reintentando en %.1fs (%d/%d)",
                response.status_code,
                response.text[:200].replace("\n", " "),
                delay,
                attempt + 1,
                max_retries,
            )
            time.sleep(delay)
            response = client.post(url, headers=headers, json=body)
            attempt += 1

        return response


def raise_if_http_error(response: httpx.Response) -> None:
    if response.is_success:
        return
    body = (response.text or "")[:8000]
    msg = f"LLM API HTTP {response.status_code}"
    if body:
        msg += f": {body[:2000]}"
    client_code = map_upstream_status_to_client(response.status_code)
    raise LLMProviderHttpError(msg, status_code=client_code, response_body=body)
