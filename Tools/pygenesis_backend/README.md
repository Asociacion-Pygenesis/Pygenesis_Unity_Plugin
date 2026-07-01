# PyGenesis Backend

API HTTP (FastAPI) que analiza la selección del editor Unity y devuelve un mensaje y sugerencias de acciones ejecutables en el cliente.

## Requisitos

- Python 3.10+ (recomendado 3.12)
- Entorno virtual en esta carpeta (`.venv`)

## Instalación

```powershell
cd Tools\pygenesis_backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Tests: pip install -r requirements-dev.txt
```

## Arranque

Desde esta carpeta, con el venv activado:

```powershell
python -u -m uvicorn main:app --host 127.0.0.1 --port 8765
```

También puedes usar:

- `start_backend_unity.bat` — arranque sin `pause` (pensado para lanzarlo desde Unity).
- `start_backend.bat` — arranque interactivo con `pause` al final.

El plugin de Unity asume por defecto **`http://127.0.0.1:8765`**.

## Configuración: `config/settings.json`

Valores por defecto del modo de razonamiento y del proveedor LLM (modelo, `base_url`, nombre de variable para la clave API, etc.). **No pongas secretos aquí**; usa variables de entorno o un archivo `.env` local.

### Archivo `.env` (solo desarrollo)

- Copia `.env.example` a **`.env`** en esta misma carpeta (`Tools/pygenesis_backend/`).
- Añade p. ej. `OPENAI_API_KEY=...`. El archivo `settings_loader.py` carga `.env` con **`python-dotenv`** si el paquete está instalado y si el archivo existe.
- **`override=False`**: si ya existe una variable en el sistema, no la sobrescribe el `.env`.
- **`.env` está en `.gitignore`**; no lo subas al repositorio.

## Variables de entorno

Sustituyen/extienden lo definido en `settings.json` cuando están definidas:

| Variable | Descripción |
|----------|-------------|
| `PYGENESIS_REASONING_MODE` | `rules`, `llm` o `hybrid`. |
| `PYGENESIS_REASONING` | Alias reconocido por compatibilidad (misma función que la anterior). |
| `PYGENESIS_LLM_PROVIDER` | p. ej. `openai_compatible`. |
| `PYGENESIS_LLM_MODEL` | Identificador del modelo. |
| `PYGENESIS_LLM_BASE_URL` | URL base del API (p. ej. `https://api.openai.com/v1`). |
| `PYGENESIS_LLM_API_KEY_ENV` | Nombre de la variable de entorno donde está la clave (por defecto `OPENAI_API_KEY`). |
| `PYGENESIS_LLM_TIMEOUT_SECONDS` | Timeout entero en segundos. |
| `PYGENESIS_LLM_TEMPERATURE` | Temperatura del modelo (`float`). |
| `PYGENESIS_LLM_USE_JSON_RESPONSE_FORMAT` | `true`/`false`: si `false`, no se envía `response_format: json_object` (útil en servidores locales que no lo soportan). Por defecto `true`. |
| `PYGENESIS_LLM_MAX_TOKENS` | Entero o vacío/`none`: límite de tokens de salida (por defecto `2048`). En CPU/local reduce tiempos largos de generación. |
| `PYGENESIS_LLM_WARMUP` | `true`/`false`: al arrancar el backend, una petición corta al LLM para cargar el modelo; el texto breve aparece en `GET /health` (`llm_warmup`) y en la ventana Unity. |
| `PYGENESIS_COMPACT_LLM_PROMPT` | `true`/`false` (por defecto `true`): prompt de análisis más corto (menos tokens → más rápido en CPU/Ollama). |
| `PYGENESIS_LLM_CHAT_MAX_TOKENS` | Límite de tokens de salida para `POST /chat` (por defecto igual que `chat_max_tokens` en settings). |
| `PYGENESIS_LLM_CHAT_TEMPERATURE` | Temperatura solo para chat; vacío/`none` = misma que `PYGENESIS_LLM_TEMPERATURE`. |
| `PYGENESIS_CHAT_MAX_HISTORY_MESSAGES` | Máximo de mensajes user+assistant enviados al modelo (truncado por el final). |
| `PYGENESIS_OLLAMA_REASONING_EFFORT` | Solo si `base_url` apunta a Ollama (p. ej. puerto `11434`) o `provider` es `ollama`/`local`: se envía `reasoning_effort` en el JSON de `/v1/chat/completions` (`none` por defecto) para modelos *thinking* (p. ej. Qwen 3). Valores: `none`, `low`, `medium`, `high`. Vacío / `false` / `off` = no enviar el campo. |

**Interpretar logs:** si ves `Analyze completed: mode=llm` fue el modelo. Si ves `mode=rules (fallback tras fallo del LLM)` se usaron reglas. La respuesta JSON incluye `mode` y `metadata.llm_duration_ms` cuando aplica.

