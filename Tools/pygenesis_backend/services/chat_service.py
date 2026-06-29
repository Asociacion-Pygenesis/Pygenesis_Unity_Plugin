"""Orquestación del chat conversacional contra el proveedor LLM."""

import logging
import os
from typing import Any, Dict, Iterator, List, Tuple

from config.models import AppSettings
from models import ChatMessage, ChatRequest, ChatResponse
from providers.factory import build_provider
from providers.repetition_guard import (
    SourceCitationStreamFilter,
    _strong_cut_reason,
    finalize_chat_visible_text,
    repair_truncated_markdown_fences,
    repetition_guard_mode,
    should_cut_stream_for_repetition,
    strip_source_citations,
)
from reasoning.chat_prompts import CHAT_SCRIPT_AUTOMATION, build_chat_system_prompt, chat_persona_mode
from reasoning.rag.retrieve import retrieve_rag_context
from services.chat_passthrough import chat_passthrough_enabled
from services.script_creation_parser import MARKER_START, extract_script_creation

logger = logging.getLogger("pygenesis")


_PYGENESIS_SCRIPT_NEEDLE = "PYGENESIS_CREATE_SCRIPT"
# Al streamear texto retenemos una cola de este tamaño para no mostrar el marcador
# de creación de script partido entre fragmentos (se oculta en cuanto aparece).
_MARKER_GUARD_LEN = len(MARKER_START)


def _truncate_system_prompt(text: str) -> Tuple[str, bool]:
    """
    Evita saturar el contexto del LLM local (p. ej. Ollama con num_ctx pequeño): demasiado
    system prompt puede hacer que la respuesta venga vacía.

    Por defecto el límite es alto: instantánea de escena + RAG + conocimiento superan 10k con facilidad;
    recortar el centro eliminaba el contrato PYGENESIS y Unity dejaba de recibir metadata.create_script.
    """
    try:
        max_c = int((os.getenv("PYGENESIS_CHAT_MAX_SYSTEM_CHARS") or "48000").strip())
    except ValueError:
        max_c = 48_000
    max_c = max(8000, min(max_c, 250_000))
    if len(text) <= max_c:
        return text, False

    head = int(max_c * 0.55)
    tail = max_c - head - 150
    if tail < 400:
        tail = 400
        head = max_c - tail - 150
    sep = (
        "\n\n[... PyGenesis: parte central del system prompt omitida por límite de tamaño "
        f"({len(text)} caracteres → {max_c}). Ajusta PYGENESIS_CHAT_MAX_SYSTEM_CHARS, "
        "o usa PYGENESIS_RAG_ENABLED=false / PYGENESIS_CHAT_KNOWLEDGE=minimal ...]\n\n"
    )
    out = text[:head] + sep + text[-tail:]
    if len(out) > max_c:
        out = out[:max_c]

    # Si el recorte eliminó el contrato de creación de scripts, reinyectarlo al final (imprescindible para Unity).
    script_block = "\n\n--- PyGenesis (contrato obligatorio si generas un .cs completo) ---\n" + CHAT_SCRIPT_AUTOMATION.strip()
    if _PYGENESIS_SCRIPT_NEEDLE not in out:
        reserve = len(script_block) + 120
        max_main = max(0, max_c - reserve)
        if len(out) > max_main:
            out = out[:max_main].rstrip() + "\n\n[... truncado para reservar contrato PYGENESIS ...]\n"
        out = out + script_block
        logger.warning(
            "System prompt recortado: reinyectado contrato PYGENESIS al final (original=%d, límite=%d).",
            len(text),
            max_c,
        )
    else:
        logger.warning(
            "System prompt recortado: original=%d chars, límite=%d (cabecera+cola).",
            len(text),
            max_c,
        )
    return out, True


