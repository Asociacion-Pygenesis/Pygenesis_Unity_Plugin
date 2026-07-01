"""Recorte anti-bucle en respuestas del chat."""

from providers.repetition_guard import truncate_repetitive_completion


def test_truncate_on_section_restart():
    text = (
        "1. Diagnóstico: falta Rigidbody.\n\n"
        "2. Solución: añade el componente.\n\n"
        "¿Quieres que te pase el script?\n\n"
        "1. Diagnóstico: falta Rigidbody otra vez.\n\n"
        "2. Solución repetida…"
    )
    out, changed = truncate_repetitive_completion(text)
    assert changed is True
    assert "otra vez" not in out
    assert out.endswith("¿Quieres que te pase el script?")


def test_truncate_on_repeated_paragraph():
    block = "Para usar Rigidbody en Unity, añade el componente al GameObject y usa FixedUpdate."
    text = f"{block}\n\nMás detalle breve.\n\n{block}\n\nY otra vez lo mismo."
    out, changed = truncate_repetitive_completion(text)
    assert changed is True
    assert out.count(block) == 1


def test_truncate_on_tail_repeat():
    head = "A" * 80 + " Respuesta útil sobre colliders."
    text = head + " " + head
    out, changed = truncate_repetitive_completion(text)
    assert changed is True
    assert len(out) < len(text)


def test_truncate_on_section_restart_arquitectura():
    text = (
        "1. ARQUITECTURA Y CONCEPTO: el Rigidbody…\n\n"
        "2. CÓDIGO LIMPIO: ```csharp …```\n\n"
        "3. CONSEJOS DE RENDIMIENTO: evita GetComponent en Update.\n\n"
        "¿Quieres ver un ejemplo con Input System?\n\n"
        "1. ARQUITECTURA Y CONCEPTO: otra vez…"
    )
    out, changed = truncate_repetitive_completion(text)
    assert changed is True
    assert "otra vez" not in out


def test_no_change_on_normal_answer():
    text = "Usa Rigidbody con AddForce en FixedUpdate.\n\n¿Quieres un ejemplo con Input System?"
    out, changed = truncate_repetitive_completion(text)
    assert changed is False
    assert out == text


def test_strip_source_citation_mid_text():
    from providers.repetition_guard import strip_source_citations

    text = (
        "1. ARQUITECTURA: intro.\n\n"
        "[Fuente manual Unity — Rigidbody]\n\n"
        "2. CÓDIGO: ejemplo."
    )
    out, changed = strip_source_citations(text)
    assert changed is True
    assert "[Fuente" not in out
    assert "2. CÓDIGO" in out


def test_strip_paren_source_citation():
    from providers.repetition_guard import strip_source_citations

    text = (
        "3. CONSEJOS: usa SerializeReference con cuidado.\n\n"
        "¿Quieres un ejemplo con ScriptableObject?\n\n"
        "(Fuente: Manual_ScriptableObjectGuide.html.txt)"
    )
    out, changed = strip_source_citations(text)
    assert changed is True
    assert "Fuente" not in out
    assert "SerializeReference" in out


def test_strip_trailing_quiz_and_fuente(monkeypatch):
    from providers.repetition_guard import finalize_chat_visible_text

    monkeypatch.setenv("PYGENESIS_CHAT_REPETITION_GUARD", "off")
    text = (
        "1. ARQUITECTURA: serialización.\n\n"
        "2. CÓDIGO: ejemplo.\n\n"
        "3. CONSEJOS: evita ciclos.\n\n"
        "¿Quieres ver el ScriptableObject completo?\n\n"
        "**¿Qué problema tiene el código anterior y cómo lo solucionas? "
        "¿Cómo se usa `SerializeReference` en este contexto?**\n\n"
        "(Fuente: Manual_ScriptableObjectGuide.html.txt)"
    )
    out, _ = finalize_chat_visible_text(text)
    assert "Fuente" not in out
    assert "código anterior" not in out
    assert "ScriptableObject completo" in out


