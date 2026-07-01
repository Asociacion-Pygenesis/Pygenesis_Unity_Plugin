#!/usr/bin/env python3
"""
Compara la misma pregunta entre Ollama y el puente PyGenesis (llama-server).

Uso:
  cd Tools/pygenesis_backend
  .\.venv\Scripts\python.exe scripts/compare_with_ollama.py "¿Cómo muevo un objeto en Unity?"
  .\.venv\Scripts\python.exe scripts/compare_with_ollama.py --bridge-only

Requisitos:
  - Ollama con pygenesis-unity (opcional si --bridge-only)
  - llama-server en PYGENESIS_BRIDGE_URL (defecto http://127.0.0.1:8081/v1)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env", override=False)

import httpx  # noqa: E402

from config.models import LLMSettings  # noqa: E402
from providers.bridge.config import load_bridge_config  # noqa: E402
from providers.bridge.llama_cpp_bridge import LlamaCppBridgeProvider  # noqa: E402


DEFAULT_QUESTION = "¿Cómo hago un movimiento básico en Unity con un script C#?"


def ollama_native_chat(question: str, model: str, base: str) -> tuple[str, str]:
    url = base.replace("/v1", "").rstrip("/") + "/api/chat"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": question}],
        "stream": False,
    }
    r = httpx.post(url, json=body, timeout=600)
    r.raise_for_status()
    data = r.json()
    content = (data.get("message") or {}).get("content") or ""
    reason = data.get("done_reason") or "?"
    return content, reason


def bridge_chat(question: str) -> tuple[str, str]:
    settings = LLMSettings(provider="pygenesis_bridge", timeout_seconds=600)
    provider = LlamaCppBridgeProvider(settings)
    text = provider.bridge_complete(user_message=question)
    return text, "bridge"


def ratio(a: int, b: int) -> str:
    if b <= 0:
        return "n/a"
    return f"{a / b:.2%}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Comparar Ollama vs puente PyGenesis")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--bridge-only", action="store_true")
    parser.add_argument("--ollama-only", action="store_true")
    args = parser.parse_args()

    cfg = load_bridge_config()
    ollama_model = os.getenv("PYGENESIS_LLM_MODEL", "pygenesis-unity:latest")
    ollama_base = os.getenv("PYGENESIS_LLM_BASE_URL", "http://127.0.0.1:11434/v1")

    print("=== PyGenesis compare_with_ollama ===")
    print(f"Pregunta: {args.question[:120]}{'…' if len(args.question) > 120 else ''}")
    print(f"Bridge URL: {os.getenv('PYGENESIS_BRIDGE_URL', cfg.base_url)}")
    print(f"GGUF config: {cfg.resolve_gguf_path()}")
    print()

    bridge_text, bridge_reason = "", "skipped"
    ollama_text, ollama_reason = "", "skipped"

    if not args.ollama_only:
        try:
            bridge_text, bridge_reason = bridge_chat(args.question)
            print(f"[bridge] chars={len(bridge_text)} reason={bridge_reason}")
            print(bridge_text[:400].replace("\n", " ") + ("…" if len(bridge_text) > 400 else ""))
            print()
        except Exception as ex:  # noqa: BLE001
            print(f"[bridge] ERROR: {ex}")
            print()

    if not args.bridge_only:
        try:
            ollama_text, ollama_reason = ollama_native_chat(args.question, ollama_model, ollama_base)
            print(f"[ollama /api/chat] chars={len(ollama_text)} done_reason={ollama_reason}")
            print(ollama_text[:400].replace("\n", " ") + ("…" if len(ollama_text) > 400 else ""))
            print()
        except Exception as ex:  # noqa: BLE001
            print(f"[ollama] ERROR: {ex}")
            print()

    if bridge_text and ollama_text:
        print(
            f"Ratio bridge/ollama: {ratio(len(bridge_text), len(ollama_text))} "
            f"({len(bridge_text)} / {len(ollama_text)} chars)"
        )
        target = 0.90
        ok = len(bridge_text) >= int(len(ollama_text) * target)
        print(f"Umbral {target:.0%}: {'OK' if ok else 'POR DEBAJO — ajustar model_config.yaml o llama-server'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