def _last_user_content(messages: List[ChatMessage]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return (m.content or "").strip()
    return ""


def _truncate_history(messages: List[ChatMessage], max_messages: int) -> List[ChatMessage]:
    """Mantiene roles user/assistant, omite contenido vacío, tope de mensajes y tope total de caracteres."""
    filtered = [
        m for m in messages if m.role in ("user", "assistant") and (m.content or "").strip()
    ]
    if len(filtered) > max_messages:
        filtered = filtered[-max_messages:]

    try:
        max_chars = int((os.getenv("PYGENESIS_CHAT_MAX_HISTORY_CHARS") or "12000").strip())
    except ValueError:
        max_chars = 12_000
    max_chars = min(max_chars, 200_000)

    def _total_chars(msgs: List[ChatMessage]) -> int:
        return sum(len(m.content or "") for m in msgs)

    dropped = 0
    while len(filtered) > 2 and _total_chars(filtered) > max_chars:
        filtered.pop(0)
        dropped += 1

    if dropped:
        logger.info(
            "Chat history recortado: %d mensaje(s) antiguo(s) omitido(s) (límite %d chars, quedan %d)",
            dropped,
            max_chars,
            len(filtered),
        )
    return filtered


def _history_for_llm(messages: List[ChatMessage], max_messages: int) -> List[ChatMessage]:
    """
    Historial enviado al LLM.
    ollama_native: solo el último user (≈ `ollama run`, un turno).
    """
    filtered = [
        m for m in messages if m.role in ("user", "assistant") and (m.content or "").strip()
    ]
    if chat_persona_mode() == "ollama_native":
        users = [m for m in filtered if m.role == "user"]
        if users:
            logger.info("Chat ollama_native: un solo turno (último user; historial omitido)")
            return [users[-1]]
        return filtered[-1:] if filtered else []
    return _truncate_history(messages, max_messages)


def _prepare_chat(settings: AppSettings, request: ChatRequest) -> Dict[str, Any]:
    """Construye los mensajes para el LLM y los metadatos comunes a /chat y /chat/stream."""
    llm = settings.llm
    history = _history_for_llm(request.messages, llm.chat_max_history_messages)
    if not any(m.role == "user" for m in history):
        raise ValueError("Se requiere al menos un mensaje con role=user en el historial.")

    last_user = _last_user_content(history)
    system_text = build_chat_system_prompt(
        scene_name=request.scene_name,
        last_user_message=last_user,
        scene_snapshot=request.scene_snapshot,
    )

    rag_text, rag_meta = retrieve_rag_context(last_user)
    if rag_text and chat_persona_mode() != "ollama_native":
        system_text = f"{system_text}\n\n{rag_text}"

    system_text, system_truncated = _truncate_system_prompt(system_text)

    api_messages: list[dict] = []
    if (system_text or "").strip():
        api_messages.append({"role": "system", "content": system_text})
    for m in history:
        api_messages.append({"role": m.role, "content": m.content})

    logger.info(
        "Chat prepare: persona=%s, system_chars=%d, history_msgs=%d",
        chat_persona_mode(),
        len(system_text or ""),
        len(history),
    )

    chat_temp = llm.chat_temperature if llm.chat_temperature is not None else llm.temperature
    max_out = llm.chat_max_tokens if llm.chat_max_tokens is not None else llm.max_tokens

    logger.debug("Chat repetition_guard=%s", repetition_guard_mode())
    passthrough = chat_passthrough_enabled(settings)
    if passthrough:
        logger.info("Chat passthrough: activo (sin post-procesado ni anti-bucle)")
    elif chat_persona_mode() == "ollama_native" and repetition_guard_mode() == "off":
        logger.info(
            "Chat stream anti-bucle: auto strong (ollama_native; PYGENESIS_CHAT_REPETITION_GUARD=off)"
        )

    return {
        "llm": llm,
        "history": history,
        "api_messages": api_messages,
        "system_text": system_text,
        "system_truncated": system_truncated,
        "rag_meta": rag_meta,
        "chat_temp": chat_temp,
        "max_out": max_out,
        "passthrough": passthrough,
    }


def _finalize_chat_text(raw: str, *, allow_repetition_cut: bool = True) -> Tuple[str, bool]:
    """Thinking strip + quita citas espurias + anti-bucle antes de parsear scripts."""
    return finalize_chat_visible_text(raw, allow_repetition_cut=allow_repetition_cut)


def _build_chat_metadata(
    prep: Dict[str, Any],
    request: ChatRequest,
    script_meta,
    *,
    repetition_truncated: bool = False,
    raw_chars: int | None = None,
) -> dict:
    meta_out: dict = {
        "model": prep["llm"].model,
        "history_messages_used": len(prep["history"]),
        "system_prompt_chars": len(prep["system_text"]),
        "system_prompt_truncated": prep["system_truncated"],
        "scene_snapshot_attached": request.scene_snapshot is not None,
        "create_script_in_response": script_meta is not None,
        "repetition_truncated": repetition_truncated,
        "passthrough": bool(prep.get("passthrough")),
    }
    if raw_chars is not None:
        meta_out["raw_chars"] = raw_chars
    meta_out.update(prep["rag_meta"])
    if script_meta:
        meta_out["create_script"] = script_meta
    return meta_out


def run_chat(settings: AppSettings, request: ChatRequest) -> ChatResponse:
    prep = _prepare_chat(settings, request)
    provider = build_provider(prep["llm"])

    content = provider.chat_completion(
        messages=prep["api_messages"],
        temperature=prep["chat_temp"],
        max_tokens=prep["max_out"],
    )

    if prep.get("passthrough"):
        visible, cited = strip_source_citations((content or "").strip())
        if cited:
            logger.info("Chat passthrough: citas [Fuente…] eliminadas (chars %d→%d)", len(content or ""), len(visible))
        logger.info("Chat completion passthrough OK (chars=%d)", len(visible))
        return ChatResponse(
            content=visible,
            metadata=_build_chat_metadata(
                prep, request, None, repetition_truncated=False, raw_chars=len(content or "")
            ),
        )

    finalized, repetition_truncated = _finalize_chat_text(content)
    visible, script_meta = extract_script_creation(finalized)

    logger.info("Chat completion OK (chars=%d)", len(visible or ""))
    if script_meta:
        logger.info("create_script en respuesta: %s", script_meta.get("asset_path"))
    elif _PYGENESIS_SCRIPT_NEEDLE in (content or ""):
        logger.warning(
            "Marcador PYGENESIS en texto del modelo pero extract_script_creation no produjo metadata; "
            "revisa fences ```csharp o JSON entre markers."
        )
    if repetition_truncated:
        logger.warning("Chat: respuesta recortada por detección de repetición (chars=%d)", len(visible or ""))

    return ChatResponse(
        content=(visible or "").strip(),
        metadata=_build_chat_metadata(prep, request, script_meta, repetition_truncated=repetition_truncated),
    )


def _stream_visible_upto(full: str, hidden: bool) -> Tuple[int, bool]:
    """
    Calcula hasta qué índice de `full` es seguro mostrar al usuario sin filtrar el bloque
    de creación de script. Devuelve (índice_seguro, hidden_actualizado).

    - Si aparece el marcador (---PYGENESIS…) dejamos de mostrar a partir de ahí.
    - Si no, retenemos una cola por si el marcador llega partido entre fragmentos.
    """
    if hidden:
        return -1, True
    idx = full.find(MARKER_START)
    if idx != -1:
        return idx, True
    safe = len(full) - _MARKER_GUARD_LEN
    return (safe if safe > 0 else 0), False


def run_chat_stream(settings: AppSettings, request: ChatRequest) -> Iterator[Dict[str, Any]]:
    """
    Variante en streaming de run_chat. Produce eventos dict:
      - {"type": "delta", "text": "..."}   fragmentos de texto visibles
      - {"type": "done", "content": "...", "metadata": {...}}   resultado final canónico
    Las excepciones se propagan; el endpoint las traduce a un evento de error.
    """
    prep = _prepare_chat(settings, request)
    provider = build_provider(prep["llm"])

    if not hasattr(provider, "chat_completion_stream"):
        # Proveedor sin streaming: emitir todo de una vez (degradación elegante).
        response = run_chat(settings, request)
        if response.content:
            yield {"type": "delta", "text": response.content}
        yield {"type": "done", "content": response.content, "metadata": response.metadata}
        return

    if prep.get("passthrough"):
        full = ""
        citation_filter = SourceCitationStreamFilter()
        for piece in provider.chat_completion_stream(
            messages=prep["api_messages"],
            temperature=prep["chat_temp"],
            max_tokens=prep["max_out"],
        ):
            full += piece
            visible_piece = citation_filter.feed(piece)
            if visible_piece:
                yield {"type": "delta", "text": visible_piece}
        visible = citation_filter.finalize()
        if visible:
            logger.info(
                "Chat stream passthrough OK (raw_chars=%d, visible_chars=%d)",
                len(full),
                len(visible),
            )
        else:
            logger.info("Chat stream passthrough OK (raw_chars=%d)", len(full))
        yield {
            "type": "done",
            "content": visible or None,
            "metadata": _build_chat_metadata(
                prep, request, None, repetition_truncated=False, raw_chars=len(full)
            ),
        }
        return

    full = ""
    emitted = 0
    hidden = False
    repetition_truncated_stream = False

    for piece in provider.chat_completion_stream(
        messages=prep["api_messages"],
        temperature=prep["chat_temp"],
        max_tokens=prep["max_out"],
    ):
        full += piece
        cut = should_cut_stream_for_repetition(full)
        if cut is not None:
            raw_len = len(full)
            reason = _strong_cut_reason(full, cut)
            full = repair_truncated_markdown_fences(full[:cut].strip(), repetition_cut=True)
            repetition_truncated_stream = True
            logger.warning(
                "Chat stream: bucle detectado en vivo (guard=%s, reason=%s); corte en char %d de %d",
                repetition_guard_mode(),
                reason,
                cut,
                raw_len,
            )
            safe_idx, hidden = _stream_visible_upto(full, hidden)
            if safe_idx > emitted:
                yield {"type": "delta", "text": full[emitted:safe_idx]}
                emitted = safe_idx
            break

        safe_idx, hidden = _stream_visible_upto(full, hidden)
        if safe_idx > emitted:
            yield {"type": "delta", "text": full[emitted:safe_idx]}
            emitted = safe_idx

    finalized, repetition_truncated = _finalize_chat_text(
        full, allow_repetition_cut=repetition_truncated_stream
    )
    repetition_truncated = repetition_truncated or repetition_truncated_stream
    visible, script_meta = extract_script_creation(finalized)

    logger.info(
        "Chat stream OK (raw_chars=%d, visible_chars=%d, repetition_truncated=%s)",
        len(full),
        len(visible or ""),
        repetition_truncated,
    )
    if repetition_truncated:
        logger.warning(
            "Chat stream: respuesta recortada por repetición (guard=%s, stream_cut=%s, raw_chars=%d, visible_chars=%d)",
            repetition_guard_mode(),
            repetition_truncated_stream,
            len(full),
            len(visible or ""),
        )
    if script_meta:
        logger.info("create_script en respuesta (stream): %s", script_meta.get("asset_path"))

    yield {
        "type": "done",
        "content": (visible or "").strip(),
        "metadata": _build_chat_metadata(prep, request, script_meta, repetition_truncated=repetition_truncated),
    }
