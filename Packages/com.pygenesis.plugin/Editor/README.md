# PyGenesis — Editor (Unity)

Scripts del asistente PyGenesis en el editor. La responsabilidad está repartida entre **UI**, **red (HTTP)**, **proceso del backend** y **datos / utilidades**.

## Requisitos

- Unity con soporte de **Editor** (carpeta `Editor/`).
- Paquete **Newtonsoft.Json** (típico en proyectos Unity modernos).
- Backend Python en `Tools/pygenesis_backend` (o ruta configurada con `PyGenesisRuntimePaths`) escuchando en el host y puerto definidos en `PyGenesisBackendSettings`.

## Configuración de red y rutas

Todo lo relacionado con **URL base y puerto** está centralizado en:

| Clase | Uso |
|-------|-----|
| `PyGenesisBackendSettings` | `Host`, `Port`, `BaseUrl`, `HealthUrl`, `AnalyzeSelectionUrl`, `ChatCapabilitiesUrl`, `ChatUrl`, ruta al `start_backend_unity.bat`. |

Si cambias el puerto del backend, actualiza **`PyGenesisBackendSettings.Port`** (y el arranque del servidor Python) para que coincidan.

## Mapa de archivos

### Ventana y UI

| Archivo | Rol |
|---------|-----|
| `PyGenesisWindow.cs` | Clase `partial`: estado, `OnEnable` / `OnDisable`, lógica de backend (callbacks, corrutinas), parsing de respuesta, aplicación de acciones. |
| `PyGenesisWindow.UI.cs` | `partial`: `OnGUI` y todo el dibujo (secciones Backend, Selection, análisis, logs, tarjetas de acciones). |
| `PyGenesisChatWindow.cs` | Ventana **PyGenesis/Chat with PYgenesis AI**: se acopla junto a `PyGenesisWindow` (no junto a Scene); arrastrar la pestaña para flotar. |
| `PyGenesisChatHttpClient.cs` | `GET` capabilities, `POST` chat (UTF-8). |
| `PyGenesisChatModels.cs` | DTOs JSON alineados con el backend. |

La ventana usa **`PyGenesisBackendHttpClient`** para health y análisis, **`PyGenesisChatHttpClient`** para el chat, y **`PyGenesisBackendLauncher`** para arrancar/parar el proceso.

### Red (HTTP)

| Archivo | Rol |
|---------|-----|
| `PyGenesisAnalyzeRequestBuilder` | Construye `PyGenesisAnalyzeRequest` desde `Selection` y la escena activa (sin HTTP). |
| `PyGenesisBackendHttpClient` | `UnityWebRequest`: `GET` health, `POST` analyze; usa `EditorCoroutineRunner`. |
| `PyGenesisBridge` | **Fachada** que delega en el builder y en `PyGenesisBackendHttpClient`. Útil si quieres un único punto de entrada; la ventana puede llamar directamente al cliente HTTP. |

### Proceso del backend (Python en Windows)

| Archivo | Rol |
|---------|-----|
| `PyGenesisBackendProcessController` | Lanza `cmd.exe` con el `.bat`, redirige stdout/stderr al almacén de logs, para el proceso gestionado. |
| `PyGenesisBackendLogClassifier` | Clasifica cada línea de log (Info / Warning / Error) para la consola de la ventana. |
| `PyGenesisWindowsPortProcessKiller` | `netstat` + `findstr` + `taskkill` para liberar un puerto (p. ej. backend externo). |
| `PyGenesisBackendLauncher` | **Fachada** sobre el controlador de proceso y el killer de puerto; mantiene la API que ya usaba la UI. |

### Modelos y respuesta del API

| Archivo | Rol |
|---------|-----|
| `PygenesisModels.cs` | DTOs: request, selection, transform, `PyGenesisSuggestedAction`, `PyGenesisAnalyzeResponse`. |
| `MiniJsonParser.cs` | Deserializa la respuesta del backend cuando `params` llega como objeto JSON anidado (compatibilidad con el contrato Python). |

### Acciones en la escena

| Archivo | Rol |
|---------|-----|
| `PyGenesisActions.cs` | Registro `action → handler` (diccionario estático) alineado con el catálogo del servidor; ejecuta la acción sobre el `GameObject` analizado. Para una acción nueva, registra un manejador en `BuildRegistry()` y añade la entrada en el backend (`action_catalog.py`). |

### Soporte

| Archivo | Rol |
|---------|-----|
| `PyGenesisBackendLogStore` | Buffer thread-safe de líneas de log para la UI. |
| `EditorCoroutineRunner` | Ejecuta `IEnumerator` en el hilo del editor (peticiones HTTP asíncronas). |

## Flujo resumido

1. **Health check**: `PyGenesisBackendHttpClient.CheckBackendHealth` → `GET` `{BaseUrl}/health`.
2. **Analizar**: builder crea el JSON → `PyGenesisBackendHttpClient.AnalyzeSelection` → `POST` `{BaseUrl}/analyze-selection`.
3. **Respuesta**: `MiniJsonParser.ParseAnalyzeResponse` → texto visible (`message` o, si viene vacío, `summary`), lista de **issues** y **suggestions**.
4. **Aplicar**: usuario pulsa *Apply* → `PyGenesisActions.ExecuteAction`.
5. **Arranque local del backend**: `PyGenesisBackendProcessController` ejecuta el `.bat` bajo `Tools/pygenesis_backend`.

## Ampliar el plugin

- **Nuevo endpoint o cabeceras**: tocar `PyGenesisBackendHttpClient` y, si aplica, `PyGenesisBackendSettings`.
- **Más campos en la petición**: `PyGenesisAnalyzeRequestBuilder` y el modelo en `PygenesisModels.cs` (y el backend Python).
- **Cambios de UI**: preferentemente en `PyGenesisWindow.UI.cs`; estado compartido en `PyGenesisWindow.cs`.

### Checklist: nueva acción ejecutable (end-to-end)

Para que una acción nueva sea coherente entre servidor, LLM y Unity:

1. **`Tools/pygenesis_backend/reasoning/action_catalog.py`** — Añade una entrada en `ACTION_CATALOG` con `action_id`, `required_params` / `optional_params`, `safety`, `target` y `supports_auto_apply` si aplica. Sin esto, `output_validator.validate_action_step` descartará pasos del plan.
2. **`Tools/pygenesis_backend/rules/builtin.py`** (si usas reglas) — Genera `ActionStep` / `DetectedIssue` coherentes con el catálogo.
3. **`Tools/pygenesis_backend/reasoning/prompts.py`** (si usas LLM/híbrido) — El esquema JSON del prompt ya describe `plan` e `issues`; revisa que el texto de “allowed actions” siga alineado con el catálogo (o amplía el ejemplo si cambias el formato).
4. **`Packages/com.pygenesis.plugin/Editor/PyGenesisActions.cs`** — Añade un manejador y regístralo en `BuildRegistry()` con el mismo id de acción que en `action_catalog`.
5. **`PygenesisModels.cs` / `MiniJsonParser.cs`** — Solo si cambia el contrato (nuevos campos en `suggestions` o `issues`).

La UI muestra el resumen con `PyGenesisAnalyzeResponse.GetDisplayMessage()` (prioriza `message`, luego `summary`) y lista **Detected issues** debajo del cuadro de resumen.

## Documentación del servidor

El comportamiento del API, variables de entorno (`PYGENESIS_REASONING`, `OPENAI_API_KEY`, etc.) y el arranque con `uvicorn` están descritos en:

`Tools/pygenesis_backend/README.md`