def test_ui_gc_menu_loop_segment_repeat():
    """Bucle típico tras mucho contexto: repite un bloque largo de la misma respuesta."""
    intro = (
        "1. ARQUITECTURA Y CONCEPTO: Los botones UI dinámicos con Instantiate generan GC "
        "por asignaciones de delegates y strings en cada refresco del menú.\n\n"
        "2. CÓDIGO LIMPIO: usa object pooling y evita closures en listeners.\n\n"
        "3. CONSEJOS: cachea referencias y evita LINQ en hot paths.\n\n"
        "¿Quieres un ejemplo con pool de botones?\n\n"
    )
    repeat = (
        "1. ARQUITECTURA Y CONCEPTO: Los botones UI dinámicos con Instantiate generan GC "
        "por asignaciones de delegates y strings en cada refresco del menú.\n\n"
        "2. CÓDIGO LIMPIO: usa object pooling"
    )
    text = intro + repeat
    out, changed = truncate_repetitive_completion(text)
    assert changed is True
    assert out.count("1. ARQUITECTURA Y CONCEPTO") == 1
    assert "¿Quieres un ejemplo" in out


def test_find_repetition_cut_index_none_on_short_text():
    from providers.repetition_guard import find_repetition_cut_index

    assert find_repetition_cut_index("Respuesta corta sin bucle.") is None


def test_strip_meta_narration():
    from providers.repetition_guard import strip_finetune_artifacts

    raw = (
        "El usuario ha pedido una implementacion completa, por lo tanto se genera código C# "
        "compilable bajo la convención PyGenesis para automatización dentro del Editor Unity.\n\n"
        "1. ARQUITECTURA: guardado JSON."
    )
    out, changed = strip_finetune_artifacts(raw)
    assert changed is True
    assert out.startswith("1. ARQUITECTURA")
    assert "El usuario ha pedido" not in out


def test_strong_no_cut_under_1000_chars(monkeypatch):
    from providers.repetition_guard import find_strong_repetition_cut_index

    monkeypatch.setenv("PYGENESIS_CHAT_REPETITION_GUARD", "strong")
    text = "x" * 200 + "\n" + "y" * 200 + "\n" + "x" * 150
    assert len(text) < 1000
    assert find_strong_repetition_cut_index(text) is None
    from providers.repetition_guard import find_strong_repetition_cut_index

    monkeypatch.setenv("PYGENESIS_CHAT_REPETITION_GUARD", "strong")
    # Dos líneas iguales cercanas (~80 chars de separación) en respuesta corta: no cortar.
    line = "        public float health, mana; // valor inicial del jugador"
    text = (
        "1. ARQUITECTURA Y CONCEPTO: PlayerPrefs no basta para saves complejos.\n\n"
        "2. CÓDIGO LIMPIO:\n```csharp\nusing UnityEngine;\n"
        f"public class Save {{ {line}\n  void Save() {{}}\n  {line}\n}}\n```\n\n"
        "3. CONSEJOS: evita JSON en cada frame.\n\n"
        "¿Quieres ver cifrado con AES?"
    )
    assert len(text) < 520
    assert find_strong_repetition_cut_index(text) is None


