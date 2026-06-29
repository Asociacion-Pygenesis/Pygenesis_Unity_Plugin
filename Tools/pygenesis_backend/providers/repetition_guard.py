"""Recorta respuestas del LLM que entran en bucle repitiendo el mismo texto."""

from __future__ import annotations

import os
import re
from typing import Optional

_SECTION_RESTART = re.compile(
    r"(?:^|\n)\s*1\.\s*(?:"
    r"diagn[oó]stico|Diagn[oó]stico|"
    r"ARQUITECTURA(?:\s+Y\s+CONCEPTO)?"
    r")",
    re.MULTILINE | re.IGNORECASE,
)
_SECTION_3 = re.compile(
    r"(?:^|\n)\s*3\.\s*CONSEJOS",
    re.MULTILINE | re.IGNORECASE,
)
_LEADING_SOURCE_CITATION = re.compile(r"^\s*\[Fuente[^\]]*\]\s*", re.IGNORECASE)
_SOURCE_CITATION_LINE = re.compile(r"(?:^|\n)\s*\[Fuente[^\]]*\]\s*", re.IGNORECASE | re.MULTILINE)
_SOURCE_CITATION_PAREN_LINE = re.compile(
    r"(?:^|\n)\s*\(Fuente:\s*[^)]+\)\s*",
    re.IGNORECASE | re.MULTILINE,
)
_SOURCE_CITATION_PAREN_INLINE = re.compile(r"\s*\(Fuente:\s*[^)]+\)", re.IGNORECASE)
_FINETUNE_META_TAIL = re.compile(
    r"(?:^|\n)\s*Termina cuando la pregunta de seguimiento[^\n]*(?:¡?\s*Felicidades!?\s*)?$",
    re.IGNORECASE | re.MULTILINE,
)
_FINETUNE_FELICIDADES = re.compile(r"(?:^|\n)\s*¡?\s*Felicidades!?\s*$", re.IGNORECASE)
_PYGENESIS_AUTOMATE = re.compile(r"PYGENESIS_AUTOMATE", re.IGNORECASE)
_META_NARRATION = re.compile(
    r"^(?:El usuario ha pedido[^\n.]*[.\s]*)+",
    re.IGNORECASE | re.MULTILINE,
)
_META_GENERATION = re.compile(
    r"(?:^|\n)\s*(?:Por lo tanto[,]?\s*)?"
    r"(?:se genera|generamos|generaré)\s+código\s+C#\s+compilable[^\n.]*[.\s]*",
    re.IGNORECASE | re.MULTILINE,
)


def _min_chars_for_repetition_check() -> int:
    try:
        return max(200, int((os.getenv("PYGENESIS_CHAT_REPETITION_MIN_CHARS") or "400").strip()))
    except ValueError:
        return 400


def repetition_guard_mode() -> str:
    """off (defecto) = sin recorte; strong = solo bucles largos; full = agresivo."""
    raw = (os.getenv("PYGENESIS_CHAT_REPETITION_GUARD") or "off").strip().lower()
    if raw in ("strong", "on", "1", "true", "yes"):
        return "strong"
    if raw in ("full", "aggressive", "all"):
        return "full"
    return "off"


def _repetition_guard_mode() -> str:
    return repetition_guard_mode()


def _stream_repetition_guard_mode() -> str:
    """
    Guardia en vivo (streaming). Con ollama_native y guard=off, activa strong automáticamente:
    ollama run corta solo; por API el modelo a veces buclea hasta num_predict.
    """
    explicit = repetition_guard_mode()
    if explicit != "off":
        return explicit
    try:
        from reasoning.chat_prompts import chat_persona_mode

        if chat_persona_mode() == "ollama_native":
            return "strong"
    except Exception:  # noqa: BLE001
        pass
    return "off"


def _min_chars_for_stream_strong_cut() -> int:
    try:
        from reasoning.chat_prompts import chat_persona_mode

        default = "600" if chat_persona_mode() == "ollama_native" else "1000"
    except Exception:  # noqa: BLE001
        default = "1000"
    try:
        return max(400, int((os.getenv("PYGENESIS_CHAT_REPETITION_STRONG_MIN_CHARS") or default).strip()))
    except ValueError:
        return 600 if default == "600" else 1000


