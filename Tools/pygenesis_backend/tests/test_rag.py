"""Tests RAG: lista blanca, troceado y recuperación con Chroma."""

import pytest

from reasoning.rag.allowlist import assert_allowed_url, is_allowed_url
from reasoning.rag.html_chunk import chunk_text, html_to_text
from reasoning.rag.retrieve import retrieve_rag_context


def test_allowlist_unity_and_learn():
    assert is_allowed_url("https://docs.unity3d.com/Manual/x.html") is True
    assert is_allowed_url("https://learn.microsoft.com/foo") is True
    assert is_allowed_url("https://docs.microsoft.com/foo") is True


def test_allowlist_rejects_unknown_host():
    assert is_allowed_url("https://evil.com/doc") is False
    assert is_allowed_url("not-a-url") is False


def test_assert_allowed_raises():
    with pytest.raises(ValueError):
        assert_allowed_url("https://example.com/")


def test_html_to_text_strips_script():
    html = "<html><head><title>T</title></head><body><script>x</script><p>Hello</p></body></html>"
    text, title = html_to_text(html)
    assert "Hello" in text
    assert title == "T"


def test_chunk_overlap():
    s = "a" * 2000
    parts = chunk_text(s, size=400, overlap=50)
    assert len(parts) >= 4
    assert all(len(p) <= 400 for p in parts)


def test_retrieve_disabled_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PYGENESIS_RAG_ENABLED", raising=False)
    text, meta = retrieve_rag_context("rigidbody physics unity")
    assert text == ""
    assert meta == {}


def test_retrieve_with_temp_index(tmp_path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("chromadb")
    monkeypatch.setenv("PYGENESIS_RAG_ENABLED", "true")
    monkeypatch.setenv("PYGENESIS_RAG_CHROMA_PATH", str(tmp_path / "chroma_db"))
    monkeypatch.setenv("PYGENESIS_RAG_TOP_K", "3")

    from reasoning.rag.chroma_store import get_or_create_collection

    coll = get_or_create_collection()
    coll.add(
        ids=["chunk1"],
        documents=[
            "The Rigidbody interface allows you to control the movement of a GameObject through physics simulation."
        ],
        metadatas=[
            {
                "source_url": "https://docs.unity3d.com/Manual/class-Rigidbody.html",
                "title": "Rigidbody",
                "chunk_index": 0,
            }
        ],
    )

    text, meta = retrieve_rag_context("how to use rigidbody for physics movement")
    assert "Rigidbody" in text or "physics" in text.lower()
    assert meta.get("rag_chunks", 0) >= 1
