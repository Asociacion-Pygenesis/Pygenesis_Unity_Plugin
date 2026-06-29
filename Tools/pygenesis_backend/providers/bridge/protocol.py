"""Contrato del puente de inferencia (independiente de Ollama)."""

from __future__ import annotations

from typing import Iterator, Optional, Protocol


class InferenceBridge(Protocol):
  def health(self) -> dict: ...

  def chat_completion_stream(
      self,
      *,
      user_message: str,
      system_override: Optional[str] = None,
      max_tokens: Optional[int] = None,
  ) -> Iterator[str]: ...

  def chat_completion(
      self,
      *,
      user_message: str,
      system_override: Optional[str] = None,
      max_tokens: Optional[int] = None,
  ) -> str: ...
