"""Lista blanca de hosts para fetch e indexación RAG."""

from __future__ import annotations

from urllib.parse import urlparse

# Solo estos hosts exactos pueden indexarse (HTTPS recomendado en seeds).
_ALLOWED_HOSTS = frozenset(
    {
        "docs.unity3d.com",
        "learn.microsoft.com",
        "docs.microsoft.com",
    }
)


def is_allowed_url(url: str) -> bool:
    if not url or not url.strip().startswith(("http://", "https://")):
        return False
    try:
        host = urlparse(url.strip()).netloc.lower()
    except ValueError:
        return False
    if not host:
        return False
    return host in _ALLOWED_HOSTS


def assert_allowed_url(url: str) -> None:
    if not is_allowed_url(url):
        raise ValueError(f"URL no permitida por la lista blanca RAG: {url!r}")