**Rendimiento en hardware lento:** modelo más pequeño en Ollama (p. ej. `qwen3.5:4b`), `PYGENESIS_LLM_MAX_TOKENS` bajo (512–1024), y `PYGENESIS_COMPACT_LLM_PROMPT=true`.

La clave del LLM se lee de la variable indicada en `api_key_env` (típicamente **`OPENAI_API_KEY`**). Los servidores locales suelen aceptar una clave ficticia (`dummy`) si no validan el token.

## Inferencia local (carpeta `PygenesisAI`)

Los pesos del modelo viven en la raíz del proyecto Unity, carpeta **`PygenesisAI`** (formato Hugging Face). El backend **no** carga esos archivos directamente: hay que levantar un **servidor compatible con OpenAI** (`POST /v1/chat/completions`) que use esa ruta como `--model`.

Ejemplo con **vLLM** (requiere GPU adecuada, versión de vLLM compatible con Qwen3.5 y el paquete instalado en otro entorno; ajusta rutas y puerto):

```powershell
$modelPath = Resolve-Path (Join-Path $PSScriptRoot "..\..\PygenesisAI")
python -m vllm.entrypoints.openai.api_server `
  --model $modelPath `
  --served-model-name pygenesis-ai `
  --host 127.0.0.1 --port 8000 `
  --trust-remote-code
```

Luego arranca el backend PyGenesis con:

```powershell
$env:PYGENESIS_REASONING_MODE = "llm"
$env:PYGENESIS_LLM_BASE_URL = "http://127.0.0.1:8000/v1"
$env:PYGENESIS_LLM_MODEL = "pygenesis-ai"
$env:PYGENESIS_LLM_USE_JSON_RESPONSE_FORMAT = "false"
$env:OPENAI_API_KEY = "dummy"
python -u -m uvicorn main:app --host 127.0.0.1 --port 8765
```

El **rol de sistema** del LLM está definido como **PYgenesis AI** en `reasoning/llm_engine.py` y en los textos de `reasoning/prompts.py`.

Hay un script de referencia: `start_local_openai_server_example.ps1` (solo documenta el comando; no instala dependencias).

### vLLM + carpeta `PygenesisAI` (pesos Hugging Face locales)

Requiere **GPU NVIDIA + CUDA**. Con **AMD Radeon** (o sin GPU dedicada) usa **Ollama** en su lugar (siguiente apartado).

Instalación y arranque: **`Tools/vllm_pygenesis/README.md`** (`install.ps1` + `start_vllm_pygenesis.bat`). Backend: `PYGENESIS_LLM_BASE_URL=http://127.0.0.1:8000/v1`, `PYGENESIS_LLM_MODEL=pygenesis-ai`.

### Ollama + Qwen 3.5 (AMD / sin CUDA)

