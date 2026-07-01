# Guía de instalación PyGenesis

## Resumen

PyGenesis consta de dos piezas:

1. **Plugin Unity** (`Packages/com.pygenesis.plugin`) — ventanas en el editor.
2. **Runtime local** — backend Python + puente llama.cpp + modelo GGUF.

Puedes usar el **chat en Unity** o el **navegador** (`http://127.0.0.1:8081`); ambos comparten el mismo modelo y system prompt.

**Plataforma soportada:** Windows 10/11 x64 (binarios llama.cpp con Vulkan).

---

## Instalación rápida (recomendada)

### 1. Añadir el plugin a Unity

1. Abre tu proyecto en Unity 2021.3+.
2. **Window → Package Manager → + → Add package from git URL…**
3. Pega:

   ```
   https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin.git?path=Packages/com.pygenesis.plugin
   ```

4. Espera a que resuelva la dependencia `com.unity.nuget.newtonsoft-json`.

### 2. Configurar el runtime desde Unity

1. Abre **PyGenesis → Setup**.
2. Sigue el checklist (semáforo verde/rojo):
   - **Instalar runtime (PowerShell)** — copia backend + inferencia, crea venv Python y `.env` (`install_pygenesis.ps1`).
   - **Descargar binarios Vulkan (automático)** — descarga el ZIP pre-filtrado desde [GitHub Releases](https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin/releases) (~37 MB, build `b9694`).
   - **Modelo en Hugging Face** — descarga `pygenesis-unity-q4km.gguf` (~4,7 GB) o usa el instalador con descarga automática.
3. Pulsa **Volver a comprobar** hasta que no queden dependencias críticas en rojo.

Si instalaste en `%USERPROFILE%\.pygenesis`, pulsa **Usar ~/.pygenesis** en Setup (o déjalo en auto-detect).

### 3. Arrancar

1. **PyGenesis → Open Assistant**
2. **Start Backend** — Unity lanza el puente (`:8081`) y el backend Python (`:8765`).
3. Espera el modelo listo (la primera carga del GGUF puede tardar varios minutos).
4. **PyGenesis → Chat with Pygenesis AI** o navegador en **http://127.0.0.1:8081**

Si falta algo al arrancar, Open Assistant muestra un banner con enlace a **Setup**.

---

## Instalación por PowerShell (alternativa)

Equivalente a los botones de Setup, útil en CI o sin abrir Unity:

```powershell
git clone https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin.git
cd Pygenesis_Unity_Plugin
.\Tools\install\install_pygenesis.ps1 -InstallLlamaBinaries
```

Parámetros útiles:

```powershell
.\Tools\install\install_pygenesis.ps1 -RuntimeRoot "D:\PyGenesis"
.\Tools\install\install_pygenesis.ps1 -SkipModelDownload
.\Tools\install\install_llama_binaries.ps1 -RuntimeRoot "$env:USERPROFILE\.pygenesis"
```

Por defecto el runtime se instala en `%USERPROFILE%\.pygenesis`.

### Tools junto al proyecto Unity

Copia la carpeta `Tools/` del repositorio al lado de `Assets/`. El plugin la detectará; Setup mostrará la ruta en **Runtime root**.

---

## Componentes del runtime

