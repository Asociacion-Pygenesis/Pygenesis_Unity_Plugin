"""Selección condicional de bloques de dominio (C#, animación, texturas) en el system prompt del chat."""

from reasoning.chat_prompts import _select_domain_blocks, build_chat_system_prompt

CSHARP_MARK = "Dominio: C# y scripting"
ANIM_MARK = "Dominio: Animator"
TEX_MARK = "Dominio: texturas"


def test_csharp_question_includes_only_csharp():
    blocks = _select_domain_blocks("¿Cómo uso un Rigidbody?")
    joined = "\n".join(blocks)
    assert CSHARP_MARK in joined
    assert ANIM_MARK not in joined
    assert TEX_MARK not in joined


def test_animation_question_includes_only_animation():
    blocks = _select_domain_blocks("¿Cómo configuro un Animator con transiciones?")
    joined = "\n".join(blocks)
    assert ANIM_MARK in joined
    assert TEX_MARK not in joined


def test_textures_question_includes_only_textures():
    blocks = _select_domain_blocks("¿Qué compresión de textura conviene para móvil?")
    joined = "\n".join(blocks)
    assert TEX_MARK in joined
    assert ANIM_MARK not in joined


def test_generic_question_includes_no_domain_blocks():
    assert _select_domain_blocks("Hola, ¿qué tal estás?") == []


def test_always_mode_includes_all(monkeypatch):
    monkeypatch.setenv("PYGENESIS_CHAT_DOMAIN_BLOCKS", "always")
    blocks = _select_domain_blocks("Hola")
    joined = "\n".join(blocks)
    assert CSHARP_MARK in joined and ANIM_MARK in joined and TEX_MARK in joined


def test_off_mode_includes_none(monkeypatch):
    monkeypatch.setenv("PYGENESIS_CHAT_DOMAIN_BLOCKS", "off")
    assert _select_domain_blocks("¿Cómo uso un Rigidbody?") == []


def test_build_chat_system_prompt_generic_is_lean(monkeypatch):
    """Pregunta genérica: sin escena, sin bloques de dominio y sin índice de conocimiento."""
    monkeypatch.setenv("PYGENESIS_CHAT_KNOWLEDGE", "minimal")
    s = build_chat_system_prompt(last_user_message="Hola, ¿quién eres?")
    assert CSHARP_MARK not in s
    assert ANIM_MARK not in s
    assert TEX_MARK not in s
    assert "Fuentes oficiales" not in s
    # La persona base y el contrato de scripts siempre están.
    assert "Pygenesis AI" in s


def test_build_chat_system_prompt_technical_includes_knowledge(monkeypatch):
    """Pregunta técnica: incluye dominio C# y el índice de conocimiento."""
    monkeypatch.setenv("PYGENESIS_CHAT_KNOWLEDGE", "minimal")
    s = build_chat_system_prompt(last_user_message="¿Cómo uso un Rigidbody?")
    assert CSHARP_MARK in s
    assert "Fuentes oficiales" in s