1. Instala [Ollama](https://ollama.com).
2. Flujo recomendado (**GGUF fine-tuned + Ollama**): ver **`Tools/ollama/README.md`** (`Modelfile.pygenesis-unity`, `ollama create pygenesis-unity`).
3. En `.env`: `PYGENESIS_LLM_BASE_URL=http://127.0.0.1:11434/v1`, `PYGENESIS_LLM_MODEL=pygenesis-unity` (o el nombre que hayas usado en `ollama create`), `PYGENESIS_LLM_USE_JSON_RESPONSE_FORMAT=false`, `OPENAI_API_KEY=dummy`.

No es el mismo binario que la carpeta `PygenesisAI` del proyecto (pesos HF), pero es la vía práctica en hardware sin NVIDIA.

En **PowerShell**:

```powershell
$env:PYGENESIS_REASONING_MODE = "hybrid"
$env:OPENAI_API_KEY = "sk-..."
```

En **cmd**:

```bat
set PYGENESIS_REASONING_MODE=llm
set OPENAI_API_KEY=sk-...
```

> No commitees claves API.

## Modos de razonamiento

- **`rules`** — Solo reglas deterministas definidas en `rules/builtin.py`. No llama al LLM. No requiere `OPENAI_API_KEY`.

- **`llm`** — El modelo genera el mensaje y las sugerencias a partir del JSON de la petición. Si falla la llamada o **no hay clave**, se usa el motor de **reglas** como respaldo.

- **`hybrid`** — Primero se calcula un borrador con **reglas**; después el **LLM** lo refina (mismo contrato de salida). Si el LLM falla o no hay clave, se devuelve el borrador de reglas.

Las sugerencias se filtran después contra las acciones que el cliente Unity soporta (ver `reasoning/output_validator.py`).

## API

### `GET /health`

Comprueba que el proceso responde. Respuesta típica: `{"status":"ok"}`.

### `GET /chat/capabilities`

Sin llamar al LLM: devuelve saludo sugerido, lista de capacidades y texto de ayuda para la UI conversacional (ver `reasoning/chat_prompts.py`).

### `POST /chat`

Conversación con PYgenesis AI. Cuerpo JSON (`ChatRequest`): `messages` (array de `{ "role": "user"|"assistant"|"system", "content": "..." }`, mínimo 1), `scene_name` opcional.

Se antepone un **system prompt** fijo (persona, capacidades, regla de no escribir en disco). Solo se conservan en historial los turnos **user/assistant**; se trunca a `chat_max_history_messages` (config / `PYGENESIS_CHAT_MAX_HISTORY_MESSAGES`).

Respuesta (`ChatResponse`): `role`, `content`, `metadata` (incluye `model`).

Variables relacionadas: `PYGENESIS_LLM_CHAT_MAX_TOKENS`, `PYGENESIS_LLM_CHAT_TEMPERATURE`, `PYGENESIS_CHAT_MAX_HISTORY_MESSAGES`.

**Windows PowerShell 5.x:** `Invoke-RestMethod -Body $json` puede enviar el cuerpo en UTF-16 y FastAPI responde `There was an error parsing the body`. Usa UTF-8 explícito o el script:

`Tools/pygenesis_backend/scripts/test_chat.ps1`

**Unity:** menú **PyGenesis → Chat with PYgenesis AI** o botón **Open conversational chat** en la ventana PyGenesis.

### `POST /analyze-selection`

Cuerpo JSON alineado con `models.AnalyzeSelectionRequest` (comando, nombre de escena, objeto `selection` opcional con transform y flags de componentes).

Respuesta: `AnalyzeSelectionResponse` — `summary`, `issues`, `plan`, `message` / `suggestions` (legacy para Unity), `execution_policy`, etc. (ver `models.py`).

### Checklist: nueva acción ejecutable

1. **`reasoning/action_catalog.py`** — Definición de la acción y parámetros permitidos.
2. **`rules/builtin.py`** — Si aplica lógica determinista que emite esa acción.
3. **`reasoning/prompts.py`** — Mantener el catálogo alineado con lo que puede devolver el LLM.
4. **Cliente Unity** — `PyGenesisActions.cs` + modelos/parser si cambia el JSON (ver `Packages/com.pygenesis.plugin/Editor/README.md`, sección checklist).

## Estructura del código

| Ruta | Rol |
|------|-----|
| `main.py` | FastAPI, lifespan (inicializa `AnalysisService`), rutas `/health`, `/chat`, `/analyze-selection`. |
| `reasoning/chat_prompts.py` | System prompt y `GET /chat/capabilities`. |
| `services/chat_service.py` | Orquesta `POST /chat` contra el proveedor OpenAI-compatible. |
| `models.py` | Modelos Pydantic del contrato API. |
| `services/analysis_service.py` | Orquesta validación de selección vacía, motor y validación de salida. |
| `services/selection_validation.py` | Detección de “sin selección” coherente con Unity. |
| `reasoning/engine.py` | Protocol `ReasoningEngine` y `RuleBasedEngine`. |
| `reasoning/llm_engine.py` | Llamadas al LLM (analyze / refine). |
| `reasoning/hybrid_engine.py` | Reglas + refinado LLM. |
| `config/settings.json` | Modo de razonamiento y ajustes del LLM. |
| `config/settings_loader.py` | Carga ajustes y aplica overrides por entorno. |
| `providers/` | Fábrica y proveedor HTTP compatible con OpenAI. |
| `reasoning/engine_factory.py` | Construye el motor según ajustes + proveedor LLM. |
| `reasoning/output_validator.py` | Normaliza mensaje y filtra acciones permitidas en Unity. |
| `rules/builtin.py` | Reglas individuales; la lista expuesta está en `rules/__init__.py`. |

## Cliente Unity

El plugin envía la petición y aplica en el editor solo las acciones reconocidas (por ejemplo `set_scale`, `add_box_collider`, `rename_selected`, …). Cualquier otra `action` que devuelva el LLM se **descarta** en el validador de salida.

## Pruebas y herramientas

Si usas `starlette.testclient.TestClient`, envuelve el cliente en un context manager para que se ejecute el **lifespan** y exista `app.state.analysis_service`:

```python
from starlette.testclient import TestClient
from main import app

with TestClient(app) as client:
    r = client.get("/health")
```

Sin el `with`, las rutas que dependen del estado inicializado en el lifespan pueden fallar.

## Tests (pytest)

Con el venv activado e instalación de dependencias de desarrollo:

```powershell
cd Tools\pygenesis_backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest
```

Incluye pruebas de `normalize_response`, `build_rule_response` y `AnalysisService` con un motor simulado (`tests/`).