def test_player_save_csharp_loop_cut(monkeypatch):
    """Bucle real: repite campos y struct SaveState dentro de ```csharp```."""
    from providers.repetition_guard import truncate_strong_repetition_only

    monkeypatch.setenv("PYGENESIS_CHAT_REPETITION_GUARD", "strong")
    loop_line = '    [SerializeField] private string _saveFilename = "player_save.json";'
    chunk = (
        f"{loop_line}\n"
        "private Dictionary<string,string> saveData;\n\n"
        "void Start() { Load(); }\n\n"
        "// Guardar el estado del jugador en JSON a un archivo.\n"
        "[Serializable]\n"
        "struct SaveState {\n"
        "        public float health, mana;\n"
        "public Vector3 position; // Posición actual\n"
    )
    intro = (
        "Para guardar datos persistentes, `PlayerPrefs` es insuficiente.\n\n"
        "```csharp\n"
        "using UnityEngine;\n"
        "public class PlayerSaveSystem : MonoBehaviour {\n"
    )
    text = intro + chunk + chunk + chunk
    out, changed = truncate_strong_repetition_only(text)
    assert changed is True
    assert out.count(loop_line) == 1
    assert "bucle detectado" in out
    assert "struct SaveState" in out


def test_repair_open_code_fence():
    from providers.repetition_guard import repair_truncated_markdown_fences

    t = "texto\n```csharp\nclass A {}"
    assert repair_truncated_markdown_fences(t).endswith("```")

    stub = "Intro\n```csharp\nusing UnityEngine;\n#if PYGENESIS_AUTOMATE\nclass X {}\n"
    repaired = repair_truncated_markdown_fences(stub, repetition_cut=True)
    assert "PYGENESIS_AUTOMATE" not in repaired


def test_strip_finetune_artifacts():
    from providers.repetition_guard import strip_finetune_artifacts

    raw = (
        "1. ARQUITECTURA: guardado en JSON.\n\n"
        "```csharp\nusing UnityEngine;\n#if UNITY_EDITOR || PYGENESIS_AUTOMATE\n"
        "public class PlayerSave { public int healthPoints; }\n#endif\n```\n\n"
        "Termina cuando la pregunta de seguimiento final esté resuelta. ¡Felicidades!"
    )
    out, changed = strip_finetune_artifacts(raw)
    assert changed is True
    assert "PYGENESIS_AUTOMATE" not in out
    assert "Felicidades" not in out
    assert "ARQUITECTURA" in out


def test_strong_guard_no_cut_before_section_3(monkeypatch):
    from providers.repetition_guard import find_strong_repetition_cut_index

    monkeypatch.setenv("PYGENESIS_CHAT_REPETITION_GUARD", "strong")
    text = (
        "1. ARQUITECTURA Y CONCEPTO: pooling de botones.\n\n"
        "2. CÓDIGO LIMPIO: ver ejemplo.\n\n"
        "1. ARQUITECTURA Y CONCEPTO: reinicio prematuro del modelo.\n\n"
        "más texto…"
    )
    assert find_strong_repetition_cut_index(text) is None


def test_stream_guard_auto_strong_when_ollama_native_and_guard_off(monkeypatch):
    from providers.repetition_guard import _stream_repetition_guard_mode, should_cut_stream_for_repetition

    monkeypatch.setenv("PYGENESIS_CHAT_PERSONA", "ollama_native")
    monkeypatch.setenv("PYGENESIS_CHAT_REPETITION_GUARD", "off")
    assert _stream_repetition_guard_mode() == "strong"

    loop = (
        "1. ARQUITECTURA Y CONCEPTO\n" + ("x" * 200) + "\n"
        "2. CÓDIGO\n```csharp\nclass A {}\n```\n"
        "3. CONSEJOS DE RENDIMIENTO PRINCIPAL\n" + ("y" * 200) + "\n"
        "1. ARQUITECTURA Y CONCEPTO\n" + ("z" * 200)
    )
    assert should_cut_stream_for_repetition(loop) is not None


def test_stream_repetition_tail_loop(monkeypatch):
    from providers.repetition_guard import find_stream_repetition_cut_index

    monkeypatch.setenv("PYGENESIS_CHAT_PERSONA", "ollama_native")
    chunk = "Esta línea se repite sin parar en el bucle. " * 8
    text = ("Intro larga. " * 40) + chunk + chunk
    cut = find_stream_repetition_cut_index(text)
    assert cut is not None
    assert cut < len(text) - 50


