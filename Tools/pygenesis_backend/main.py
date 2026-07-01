import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from starlette.responses import JSONResponse, StreamingResponse

from config.settings_loader import load_settings
from models import (
    AnalyzeSelectionRequest,
    AnalyzeSelectionResponse,
    ChatRequest,
    ChatResponse,
)
from reasoning.engine_factory import ENV_REASONING_MODE, create_engine
from reasoning.chat_prompts import get_capabilities_payload
from providers.llm_http_errors import LLMProviderHttpError
from services.analysis_service import AnalysisService
from services.chat_service import run_chat, run_chat_stream
from services.llm_warmup_retry import (
    apply_llm_warmup,
    llm_warmup_retry_loop,
    warmup_retry_enabled,
)
from providers.factory import build_provider
from providers.repetition_guard import repetition_guard_mode
from services.chat_passthrough import is_bridge_provider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pygenesis")


def _paths_exempt_from_llm_ready_gate(path: str) -> bool:
    if path == "/health" or path == "/chat/capabilities":
        return True
    if path in ("/docs", "/redoc", "/openapi.json"):
        return True
    if path.startswith("/docs") or path.startswith("/redoc"):
        return True
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.llm_warmup_preview = None
    app.state.llm_warmup_error = None
    app.state.llm_ready = False

    settings = load_settings()
    provider = build_provider(settings.llm)
    engine = create_engine(settings, provider)
    analysis_service = AnalysisService(engine)
    app.state.analysis_service = analysis_service

    mode = (
        os.environ.get(ENV_REASONING_MODE)
        or os.environ.get("PYGENESIS_REASONING")
        or settings.reasoning_mode
        or "rules"
    )
    logger.info(
        "PyGenesis backend iniciando (%s=%s); LLM url=%s model=%s timeout_s=%s max_tokens=%s chat_repetition_guard=%s",
        ENV_REASONING_MODE,
        mode,
        settings.llm.base_url,
        settings.llm.model,
        settings.llm.timeout_seconds,
        settings.llm.max_tokens,
        repetition_guard_mode(),
    )

    if os.getenv("PYGENESIS_LLM_SKIP_STARTUP_LOAD", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        app.state.llm_ready = True
        app.state.llm_warmup_preview = "(PYGENESIS_LLM_SKIP_STARTUP_LOAD)"
        logger.warning("Arranque LLM omitido (PYGENESIS_LLM_SKIP_STARTUP_LOAD); llm_ready=True.")
    else:
        logger.info("Cargando modelo LLM (bloquea hasta primera respuesta)…")
        if not await apply_llm_warmup(app):
            err = app.state.llm_warmup_error
            logger.error("El backend escucha HTTP pero el LLM no está listo: %s", err)
        else:
            logger.info("LLM listo; se aceptan /chat y /analyze-selection.")

    stop_retry = asyncio.Event()
    retry_task: asyncio.Task | None = None
    if (
        warmup_retry_enabled()
        and not app.state.llm_ready
        and os.getenv("PYGENESIS_LLM_SKIP_STARTUP_LOAD", "").strip().lower()
        not in ("1", "true", "yes", "on")
    ):
        retry_task = asyncio.create_task(llm_warmup_retry_loop(app, stop_retry))

    yield

    stop_retry.set()
    if retry_task is not None:
        retry_task.cancel()
        try:
            await retry_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="PyGenesis Backend", lifespan=lifespan)


@app.middleware("http")
async def llm_ready_gate(request: Request, call_next):
    if _paths_exempt_from_llm_ready_gate(request.url.path):
        return await call_next(request)
    if not getattr(request.app.state, "llm_ready", False):
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "El modelo LLM aún no está listo o falló la carga inicial. "
                    "Consulta GET /health (llm_ready, llm_warmup_error)."
                ),
            },
        )
    return await call_next(request)


@app.get("/health")
def health(request: Request):
    settings = load_settings()
    body: dict = {
        "status": "ok",
        "llm_ready": bool(getattr(request.app.state, "llm_ready", False)),
        "llm_provider": settings.llm.provider,
    }
    err = getattr(request.app.state, "llm_warmup_error", None)
    if err:
        body["llm_warmup_error"] = err
    preview = getattr(request.app.state, "llm_warmup_preview", None)
    if preview:
        body["llm_warmup"] = preview
    if is_bridge_provider(settings) and body["llm_ready"]:
        try:
            bridge = build_provider(settings.llm)
            health_fn = getattr(bridge, "health", None)
            if callable(health_fn):
                body["inference_bridge"] = health_fn()
        except Exception as ex:  # noqa: BLE001
            body["inference_bridge"] = {"status": "error", "detail": str(ex)}
    return body


@app.get("/chat/capabilities")
def chat_capabilities():
    """Texto de bienvenida y capacidades para la UI (sin llamar al LLM)."""
    return get_capabilities_payload()


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    """Conversación con Pygenesis AI (mensajes user/assistant + system del servidor)."""
    settings = load_settings()
    try:
        return run_chat(settings, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LLMProviderHttpError as e:
        logger.warning("POST /chat LLM HTTP %s: %s", e.status_code, e)
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    except Exception as e:
        logger.exception("POST /chat failed: %s", e)
        raise HTTPException(status_code=502, detail=f"LLM chat failed: {e}") from e


@app.post("/chat/stream")
def chat_stream(payload: ChatRequest):
    """
    Igual que /chat pero en streaming (NDJSON: una línea JSON por evento).

    Eventos:
      {"type":"delta","text":"..."}                 fragmentos de texto a medida que se generan
      {"type":"done","content":"...","metadata":{}} resultado final (passthrough: content=null, metadata.passthrough=true)
      {"type":"error","detail":"...","status":502}  si falla la generación
    """
    settings = load_settings()

    def _ndjson() -> "object":
        try:
            for event in run_chat_stream(settings, payload):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except ValueError as e:
            yield json.dumps({"type": "error", "detail": str(e), "status": 400}, ensure_ascii=False) + "\n"
        except LLMProviderHttpError as e:
            logger.warning("POST /chat/stream LLM HTTP %s: %s", e.status_code, e)
            yield json.dumps(
                {"type": "error", "detail": str(e), "status": e.status_code}, ensure_ascii=False
            ) + "\n"
        except Exception as e:  # noqa: BLE001
            logger.exception("POST /chat/stream failed: %s", e)
            yield json.dumps(
                {"type": "error", "detail": f"LLM chat failed: {e}", "status": 502}, ensure_ascii=False
            ) + "\n"

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(_ndjson(), media_type="application/x-ndjson", headers=headers)


@app.post("/analyze-selection", response_model=AnalyzeSelectionResponse)
def analyze_selection(payload: AnalyzeSelectionRequest, request: Request):
    logger.info("=== /analyze-selection called ===")
    logger.info("payload: %s", payload)

    try:
        service: AnalysisService = request.app.state.analysis_service
        return service.analyze_selection(payload)
    except LLMProviderHttpError as e:
        logger.warning("/analyze-selection LLM HTTP %s: %s", e.status_code, e)
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    except Exception as e:
        logger.exception("ERROR in /analyze-selection: %s", repr(e))
        raise
