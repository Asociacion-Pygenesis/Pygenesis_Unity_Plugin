"""Genera Modelfile.pygenesis-unity desde model_config.yaml (fuente única)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "pygenesis_backend"))

from providers.bridge.config import load_bridge_config  # noqa: E402


def main() -> None:
    cfg = load_bridge_config(ROOT / "model_config.yaml")
    im_start = cfg.chat.im_start
    im_end = cfg.chat.im_end
    out = ROOT.parent / "ollama" / "Modelfile.pygenesis-unity"
    gguf_rel = f"../pygenesis_inference/{cfg.model.gguf.as_posix()}"

    lines = [
        "# Generado por Tools/pygenesis_inference/export_ollama_modelfile.py",
        "# No editar a mano; cambia model_config.yaml y vuelve a ejecutar.",
        "",
        f"FROM {gguf_rel}",
        "",
        f'TEMPLATE """{im_start}system',
        "{{ .System }}" + im_end,
        f"{im_start}user",
        "{{ .Prompt }}" + im_end,
        f"{im_start}assistant",
        '"""',
        "",
        'SYSTEM """',
        cfg.system_prompt.rstrip(),
        '"""',
        "",
    ]
    s = cfg.sampling
    for token in cfg.stop:
        lines.append(f'PARAMETER stop "{token}"')
    lines.extend(
        [
            f"PARAMETER temperature {s.temperature}",
            f"PARAMETER top_p {s.top_p}",
            f"PARAMETER top_k {s.top_k}",
            f"PARAMETER repeat_penalty {s.repeat_penalty}",
            f"PARAMETER presence_penalty {s.presence_penalty}",
            f"PARAMETER num_ctx {s.num_ctx}",
            f"PARAMETER num_predict {s.num_predict}",
            "",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