| Componente | Ubicación | Cómo instalarlo |
|------------|-----------|-----------------|
| Backend Python | `{runtime}/pygenesis_backend/` | Setup → Instalar runtime |
| Puente inferencia | `{runtime}/pygenesis_inference/` | Incluido en Instalar runtime |
| Binarios llama-server | `{runtime}/pygenesis_inference/bin/` | Setup → Descargar binarios Vulkan |
| Modelo GGUF | `{runtime}/pygenesis_inference/models/` | Instalador o [Hugging Face](https://huggingface.co/SuNavar/Pygenesis-Unity) |
| Config backend | `{runtime}/pygenesis_backend/.env` | Setup → Crear .env desde ejemplo |

Manifiesto de binarios (23 archivos, pin `b9694`): `Tools/install/llama_binaries_manifest.json`.

Release de binarios: [v0.2.0 — pygenesis-llama-vulkan-win-x64-b9694.zip](https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin/releases/download/v0.2.0/pygenesis-llama-vulkan-win-x64-b9694.zip)

---

## Modelo GGUF (Hugging Face)

Archivo: **`pygenesis-unity-q4km.gguf`** (~4,7 GB).

- Repo: **https://huggingface.co/SuNavar/Pygenesis-Unity**
- Destino: `{runtime}/pygenesis_inference/models/pygenesis-unity-q4km.gguf`

Con CLI (si no usaste el instalador):

```powershell
pip install huggingface-hub
huggingface-cli download SuNavar/Pygenesis-Unity pygenesis-unity-q4km.gguf --local-dir "%USERPROFILE%\.pygenesis\pygenesis_inference\models"
```

---

## Binarios llama-server (manual, solo si falla la descarga automática)

PyGenesis usa **llama-server** con **Vulkan** (AMD/NVIDIA). No uses ZIP de CUDA ni CPU-only.

### Opción A — ZIP PyGenesis (recomendado)

Descarga desde [GitHub Releases](https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin/releases) el asset **`pygenesis-llama-vulkan-win-x64-b9694.zip`** y extrae todo en `{runtime}/pygenesis_inference/bin/`.

### Opción B — ZIP oficial llama.cpp

1. [Releases llama.cpp](https://github.com/ggml-org/llama.cpp/releases) → **`llama-b9694-bin-win-vulkan-x64.zip`**
2. Copia **solo** los archivos listados en `pygenesis_inference/bin/README.txt` o en `llama_binaries_manifest.json`.

Comprobar:

```powershell
cd "%USERPROFILE%\.pygenesis\pygenesis_inference"
.\bin\llama-server.exe --version
```

---

## Configurar backend (.env)

Valores típicos (Setup puede crear `.env` desde `.env.example`):

```env
PYGENESIS_LLM_PROVIDER=pygenesis_bridge
PYGENESIS_BRIDGE_URL=http://127.0.0.1:8081/v1
```

---

## Unity: ruta del runtime

Setup gestiona la ruta vía **Runtime root**. Equivalente en consola del editor:

```csharp
PyGenesisRuntimePaths.SetToolsRoot(System.Environment.GetFolderPath(System.Environment.SpecialFolder.UserProfile) + "/.pygenesis");
```

---

## Uso

| Canal | URL / menú |
|-------|------------|
| Setup / checklist | **PyGenesis → Setup** |
| Unity Assistant | **PyGenesis → Open Assistant** |
| Unity Chat | **PyGenesis → Chat with Pygenesis AI** |
| Navegador | http://127.0.0.1:8081 |

---

## Solución de problemas

| Problema | Qué hacer |
|----------|-----------|
| Faltan dependencias | **PyGenesis → Setup** → revisar checklist → **Volver a comprobar** |
| «No response from server» | **Start Backend** en Open Assistant; comprueba `http://127.0.0.1:8765/health` |
| Puente no disponible / `WinError 10061` | Binarios incompletos o GGUF ausente → Setup; luego **Stop → Start Backend** |
| Binarios incompletos | Setup → **Descargar binarios Vulkan (automático)** |
| `llama-server` no arranca | ¿23 archivos en `bin/`? ¿Build Vulkan `b9694`? |
| Respuestas vacías | Verifica GGUF en `models/` |
| Vulkan / GPU en portátil | Baja `--n-gpu-layers` en `model_config.yaml` |
| Web UI rara | «Reset to default» en ajustes de llama-server |

---

## Mantenimiento (publicadores)

Regenerar y publicar binarios en GitHub Releases:

```powershell
cd Tools\install
.\build_llama_release_zip.ps1 -UpdateManifest
.\publish_llama_release.ps1 -SkipBuild
```

Ver `llama_binaries_manifest.json` para pin de versión y SHA256.
