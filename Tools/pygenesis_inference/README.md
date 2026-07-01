# PyGenesis Inference Bridge

Puente de inferencia local **sin Ollama**: `llama-server` + `model_config.yaml` como fuente única.

## Estructura

```
Tools/pygenesis_inference/
  model_config.yaml      # system, sampling, stops, rutas
  start_bridge.ps1       # llama-server (interno) + citation_proxy (puerto público)
  citation_proxy.py      # filtra citas [Fuente…] en la Web UI (misma higiene que el plugin)
  export_ollama_modelfile.py
  bin/                   # llama-server + DLLs Vulkan (no versionado)
  models/                # GGUF (no versionado)
```

## Primer uso

1. GGUF en `models/pygenesis-unity-q4km.gguf` — [descargar en Hugging Face](https://huggingface.co/SuNavar/Pygenesis-Unity/blob/main/pygenesis-unity-q4km.gguf).
2. Binarios Vulkan en `bin/` — ver **`bin/README.txt`** (lista exacta de archivos del ZIP `llama-bXXXX-bin-win-vulkan-x64.zip`).
3. Arranque:
   - **Desde Unity (recomendado):** PyGenesis → Open Assistant → **Start Backend** (lanza puente + backend).
   - **Manual:**
     ```powershell
     cd Tools\pygenesis_inference
     powershell -File .\start_bridge.ps1
     ```

### Instalar `bin/` (solo la primera vez)

1. [Releases llama.cpp](https://github.com/ggml-org/llama.cpp/releases) → **`llama-bXXXX-bin-win-vulkan-x64.zip`** (no CUDA, no CPU-only).
2. Descomprime y copia a `Tools/pygenesis_inference/bin/` **solo** lo indicado en `bin/README.txt`:
   - `llama-server.exe`, `llama-server-impl.dll`
   - `llama.dll`, `llama-common.dll`, `mtmd.dll`
   - `ggml.dll`, `ggml-base.dll`, `ggml-vulkan.dll`
   - `libomp140.x86_64.dll`
   - **todos** los `ggml-cpu-*.dll` (14 archivos en releases recientes)
3. No copies `llama-cli.exe`, bench, quantize, etc.
4. `start_bridge.ps1` arranca **llama-server en un puerto interno** y un **proxy en :8081** que reenvía la Web UI y filtra citas `[Fuente…]` en `/v1/chat/completions`.

5. Backend `.env`:
   ```env
   PYGENESIS_LLM_PROVIDER=pygenesis_bridge
   PYGENESIS_BRIDGE_URL=http://127.0.0.1:8081/v1
   PYGENESIS_CHAT_PERSONA=ollama_native
   PYGENESIS_CHAT_REPETITION_GUARD=off
   ```
   Con `pygenesis_bridge`, el chat usa **passthrough** con filtro de citas `[Fuente…]`; Unity muestra `done.content` canónico al terminar.
5. Compara con Ollama:
   ```powershell
   cd Tools\pygenesis_backend
   .\.venv\Scripts\pip install PyYAML
   .\.venv\Scripts\python.exe scripts\compare_with_ollama.py
   ```

## Fuente única

- Edita **solo** `model_config.yaml`.
- Para regenerar el Modelfile de Ollama (referencia):
  ```powershell
  python Tools\pygenesis_inference\export_ollama_modelfile.py
  ```

## Backend

`PYGENESIS_LLM_PROVIDER=pygenesis_bridge` usa `LlamaCppBridgeProvider`:

- Un turno: system del YAML + último mensaje user.
- Sampling y stops del YAML (no overrides de `settings.json`).
- Sin dependencia del daemon Ollama.
