"""Emite JSON de arranque para start_bridge.ps1 (evita rutas rotas en PowerShell)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT.parent / "pygenesis_backend"
sys.path.insert(0, str(BACKEND))

from providers.bridge.config import load_bridge_config  # noqa: E402


def _css_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_ui_config_css(title: str, subtitle: str) -> str:
    """CSS inyectado vía --ui-config-file (customCss) en la Web UI de llama-server."""
    title_css = _css_string(title)
    subtitle_css = _css_string(subtitle)
    return f"""/* PyGenesis — branding Web UI llama-server */
div[class*="text-center"] > h1 {{
  font-size: 0 !important;
  line-height: 0 !important;
  margin-bottom: 0.5rem !important;
}}
div[class*="text-center"] > h1::after {{
  content: "{title_css}";
  font-size: 1.875rem;
  line-height: 2.25rem;
  display: block;
  font-weight: 600;
  letter-spacing: -0.025em;
}}
div[class*="text-center"] > p.text-muted-foreground {{
  font-size: 0 !important;
  line-height: 0 !important;
}}
div[class*="text-center"] > p.text-muted-foreground::after {{
  content: "{subtitle_css}";
  font-size: 1.125rem;
  line-height: 1.75rem;
  display: block;
  color: var(--muted-foreground);
}}
.flex-1:has(> textarea) {{
  position: relative;
}}
.flex-1:has(> textarea:placeholder-shown)::after {{
  content: "{subtitle_css}";
  position: absolute;
  left: 0;
  top: 0;
  pointer-events: none;
  color: var(--muted-foreground);
  font-size: 1rem;
  line-height: 1.5rem;
}}
.flex-1 > textarea::placeholder {{
  color: transparent !important;
}}
"""


def write_ui_config(
    inference_root: Path,
    title: str,
    subtitle: str,
    system_message: str,
) -> Path:
    ui_config_path = inference_root / "ui_config.json"
    # systemMessage: paridad con el plugin (bridge inyecta el mismo YAML).
    # Las citas [Fuente…] las filtra citation_proxy.py delante de llama-server.
    payload: dict[str, object] = {
        "customCss": build_ui_config_css(title, subtitle),
        "systemMessage": system_message,
        "showSystemMessage": False,
    }
    ui_config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return ui_config_path


def main() -> int:
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "model_config.yaml"
    cfg = load_bridge_config(cfg_path)
    system_file = ROOT / "system_prompt.txt"
    system_file.write_text(cfg.system_prompt, encoding="utf-8")
    ui_config_file = write_ui_config(
        cfg.inference_root,
        cfg.ui.title,
        cfg.ui.subtitle,
        cfg.system_prompt,
    )
    out = {
        "host": cfg.server.host,
        "port": cfg.server.port,
        "internal_port": cfg.server.port + 10000,
        "gguf": str(cfg.resolve_gguf_path()),
        "llama_server": str(cfg.resolve_llama_server_path()),
        "system_file": str(system_file),
        "ui_config": str(ui_config_file),
        "sampling": {
            "temperature": cfg.sampling.temperature,
            "top_p": cfg.sampling.top_p,
            "repeat_penalty": cfg.sampling.repeat_penalty,
            "num_ctx": cfg.sampling.num_ctx,
            "num_predict": cfg.sampling.num_predict,
        },
        "n_gpu_layers": cfg.llama_server_args.get("n_gpu_layers", 35),
        "threads": cfg.llama_server_args.get("threads", 8),
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
