"""Carga model_config.yaml — fuente única para system, sampling y servidor."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

TOOLS_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INFERENCE_ROOT = TOOLS_ROOT / "pygenesis_inference"
DEFAULT_CONFIG_PATH = DEFAULT_INFERENCE_ROOT / "model_config.yaml"

CHATML_IM_START = "<|" + "im" + "_" + "start" + "|>"
CHATML_IM_END = "<|" + "im" + "_" + "end" + "|>"


def user_inference_data_root() -> Path:
    """Runtime instalado en portátil: %USERPROFILE%/.pygenesis/pygenesis_inference."""
    return Path.home() / ".pygenesis" / "pygenesis_inference"


def _resolve_inference_asset(inference_root: Path, relative: Path) -> Path:
    """Ruta relativa al YAML; si no existe, prueba ~/.pygenesis (modelo/bin movidos fuera del repo)."""
    if relative.is_absolute():
        return relative.resolve()
    primary = (inference_root / relative).resolve()
    if primary.exists():
        return primary
    fallback = (user_inference_data_root() / relative).resolve()
    if fallback.exists():
        return fallback
    return primary


def _resolve_gguf_path(inference_root: Path, gguf: Path) -> Path:
    resolved = _resolve_inference_asset(inference_root, gguf)
    if resolved.exists():
        return resolved
    models_dir = user_inference_data_root() / "models"
    if not models_dir.is_dir():
        models_dir = inference_root / "models"
    if models_dir.is_dir():
        ggufs = sorted(models_dir.glob("*.gguf"))
        if len(ggufs) == 1:
            return ggufs[0].resolve()
        for candidate in ggufs:
            if "pygenesis" in candidate.name.lower():
                return candidate.resolve()
        if ggufs:
            return ggufs[0].resolve()
    return resolved


def bridge_inject_system_prompt() -> bool:
    """
    Si false: solo mensaje user (sin system; distinto del chat web con ui_config).
    Si true (defecto): inyecta system_prompt de model_config.yaml — paridad con la Web UI.
    """
    raw = (os.getenv("PYGENESIS_BRIDGE_INJECT_SYSTEM") or "on").strip().lower()
    return raw not in ("off", "0", "false", "no")


def bridge_minimal_api_body() -> bool:
    """Si true (defecto): no enviar stop/sampling por API; usa parámetros del servidor."""
    raw = (os.getenv("PYGENESIS_BRIDGE_MINIMAL_API") or "on").strip().lower()
    return raw not in ("off", "0", "false", "no")


@dataclass(frozen=True)
class ChatTemplateConfig:
    template: str = "chatml"
    im_start: str = CHATML_IM_START
    im_end: str = CHATML_IM_END


@dataclass(frozen=True)
class SamplingConfig:
    temperature: float = 0.55
    top_p: float = 0.92
    top_k: int = 40
    repeat_penalty: float = 1.38
    presence_penalty: float = 0.55
    num_ctx: int = 8192
    num_predict: int = 2048


@dataclass(frozen=True)
class ModelConfig:
    id: str = "pygenesis-unity"
    gguf: Path = field(default_factory=lambda: Path("models/pygenesis-unity-q4km.gguf"))


@dataclass(frozen=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8081
    llama_server: Path = field(default_factory=lambda: Path("llama-server.exe"))


@dataclass(frozen=True)
class UiConfig:
    title: str = "Pygenesis Unity"
    subtitle: str = "Haz una pregunta"


@dataclass(frozen=True)
class BridgeConfig:
    inference_root: Path
    model: ModelConfig
    server: ServerConfig
    chat: ChatTemplateConfig
    system_prompt: str
    sampling: SamplingConfig
    stop: tuple[str, ...]
    llama_server_args: dict[str, Any]
    ui: UiConfig

    @property
    def model_id(self) -> str:
        return self.model.id

    @property
    def base_url(self) -> str:
        return f"http://{self.server.host}:{self.server.port}/v1"

    def resolve_gguf_path(self) -> Path:
        return _resolve_gguf_path(self.inference_root, self.model.gguf)

    def resolve_llama_server_path(self) -> Path:
        return _resolve_inference_asset(self.inference_root, self.server.llama_server)

    def build_messages(
        self,
        user_message: str,
        *,
        system_override: Optional[str] = None,
    ) -> list[dict[str, str]]:
        """
        Un turno hacia llama-server.
        Por defecto solo user (≈ chat web del navegador).
        Con PYGENESIS_BRIDGE_INJECT_SYSTEM=on añade system_prompt del YAML.
        """
        messages: list[dict[str, str]] = []
        system = ""
        if system_override is not None:
            system = system_override.strip()
        elif bridge_inject_system_prompt():
            system = self.system_prompt.strip()
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": (user_message or "").strip()})
        return messages


def _config_path_from_env() -> Path:
    raw = os.getenv("PYGENESIS_BRIDGE_CONFIG")
    if raw and raw.strip():
        return Path(raw.strip()).expanduser().resolve()
    user_cfg = user_inference_data_root() / "model_config.yaml"
    if user_cfg.is_file():
        return user_cfg.resolve()
    return DEFAULT_CONFIG_PATH


def load_bridge_config(path: Optional[Path] = None) -> BridgeConfig:
    cfg_path = (path or _config_path_from_env()).resolve()
    inference_root = cfg_path.parent
    with cfg_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    model_raw = data.get("model") or {}
    server_raw = data.get("server") or {}
    chat_raw = data.get("chat") or {}
    sampling_raw = data.get("sampling") or {}
    stop_raw = data.get("stop") or []

    model = ModelConfig(
        id=str(model_raw.get("id") or "pygenesis-unity"),
        gguf=Path(str(model_raw.get("gguf") or "models/pygenesis-unity-q4km.gguf")),
    )
    server = ServerConfig(
        host=str(server_raw.get("host") or "127.0.0.1"),
        port=int(server_raw.get("port") or 8081),
        llama_server=Path(str(server_raw.get("llama_server") or "llama-server.exe")),
    )
    chat = ChatTemplateConfig(
        template=str(chat_raw.get("template") or "chatml"),
        im_start=str(chat_raw.get("im_start") or CHATML_IM_START),
        im_end=str(chat_raw.get("im_end") or CHATML_IM_END),
    )
    sampling = SamplingConfig(
        temperature=float(sampling_raw.get("temperature", 0.55)),
        top_p=float(sampling_raw.get("top_p", 0.92)),
        top_k=int(sampling_raw.get("top_k", 40)),
        repeat_penalty=float(sampling_raw.get("repeat_penalty", 1.38)),
        presence_penalty=float(sampling_raw.get("presence_penalty", 0.55)),
        num_ctx=int(sampling_raw.get("num_ctx", 8192)),
        num_predict=int(sampling_raw.get("num_predict", 2048)),
    )
    system_prompt = str(data.get("system_prompt") or "").strip()
    stops_raw = [str(s) for s in stop_raw if str(s).strip()]
    stops: list[str] = []
    for token in stops_raw:
        if "redacted" in token.lower() or token in ("", "im_end"):
            stops.append(CHATML_IM_END)
        else:
            stops.append(token)
    if not stops:
        stops = [CHATML_IM_END, CHATML_IM_START]
    stops_tuple = tuple(dict.fromkeys(stops))

    ui_raw = data.get("ui") or {}
    ui = UiConfig(
        title=str(ui_raw.get("title") or "Pygenesis Unity").strip(),
        subtitle=str(ui_raw.get("subtitle") or "Haz una pregunta").strip(),
    )

    return BridgeConfig(
        inference_root=inference_root,
        model=model,
        server=server,
        chat=chat,
        system_prompt=system_prompt,
        sampling=sampling,
        stop=stops_tuple,
        llama_server_args=dict(data.get("llama_server_args") or {}),
        ui=ui,
    )
