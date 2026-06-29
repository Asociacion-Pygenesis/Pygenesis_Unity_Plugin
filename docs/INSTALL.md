# Guía de instalación PyGenesis

## Resumen

PyGenesis consta de dos piezas:

1. **Plugin Unity** (`Packages/com.pygenesis.plugin`) — ventanas en el editor.
2. **Runtime local** — backend Python + puente llama.cpp + modelo GGUF.

Puedes usar el **chat en Unity** o el **navegador** (`http://127.0.0.1:8081`); ambos comparten el mismo modelo y system prompt.

---

## Paso 1 — Añadir el plugin a Unity

1. Abre tu proyecto en Unity 2021.3+.
2. **Window → Package Manager → + → Add package from git URL…**
3. Pega:

   ```
   https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin.git?path=Packages/com.pygenesis.plugin
   ```

4. Espera a que resuelva la dependencia `com.unity.nuget.newtonsoft-json`.

---

## Paso 2 — Instalar el runtime

### Opción A — Instalador (recomendado)

```powershell
git clone https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin.git
cd Pygenesis_Unity_Plugin
.\Tools\install\install_pygenesis.ps1
```

Parámetros útiles:

```powershell
.\Tools\install\install_pygenesis.ps1 -RuntimeRoot "D:\PyGenesis"
.\Tools\install\install_pygenesis.ps1 -SkipModelDownload
```

Por defecto instala en `%USERPROFILE%\.pygenesis`.

### Opción B — Tools junto al proyecto Unity

Clona o copia la carpeta `Tools/` del repositorio al lado de `Assets/` en tu proyecto Unity. El plugin la detectará automáticamente.

---

## Paso 3 — Modelo GGUF (Hugging Face)

Descarga `pygenesis-unity-q4km.gguf` desde:

**https://huggingface.co/SuNavar/Pygenesis-Unity**

Enlace directo al archivo: [pygenesis-unity-q4km.gguf](https://huggingface.co/SuNavar/Pygenesis-Unity/blob/main/pygenesis-unity-q4km.gguf) (~4,7 GB).

Colócalo en:

```
{runtime}/pygenesis_inference/models/pygenesis-unity-q4km.gguf
```

Con CLI:

```powershell
pip install huggingface-hub
huggingface-cli download SuNavar/Pygenesis-Unity pygenesis-unity-q4km.gguf --local-dir "%USERPROFILE%\.pygenesis\pygenesis_inference\models"
```

---

## Paso 4 — Binarios llama-server (Vulkan, Windows x64)

PyGenesis usa **llama-server** con soporte **Vulkan** (AMD/NVIDIA integrada o dedicada). No uses el ZIP de CUDA ni el de «CPU only».

### Descarga

1. [Releases de llama.cpp](https://github.com/ggml-org/llama.cpp/releases)
2. Asset: **`llama-bXXXX-bin-win-vulkan-x64.zip`** (el `bXXXX` es el número de build; cualquier release reciente vale).
3. Descomprime el ZIP.

### Qué copiar

Copia **solo** estos archivos a `{runtime}/pygenesis_inference/bin/`:

| Archivo | Obligatorio |
|---------|-------------|
| `llama-server.exe` | Sí |
| `llama-server-impl.dll` | Sí |
| `llama.dll`, `llama-common.dll`, `mtmd.dll` | Sí |
| `ggml.dll`, `ggml-base.dll`, `ggml-vulkan.dll` | Sí |
| `libomp140.x86_64.dll` | Sí |
| Todos los `ggml-cpu-*.dll` del ZIP (14 archivos) | Sí |

Lista completa y comprobación: **`pygenesis_inference/bin/README.txt`**.

**No copies** `llama-cli.exe`, `llama-bench.exe` ni otros ejecutables del ZIP.

### Comprobar

```powershell
cd "%USERPROFILE%\.pygenesis\pygenesis_inference"
.\bin\llama-server.exe --version
```

Si imprime la versión, los binarios están en el sitio correcto.

---

## Paso 5 — Configurar backend

Copia y ajusta si hace falta:

```
{runtime}/pygenesis_backend/.env.example  →  .env
```

Valores típicos con el puente local:

```env
PYGENESIS_LLM_PROVIDER=pygenesis_bridge
PYGENESIS_BRIDGE_URL=http://127.0.0.1:8081/v1
```

---

## Paso 6 — Arrancar desde Unity (recomendado)

1. **PyGenesis → Open Assistant**
2. **Start Backend** — Unity lanza en este orden:
   - Puente de inferencia (`start_bridge.ps1`) → **http://127.0.0.1:8081**
   - Backend Python → **http://127.0.0.1:8765**
3. Espera el mensaje de modelo listo (la primera carga del GGUF en GPU/CPU puede tardar **varios minutos**).
4. **PyGenesis → Chat with Pygenesis AI** o navegador en **http://127.0.0.1:8081**

Si el backend arrancó antes de que el puente estuviera listo, no hace falta reiniciar a mano: el backend **reintenta el warmup** cada ~15 s. También puedes **Stop Backend → Start Backend**.

### Arranque manual (opcional)

```powershell
powershell -File "%USERPROFILE%\.pygenesis\pygenesis_inference\start_bridge.ps1"
"%USERPROFILE%\.pygenesis\pygenesis_backend\start_backend_unity.bat"
```

---

## Paso 7 — Unity: ruta del runtime

Si usaste `%USERPROFILE%\.pygenesis`, en la consola del editor (o vía código):

```csharp
PyGenesisRuntimePaths.SetToolsRoot(System.Environment.GetFolderPath(System.Environment.SpecialFolder.UserProfile) + "/.pygenesis");
```

---

## Uso

| Canal | URL / menú |
|-------|------------|
| Unity Chat | **PyGenesis → Chat with Pygenesis AI** |
| Unity Assistant | **PyGenesis → Open Assistant** |
| Navegador | http://127.0.0.1:8081 |

---

## Solución de problemas

| Problema | Qué hacer |
|----------|-----------|
| «No response from server» en Unity | Pulsa **Start Backend** en Open Assistant; comprueba `http://127.0.0.1:8765/health` |
| Puente no disponible / `WinError 10061` | Nada escucha en **:8081**. Revisa logs en Open Assistant: ¿`llama-server.exe` y las DLL en `bin/`? ¿GGUF en `models/`? **Stop → Start Backend** |
| Web UI no carga | Puerto 8081 libre; o arranca manualmente `start_bridge.ps1` |
| `llama-server` no arranca | ¿Descargaste **win-vulkan-x64**? ¿Copiaste las 14 `ggml-cpu-*.dll`? |
| Respuestas vacías | Verifica que el GGUF está en `models/` |
| Vulkan / GPU en portátil | Baja `--n-gpu-layers` en `model_config.yaml` o prueba solo CPU |
| Web UI rara | «Reset to default» en ajustes de llama-server |

---

## Próximas versiones del instalador

- Descarga automática de binarios llama.cpp
- Asistente **PyGenesis → Setup** en el editor (comprobaciones y rutas en un solo panel)