def test_strong_guard_cuts_after_section_3_loop(monkeypatch):
    from providers.repetition_guard import find_strong_repetition_cut_index

    monkeypatch.setenv("PYGENESIS_CHAT_REPETITION_GUARD", "strong")
    pad = "Detalle adicional sobre pooling y GC en UI dinámica. " * 18
    text = (
        "1. ARQUITECTURA Y CONCEPTO: pooling.\n\n"
        f"{pad}\n\n"
        "2. CÓDIGO LIMPIO: ```csharp class X {} ```\n\n"
        "3. CONSEJOS: evita GC.\n\n"
        "¿Quieres el pool completo?\n\n"
        "1. ARQUITECTURA Y CONCEPTO: otra vez…"
    )
    assert len(text) >= 1000
    cut = find_strong_repetition_cut_index(text)
    assert cut is not None
    assert "otra vez" not in text[:cut]


def test_finalize_citation_strip_does_not_flag_repetition(monkeypatch):
    from providers.repetition_guard import finalize_chat_visible_text

    monkeypatch.setenv("PYGENESIS_CHAT_REPETITION_GUARD", "off")
    text = "[Fuente manual Unity — Rigidbody]\n\n1. ARQUITECTURA: el Rigidbody…"
    out, repeated = finalize_chat_visible_text(text)
    assert repeated is False
    assert out.startswith("1. ARQUITECTURA")


def test_source_citation_stream_filter_leading():
    from providers.repetition_guard import SourceCitationStreamFilter

    filt = SourceCitationStreamFilter()
    assert filt.feed("[Fuente manual Unity — Rigidbody]\n\n") == ""
    assert filt.feed("1. ARQUITECTURA") == "1. ARQUITECTURA"
    assert "[Fuente" not in filt.finalize()
    assert filt.finalize().startswith("1. ARQUITECTURA")


def test_source_citation_stream_filter_holds_partial_bracket():
    from providers.repetition_guard import SourceCitationStreamFilter

    filt = SourceCitationStreamFilter()
    assert filt.feed("[") == ""
    assert filt.feed("Fuente manual") == ""
    assert filt.feed(" — X]\n\nHola") == "Hola"


def test_finalize_guard_off_keeps_structured_answer(monkeypatch):
    from providers.repetition_guard import finalize_chat_visible_text

    monkeypatch.setenv("PYGENESIS_CHAT_REPETITION_GUARD", "off")
    text = (
        "1. ARQUITECTURA Y CONCEPTO: pooling de botones.\n\n"
        "2. CÓDIGO LIMPIO: ver ejemplo.\n\n"
        "1. ARQUITECTURA Y CONCEPTO: reinicio prematuro del modelo.\n\n"
        "más texto…"
    )
    out, changed = finalize_chat_visible_text(text, allow_repetition_cut=False)
    assert changed is False
    assert len(out) == len(text.strip())


def test_finalize_stream_done_keeps_long_valid_answer(monkeypatch):
    """Con guard=off no recortar por líneas repetidas en código C#."""
    from providers.repetition_guard import finalize_chat_visible_text

    monkeypatch.setenv("PYGENESIS_CHAT_REPETITION_GUARD", "off")
    code_line = "            slot.Button.onClick.AddListener(() => OnSlotClicked(index));"
    text = (
        "1. ARQUITECTURA Y CONCEPTO: usa pooling de botones UI.\n\n"
        "2. CÓDIGO LIMPIO:\n```csharp\n"
        f"{code_line}\n"
        f"{code_line}\n"
        "        }\n"
        "```\n\n"
        "3. CONSEJOS: evita closures que capturen el índice del bucle.\n\n"
        "¿Quieres ver el pool completo?"
    )
    out, changed = finalize_chat_visible_text(text, allow_repetition_cut=False)
    assert changed is False
    assert "¿Quieres ver el pool completo?" in out
    assert len(out) >= len(text) - 20
