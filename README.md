# PyGenesis Unity Plugin

Plugin de editor Unity con asistente de IA local: análisis de escena, chat conversacional y generación de scripts C#.

Repositorio público de distribución: [Asociacion-Pygenesis/Pygenesis_Unity_Plugin](https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin)

## Requisitos

- **Unity** 2021.3 o superior
- **Windows** 10/11 (puente llama.cpp Vulkan)
- **Python** 3.10+
- **~5 GB** de espacio libre (modelo GGUF + binarios)
- GPU con **Vulkan** recomendada (AMD/NVIDIA); funciona también en CPU

## Instalación rápida

### 1. Plugin en tu proyecto Unity

**Package Manager → Add package from git URL:**

```
https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin.git?path=Packages/com.pygenesis.plugin
```

O clona este repositorio y añade `Packages/com.pygenesis.plugin` como paquete local.

### 2. Runtime (backend + puente + modelo)

```powershell
git clone https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin.git
cd Pygenesis_Unity_Plugin
.\Tools\install\install_pygenesis.bat
```

El instalador copia `Tools/` a `%USERPROFILE%\.pygenesis` (o la carpeta que elijas), crea el venv Python y deja listo el backend.

**Descargas manuales (v0.1):**

| Componente | Dónde |
|------------|--------|
| Modelo GGUF | [Hugging Face — SuNavar/Pygenesis-Unity](https://huggingface.co/SuNavar/Pygenesis-Unity) → `pygenesis-unity-q4km.gguf` en `models/` |
| llama-server (Vulkan) | [Releases llama.cpp](https://github.com/ggml-org/llama.cpp/releases) → asset **`llama-bXXXX-bin-win-vulkan-x64.zip`** → copiar solo los archivos listados en `Tools/pygenesis_inference/bin/README.txt` |

Ver [docs/INSTALL.md](docs/INSTALL.md) para el paso a paso completo (lista exacta de `.exe` y `.dll`).

### 3. Arranque (desde Unity)

1. Abre **PyGenesis → Open Assistant**.
2. Pulsa **Start Backend** — Unity arranca el **puente** (`start_bridge.ps1`, puerto **8081**) y el **backend** Python (puerto **8765**).
3. Espera a que el estado indique que el modelo está listo (`llm_ready`; la primera carga del GGUF puede tardar varios minutos).
4. Usa **PyGenesis → Chat with Pygenesis AI** o el navegador en **http://127.0.0.1:8081**.

**Arranque manual** (opcional, p. ej. solo Web UI sin Unity):

```powershell
powershell -File "%USERPROFILE%\.pygenesis\pygenesis_inference\start_bridge.ps1"
"%USERPROFILE%\.pygenesis\pygenesis_backend\start_backend_unity.bat"
```

## Estructura del repositorio

```
Packages/com.pygenesis.plugin/   ← Plugin UPM
Tools/
  install/                       ← Instalador
  pygenesis_backend/             ← API FastAPI (:8765)
  pygenesis_inference/           ← llama-server + proxy (:8081)
docs/                            ← Guías de instalación
manifest.json                    ← Versiones y URLs canónicas
```

## Configurar ruta de Tools en Unity

Si instalaste el runtime fuera del proyecto:

```csharp
PyGenesisRuntimePaths.SetToolsRoot(@"C:\Users\TuUsuario\.pygenesis");
```

(O desde la consola del editor cuando exista el asistente de Setup.)

## Licencia

MIT — ver [LICENSE](LICENSE).

## Enlaces

- Modelo: [Hugging Face — SuNavar/Pygenesis-Unity](https://huggingface.co/SuNavar/Pygenesis-Unity)
- Organización: [Asociacion-Pygenesis](https://github.com/Asociacion-Pygenesis)
