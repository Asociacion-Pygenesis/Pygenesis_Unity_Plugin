"""
Proxy HTTP delante de llama-server: reenvía Web UI y API, y filtra citas [Fuente…]
en POST /v1/chat/completions (misma higiene que el plugin vía backend).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import AsyncIterator
from typing import Optional

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route

sys.path.insert(0, str((__import__("pathlib").Path(__file__).resolve().parent / ".." / "pygenesis_backend")))

from providers.repetition_guard import (  # noqa: E402
    SourceCitationStreamFilter,
    strip_source_citations,
)

logger = logging.getLogger("pygenesis.citation_proxy")

_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length",
    }
)


def _forward_headers(request: Request) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in request.headers.items():
        lk = key.lower()
        if lk in _HOP_BY_HOP:
            continue
        out[key] = value
    return out


def _response_headers(headers: httpx.Headers) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}


def _is_chat_completions(path: str) -> bool:
    return path.rstrip("/").endswith("/v1/chat/completions")


def _strip_choice_message(payload: dict) -> dict:
    choices = payload.get("choices") or []
    if not choices:
        return payload
    choice = choices[0]
    msg = choice.get("message")
    if isinstance(msg, dict) and isinstance(msg.get("content"), str):
        cleaned, _ = strip_source_citations(msg["content"])
        msg["content"] = cleaned
    text = choice.get("text")
    if isinstance(text, str):
        cleaned, _ = strip_source_citations(text)
        choice["text"] = cleaned
    return payload


def _transform_sse_data(data: str, filt: SourceCitationStreamFilter) -> Optional[str]:
    if not data or data == "[DONE]":
        return data
    try:
        obj = json.loads(data)
    except json.JSONDecodeError:
        return data
    choices = obj.get("choices") or []
    if not choices:
        return data
    choice = choices[0]
    delta = choice.get("delta")
    if isinstance(delta, dict) and isinstance(delta.get("content"), str):
        piece = delta["content"]
        if piece:
            visible = filt.feed(piece)
            delta["content"] = visible if visible else ""
            choice["delta"] = delta
            obj["choices"] = [choice]
    msg = choice.get("message")
    if isinstance(msg, dict) and isinstance(msg.get("content"), str):
        cleaned, _ = strip_source_citations(msg["content"])
        msg["content"] = cleaned
        choice["message"] = msg
        obj["choices"] = [choice]
    return json.dumps(obj, ensure_ascii=False)


async def _stream_chat_sse(
    upstream_url: str,
    headers: dict[str, str],
    body: bytes,
    timeout: httpx.Timeout,
) -> AsyncIterator[bytes]:
    """Filtra SSE; el cliente httpx permanece abierto hasta cerrar el stream."""
    filt = SourceCitationStreamFilter()
    pending = ""
    client = httpx.AsyncClient(timeout=timeout)
    try:
        req = client.build_request("POST", upstream_url, headers=headers, content=body)
        resp = await client.send(req, stream=True)
        resp.raise_for_status()
    except Exception:
        await client.aclose()
        raise

    try:
        async for chunk in resp.aiter_bytes():
            pending += chunk.decode("utf-8", errors="replace")
            while "\n" in pending:
                line, pending = pending.split("\n", 1)
                line = line.rstrip("\r")
                if not line:
                    yield b"\n"
                    continue
                if line.startswith("data:"):
                    raw = line[5:].strip()
                    out = _transform_sse_data(raw, filt)
                    if out is None:
                        continue
                    yield f"data: {out}\n\n".encode("utf-8")
                else:
                    yield (line + "\n").encode("utf-8")
        if pending.strip():
            yield pending.encode("utf-8")
    finally:
        await resp.aclose()
        await client.aclose()


async def _forward_upstream(
    method: str,
    target: str,
    headers: dict[str, str],
    body: bytes,
    timeout: httpx.Timeout,
) -> Response:
    """Reenvía peticiones no-chat (Web UI, /v1/models, estáticos…)."""
    client = httpx.AsyncClient(timeout=timeout)
    try:
        req = client.build_request(method, target, headers=headers, content=body)
        resp = await client.send(req, stream=True)
    except Exception:
        await client.aclose()
        raise

    status = resp.status_code
    out_headers = _response_headers(resp.headers)
    media_type = resp.headers.get("content-type")
    content_length = resp.headers.get("content-length")
    try:
        cl = int(content_length) if content_length else None
    except ValueError:
        cl = None

    # JSON y respuestas pequeñas: buffer completo (evita problemas de streaming).
    if method in ("GET", "HEAD", "OPTIONS") and cl is not None and cl <= 32 * 1024 * 1024:
        try:
            content = await resp.aread()
        finally:
            await resp.aclose()
            await client.aclose()
        return Response(content=content, status_code=status, headers=out_headers, media_type=media_type)

    async def stream_body() -> AsyncIterator[bytes]:
        try:
            async for chunk in resp.aiter_raw():
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return StreamingResponse(stream_body(), status_code=status, headers=out_headers, media_type=media_type)


def create_app(upstream: str) -> Starlette:
    upstream_base = upstream.rstrip("/")
    timeout = httpx.Timeout(connect=30.0, read=None, write=60.0, pool=30.0)

    async def proxy(request: Request) -> Response:
        path = request.url.path or "/"
        query = request.url.query
        target = f"{upstream_base}{path}"
        if query:
            target = f"{target}?{query}"
        headers = _forward_headers(request)
        body = await request.body()

        if request.method == "POST" and _is_chat_completions(path):
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = {}
            if payload.get("stream"):
                return StreamingResponse(
                    _stream_chat_sse(target, headers, body, timeout),
                    media_type="text/event-stream",
                )
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(target, headers=headers, content=body)
            try:
                data = resp.json()
                data = _strip_choice_message(data)
                return Response(
                    content=json.dumps(data, ensure_ascii=False),
                    status_code=resp.status_code,
                    media_type=resp.headers.get("content-type", "application/json"),
                )
            except json.JSONDecodeError:
                return Response(
                    content=resp.content,
                    status_code=resp.status_code,
                    media_type=resp.headers.get("content-type"),
                )

        return await _forward_upstream(request.method, target, headers, body, timeout)

    methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
    return Starlette(routes=[Route("/{path:path}", proxy, methods=methods)])


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Proxy PyGenesis con filtro de citas [Fuente…]")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True, help="Puerto público (Web UI + API)")
    parser.add_argument("--upstream", required=True, help="URL base de llama-server interno")
    args = parser.parse_args()

    import uvicorn

    logger.info("Citation proxy http://%s:%s → %s", args.host, args.port, args.upstream.rstrip("/"))
    uvicorn.run(create_app(args.upstream), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
