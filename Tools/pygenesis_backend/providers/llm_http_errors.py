"""Errores HTTP del proveedor LLM con código propagable al cliente."""

from __future__ import annotations

from typing import Optional


class LLMProviderHttpError(Exception):
    """Fallo al llamar a la API del LLM (OpenAI, Gemini compatible, Ollama, etc.)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
        response_body: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def map_upstream_status_to_client(upstream: int) -> int:
    """Traduce códigos de la API upstream a respuestas HTTP del backend."""
    if upstream == 429:
        return 429
    if upstream in (400, 401, 403, 404, 408, 413):
        return upstream
    if upstream == 503:
        return 503
    if upstream == 504:
        return 504
    if upstream >= 500:
        return 502
    return 502


def user_notice_for_provider_error(ex: BaseException) -> Optional[str]:
    """
    Texto breve para mostrar en summary/message cuando el LLM falla y hay fallback a reglas.
    (429 = cuota o ritmo en Google Vertex / Gemini, OpenAI, etc.)
    """
    code: Optional[int] = None
    if isinstance(ex, LLMProviderHttpError):
        code = ex.status_code
    s = str(ex)
    if code is None and "HTTP 429" in s:
        code = 429
    if code == 429:
        return (
            "[LLM no disponible: HTTP 429 — cuota o ritmo de peticiones agotado en el proveedor "
            "(p. ej. Google Gemini / Vertex). Se muestran solo reglas locales; reintenta más tarde "
            "o revisa límites en la consola de Google Cloud.]"
        )
    if code in (401, 403):
        return (
            f"[LLM no disponible: HTTP {code} — credenciales o permisos del proveedor. "
            "Se muestran solo reglas locales.]"
        )
    if code == 503:
        return (
            "[LLM no disponible: HTTP 503 — proveedor sobrecargado. Se muestran solo reglas locales; reintenta en unos minutos.]"
        )
    return None