def _second_match_cut(text: str, pattern: re.Pattern[str]) -> Optional[int]:
    matches = list(pattern.finditer(text))
    if len(matches) < 2:
        return None
    n = len(text)
    first, second = matches[0].start(), matches[1].start()
    # Evita cortar si el 2.º encabezado aparece demasiado pronto (respuesta aún incompleta).
    if n >= 600 and second < int(n * 0.55):
        return None
    return second


def _find_repeated_block_cut(text: str, *, min_block_len: int = 32) -> Optional[int]:
    blocks = text.split("\n\n")
    seen: set[str] = set()
    offset = 0
    for block in blocks:
        key = block.strip()
        if len(key) >= min_block_len:
            if key in seen:
                idx = text.find(block, max(0, offset - 1))
                if idx != -1:
                    return idx
            seen.add(key)
        offset += len(block) + 2
    return None


def _find_tail_repeat_cut(text: str, *, min_period: int = 40) -> Optional[int]:
    t = text.strip()
    n = len(t)
    if n < min_period * 2:
        return None
    upper = min(n // 2 + 1, 2000)
    for period in range(min_period, upper):
        chunk = t[-period:]
        first = t.find(chunk)
        if first != -1 and first <= n - period - 8 and (first == 0 or first >= n // 3):
            return first + period
    return None


def _min_gap_for_line_repeat(n: int) -> int:
    try:
        base = int((os.getenv("PYGENESIS_CHAT_REPETITION_LINE_GAP") or "0").strip())
    except ValueError:
        base = 0
    if base > 0:
        return base
    if n < 700:
        return 130
    if n < 1200:
        return 100
    return 80


def _find_repeated_line_cut(text: str, *, min_line_len: int = 36) -> Optional[int]:
    """Segunda aparición de la misma línea larga, con separación mínima (evita falsos positivos)."""
    seen: dict[str, int] = {}
    counts: dict[str, int] = {}
    start = 0
    n = len(text)
    min_gap = _min_gap_for_line_repeat(n)
    while start < n:
        end = text.find("\n", start)
        if end == -1:
            end = n
        key = text[start:end].strip()
        if len(key) >= min_line_len:
            counts[key] = counts.get(key, 0) + 1
            if key in seen:
                gap = start - seen[key]
                if gap >= min_gap or counts[key] >= 3:
                    return start
            else:
                seen[key] = start
        start = end + 1 if end < n else n
    return None


def _find_whole_segment_repeat_cut(text: str) -> Optional[int]:
    """Detecta cuando un segmento largo (~40% del texto) se repite entero a continuación."""
    t = text.strip()
    n = len(t)
    if n < 500:
        return None
    lo = int(n * 0.35)
    hi = int(n * 0.52)
    for size in range(lo, hi):
        seg = t[:size].strip()
        if len(seg) < 180:
            continue
        rest = t[size:].lstrip()
        if rest.startswith(seg):
            return size
    return None


def _find_repeated_substring_cut(text: str, *, min_len: int = 72) -> Optional[int]:
    """Segunda copia de un bloque multilínea (bucles dentro de ```csharp```)."""
    t = text
    n = len(t)
    if n < 520:
        return None
    min_gap = max(100, n // 5)
    max_size = min(360, n // 2)
    for size in range(max_size, min_len - 1, -6):
        scan_limit = min(n - size, 900)
        for i in range(0, scan_limit):
            chunk = t[i : i + size]
            if chunk.count("\n") < 1:
                continue
            second = t.find(chunk, i + size)
            if second != -1 and second - i >= min_gap:
                return second
    return None


def _min_chars_for_strong_cut() -> int:
    try:
        return max(800, int((os.getenv("PYGENESIS_CHAT_REPETITION_STRONG_MIN_CHARS") or "1000").strip()))
    except ValueError:
        return 1000


def _min_chars_for_code_loop_check() -> int:
    try:
        return max(800, int((os.getenv("PYGENESIS_CHAT_REPETITION_CODE_MIN_CHARS") or "1000").strip()))
    except ValueError:
        return 1000


def _strong_cut_reason(text: str, cut: int) -> str:
    """Etiqueta breve para logs (depuración)."""
    n = len(text)
    if cut is None:
        return "none"
    prefix = text[:cut]
    if _SECTION_3.search(prefix) and len(list(_SECTION_RESTART.finditer(text))) >= 2:
        return "section_1_restart_after_3"
    if _find_repeated_line_cut(text[: cut + 1], min_line_len=44) == cut:
        return "repeated_line"
    if _find_repeated_substring_cut(text[: cut + 20]) == cut:
        return "repeated_multiline"
    if _find_repeated_block_cut(text, min_block_len=96) == cut:
        return "repeated_paragraph"
    return "repetition"


def find_strong_repetition_cut_index(text: str) -> Optional[int]:
    """
    Solo bucles claros en respuestas largas (≥1000 chars por defecto).
    Sin recorte por subcadena multilínea (demasiados falsos positivos en respuestas cortas).
    """
    if not (text or "").strip():
        return None
    n = len(text)
    if n < _min_chars_for_strong_cut():
        return None

    min_cut = 120
    min_code = _min_chars_for_code_loop_check()

    if n >= min_code:
        cut = _find_repeated_line_cut(text, min_line_len=48)
        if cut is not None and cut >= min_cut:
            return cut

    cut = _second_match_cut(text, _SECTION_RESTART)
    if cut is not None and not _SECTION_3.search(text[:cut]):
        cut = None
    if cut is None:
        cut = _find_repeated_block_cut(text, min_block_len=120)
    if cut is not None and cut >= min_cut:
        return cut
    return None


def find_stream_repetition_cut_index(text: str) -> Optional[int]:
    """
    Anti-bucle en streaming (ollama_native): umbrales más bajos que strong en finalize.
    Incluye cola repetida y reinicio de sección 1 tras la 3.
    """
    if not (text or "").strip():
        return None
    n = len(text)
    min_len = _min_chars_for_stream_strong_cut()
    if n < min_len:
        return None

    min_cut = max(80, min_len // 5)

    cut = _find_repeated_line_cut(text, min_line_len=40)
    if cut is not None and cut >= min_cut:
        return cut

    cut = _second_match_cut(text, _SECTION_RESTART)
    if cut is not None and not _SECTION_3.search(text[:cut]):
        cut = None
    if cut is None:
        cut = _find_repeated_block_cut(text, min_block_len=72)
    if cut is None and n >= 700:
        cut = _find_repeated_substring_cut(text, min_len=56)
    if cut is None:
        cut = _find_tail_repeat_cut(text, min_period=28)
    if cut is not None and cut >= min_cut:
        return cut
    return None


def repair_truncated_markdown_fences(text: str, *, repetition_cut: bool = False) -> str:
    """Cierra ``` abiertos; tras recorte anti-bucle añade nota breve."""
    t = (text or "").rstrip()
    if _PYGENESIS_AUTOMATE.search(t):
        idx = _PYGENESIS_AUTOMATE.search(t).start()
        fence = t.rfind("```", 0, idx)
        t = t[:fence].rstrip() if fence != -1 else t[:idx].rstrip()
    if t.count("```") % 2 == 1:
        t = t + "\n```"
        if repetition_cut:
            t += "\n\n*[Código recortado: bucle detectado. Pide «continúa el script» si lo necesitas.]*"
    return t


def strip_finetune_artifacts(text: str) -> tuple[str, bool]:
    """Quita restos del dataset de fine-tune (PYGENESIS_AUTOMATE, Felicidades, metainstrucciones)."""
    t = (text or "").strip()
    if not t:
        return "", False
    changed = False

    m0 = _META_NARRATION.match(t)
    if m0:
        t = t[m0.end() :].lstrip()
        changed = True
    m0b = _META_GENERATION.search(t)
    if m0b:
        t = (t[: m0b.start()] + "\n" + t[m0b.end() :]).strip()
        t = re.sub(r"\n{3,}", "\n\n", t)
        changed = True

    while True:
        m = _FINETUNE_META_TAIL.search(t)
        if not m:
            break
        t = t[: m.start()].rstrip()
        changed = True

    m2 = _FINETUNE_FELICIDADES.search(t)
    if m2:
        t = t[: m2.start()].rstrip()
        changed = True

    if _PYGENESIS_AUTOMATE.search(t):
        idx = _PYGENESIS_AUTOMATE.search(t).start()
        fence = t.rfind("```", 0, idx)
        if fence != -1:
            t = t[:fence].rstrip()
        else:
            line = t.rfind("\n", 0, idx)
            t = (t[:line] if line != -1 else "").rstrip()
        changed = True

    t, quiz = _strip_trailing_quiz_artifact(t)
    changed = changed or quiz

    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t, changed


def find_repetition_cut_index(text: str, *, min_total_len: Optional[int] = None) -> Optional[int]:
    """
    Índice en `text` donde cortar si hay bucle; None si no hay señal fiable.
    min_total_len: por defecto PYGENESIS_CHAT_REPETITION_MIN_CHARS (400 en streaming).
    Usa min_total_len=120 al finalizar respuestas cortas.
    """
    if not (text or "").strip():
        return None
    min_len = _min_chars_for_repetition_check() if min_total_len is None else max(80, min_total_len)
    if len(text) < min_len:
        return None

    cuts: list[int] = []
    min_cut = max(50, min_len // 4)
    for fn in (
        lambda t: _second_match_cut(t, _SECTION_RESTART),
        _find_repeated_block_cut,
        _find_repeated_line_cut,
        _find_whole_segment_repeat_cut,
        _find_tail_repeat_cut,
    ):
        idx = fn(text)
        if idx is not None and idx >= min_cut:
            return idx
    return None


def truncate_at_repetition(text: str) -> tuple[str, bool]:
    cut = find_repetition_cut_index(text, min_total_len=120)
    if cut is None:
        return (text or "").strip(), False
    return text[:cut].strip(), True


def truncate_strong_repetition_only(text: str) -> tuple[str, bool]:
    cut = find_strong_repetition_cut_index(text)
    if cut is None:
        return text.strip(), False
    out = repair_truncated_markdown_fences(text[:cut].strip(), repetition_cut=True)
    return out, True


def truncate_repetitive_completion(text: str) -> tuple[str, bool]:
    """Aplica heurísticas anti-bucle. Devuelve (texto_recortado, hubo_recorte)."""
    return truncate_at_repetition(text)


def strip_source_citations(text: str) -> tuple[str, bool]:
    """Quita citas [Fuente…] o (Fuente: …) del fine-tune o del system prompt."""
    t = (text or "").strip()
    if not t:
        return "", False
    changed = False
    for pat in (_SOURCE_CITATION_LINE, _SOURCE_CITATION_PAREN_LINE):
        new_t, n = pat.subn("\n", t)
        if n:
            changed = True
            t = new_t
    new_t, n = _SOURCE_CITATION_PAREN_INLINE.subn("", t)
    if n:
        changed = True
        t = new_t
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t, changed


def _strip_trailing_quiz_artifact(text: str) -> tuple[str, bool]:
    """
    Quita bloques finales en negrita con varias preguntas (formato examen del dataset de fine-tune).
    Conserva una sola pregunta de seguimiento normal.
    """
    t = (text or "").rstrip()
    m = re.search(r"\n(\*\*(.+?)\*\*)\s*$", t, re.DOTALL)
    if not m:
        return t, False
    inner = m.group(2)
    if inner.count("?") >= 2:
        return t[: m.start()].rstrip(), True
    return t, False


def strip_leading_source_citations(text: str) -> tuple[str, bool]:
    """Alias: quita citas [Fuente…] (cualquier posición)."""
    return strip_source_citations(text)


_PARTIAL_BRACKET_FUENTE = re.compile(r"^\s*\[(?:F|Fu|Fue|Fuen|Fuent|Fuente)?$", re.IGNORECASE)
_PARTIAL_PAREN_FUENTE = re.compile(r"^\s*\((?:F|Fu|Fue|Fuen|Fuent|Fuente|:)?$", re.IGNORECASE)


def _strip_incomplete_leading_citation(text: str) -> str:
    """
    Durante streaming: oculta una cita inicial incompleta ([Fuente…] o (Fuente: …))
    hasta tener el cierre; si la primera línea completa es cita, la omite.
    """
    t = text or ""
    if not t.strip():
        return ""

    m = re.match(r"^\s*\[Fuente", t, re.IGNORECASE)
    if m:
        close = t.find("]", m.start())
        if close == -1:
            return ""
        line_end = t.find("\n", close)
        if line_end == -1:
            rest = t[close + 1 :]
            if rest.strip():
                return rest.lstrip("\n")
            return ""
        first_line = t[:line_end]
        rest = t[line_end + 1 :]
        if _LEADING_SOURCE_CITATION.match(first_line + "\n") or re.match(
            r"^\s*\[Fuente[^\]]*\]\s*$", first_line, re.IGNORECASE
        ):
            return rest.lstrip("\n")
        return t

    m = re.match(r"^\s*\(Fuente:", t, re.IGNORECASE)
    if m:
        close = t.find(")", m.start())
        if close == -1:
            return ""
        line_end = t.find("\n", close)
        if line_end == -1:
            rest = t[close + 1 :]
            if rest.strip():
                return rest.lstrip("\n")
            return ""
        first_line = t[:line_end]
        rest = t[line_end + 1 :]
        if re.match(r"^\s*\(Fuente:\s*[^)]+\)\s*$", first_line, re.IGNORECASE):
            return rest.lstrip("\n")
        return t

    if _PARTIAL_BRACKET_FUENTE.match(t) or _PARTIAL_PAREN_FUENTE.match(t):
        return ""

    cleaned, _ = strip_source_citations(t)
    return cleaned


class SourceCitationStreamFilter:
    """Emite deltas sin la cita [Fuente…] inicial del fine-tune."""

    def __init__(self) -> None:
        self._full = ""
        self._emitted = 0

    def feed(self, piece: str) -> str:
        if not piece:
            return ""
        self._full += piece
        visible = _strip_incomplete_leading_citation(self._full)
        if len(visible) < self._emitted:
            self._emitted = len(visible)
        if len(visible) <= self._emitted:
            return ""
        out = visible[self._emitted :]
        self._emitted = len(visible)
        return out

    def finalize(self) -> str:
        visible, _ = strip_source_citations(self._full)
        return visible


def finalize_chat_visible_text(raw: str, *, allow_repetition_cut: bool = True) -> tuple[str, bool]:
    """
    Thinking strip + prefijos de cita espuria + anti-bucle opcional (PYGENESIS_CHAT_REPETITION_GUARD).
    """
    from providers.qwen_thinking_strip import apply_redacted_thinking_strip

    cleaned = apply_redacted_thinking_strip((raw or "").strip())
    cleaned, _cited = strip_source_citations(cleaned)
    mode = _repetition_guard_mode()
    repeated = False
    if mode == "off":
        pass
    elif mode == "full" and allow_repetition_cut:
        cleaned, repeated = truncate_repetitive_completion(cleaned)
    elif mode == "full" and not allow_repetition_cut:
        cleaned, repeated = truncate_strong_repetition_only(cleaned)
    elif mode == "strong":
        cleaned, repeated = truncate_strong_repetition_only(cleaned)
    cleaned, _ = strip_finetune_artifacts(cleaned)
    return cleaned, repeated


def should_cut_stream_for_repetition(text: str) -> Optional[int]:
    """Corte en vivo durante streaming; None si guard desactivado o sin señal."""
    mode = _stream_repetition_guard_mode()
    if mode == "off":
        return None
    if mode == "full":
        return find_repetition_cut_index(text)
    try:
        from reasoning.chat_prompts import chat_persona_mode

        if chat_persona_mode() == "ollama_native":
            return find_stream_repetition_cut_index(text)
    except Exception:  # noqa: BLE001
        pass
    return find_strong_repetition_cut_index(text)
