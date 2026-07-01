# PyGenesis Unity Plugin

Plugin de editor Unity con asistente de IA **local**: análisis de escena, chat conversacional y generación de scripts C#.

Repositorio de distribución: [Asociacion-Pygenesis/Pygenesis_Unity_Plugin](https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin)

## Requisitos

| Requisito | Detalle |
|-----------|---------|
| Unity | 2021.3 o superior |
| SO | Windows 10/11 x64 |
| Python | 3.10+ (lo instala el instalador) |
| Espacio | ~5 GB (modelo GGUF + binarios) |
| GPU | Vulkan recomendado (AMD/NVIDIA); funciona también en CPU |

## Instalación en 3 pasos

### 1. Plugin en Unity

**Window → Package Manager → + → Add package from git URL:**

```
https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin.git?path=Packages/com.pygenesis.plugin
```

### 2. Runtime (backend + puente + modelo)

Abre **PyGenesis → Setup** en Unity. El checklist te guía:

| Acción en Setup | Qué hace |
|-----------------|----------|
| **Instalar runtime (PowerShell)** | Backend Python, venv, `.env` → `%USERPROFILE%\.pygenesis` |
| **Descargar binarios Vulkan (automático)** | llama-server build `b9694` desde [GitHub Releases](https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin/releases) |
| **Modelo en Hugging Face** | `pygenesis-unity-q4km.gguf` (~4,7 GB) |

**Alternativa PowerShell** (sin Unity):

```powershell
git clone https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin.git
cd Pygenesis_Unity_Plugin
.\Tools\install\install_pygenesis.ps1 -InstallLlamaBinaries
```

Guía completa: [docs/INSTALL.md](docs/INSTALL.md)

### 3. Usar PyGenesis

1. **PyGenesis → Setup** — todo en verde.
2. **PyGenesis → Open Assistant** → **Start Backend** (puente `:8081` + API `:8765`).
3. **PyGenesis → Chat with Pygenesis AI** o navegador en **http://127.0.0.1:8081**.

La primera carga del modelo puede tardar varios minutos.

## Menús del plugin

| Menú | Función |
|------|---------|
| **PyGenesis → Setup** | Checklist de dependencias e instalación guiada |
| **PyGenesis → Open Assistant** | Análisis de escena/selección, arranque del backend |
| **PyGenesis → Chat with Pygenesis AI** | Chat con el modelo local |

## Estructura del repositorio

```
Packages/com.pygenesis.plugin/   ← Plugin UPM (Unity)
Tools/
  install/                       ← Instaladores y manifiesto de binarios
  pygenesis_backend/             ← API FastAPI (:8765)
  pygenesis_inference/           ← llama-server + proxy (:8081)
docs/                            ← Guías de instalación
manifest.json                    ← Versiones y URLs canónicas
```

## Binarios llama.cpp (Vulkan)

Descarga automática desde Setup o release **v0.2.0**:

[pygenesis-llama-vulkan-win-x64-b9694.zip](https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin/releases/download/v0.2.0/pygenesis-llama-vulkan-win-x64-b9694.zip)

## Ruta del runtime en Unity

Setup gestiona la carpeta runtime. Si instalaste en el perfil de usuario:

```csharp
PyGenesisRuntimePaths.SetToolsRoot(
    System.Environment.GetFolderPath(System.Environment.SpecialFolder.UserProfile) + "/.pygenesis");
```

## Licencia

MIT — ver [LICENSE](LICENSE).

## Enlaces

- **Modelo:** [Hugging Face — SuNavar/Pygenesis-Unity](https://huggingface.co/SuNavar/Pygenesis-Unity)
- **Releases (binarios):** [GitHub Releases](https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin/releases)
- **Organización:** [Asociacion-Pygenesis](https://github.com/Asociacion-Pygenesis)
