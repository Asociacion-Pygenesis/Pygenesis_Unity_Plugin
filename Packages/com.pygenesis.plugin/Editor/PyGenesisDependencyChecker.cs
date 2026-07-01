using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

/// <summary>
/// Comprueba dependencias del runtime PyGenesis (backend, inferencia, binarios llama.cpp).
/// Usado por el preflight del puente, la ventana Setup y el banner de Open Assistant.
/// </summary>
public static class PyGenesisDependencyChecker
{
    public enum DependencySeverity
    {
        Ok,
        Warning,
        Critical
    }

    public struct DependencyItem
    {
        public string Id;
        public string Label;
        public DependencySeverity Severity;
        public string Detail;
    }

    public struct LlamaBinaryCheckResult
    {
        public string BinDirectory;
        public int PresentCount;
        public int TotalCount;
        public IReadOnlyList<string> MissingFiles;
        public bool IsComplete => MissingFiles == null || MissingFiles.Count == 0;
    }

    public const string IdRuntimeRoot = "runtime_root";
    public const string IdBackend = "backend";
    public const string IdPythonVenv = "python_venv";
    public const string IdBackendEnv = "backend_env";
    public const string IdBridgeScript = "bridge_script";
    public const string IdLlamaBinaries = "llama_binaries";
    public const string IdGgufModel = "gguf_model";
    public const string IdBackendStart = "backend_start";

    /// <summary>True si falta algo imprescindible para arrancar backend + puente.</summary>
    public static bool HasCriticalGaps()
    {
        foreach (var item in RunAllChecks())
        {
            if (item.Severity == DependencySeverity.Critical)
            {
                return true;
            }
        }

        return false;
    }

    /// <summary>Texto breve para el banner de Open Assistant.</summary>
    public static string GetSetupBannerSummary()
    {
        var labels = new List<string>();
        foreach (var item in RunAllChecks())
        {
            if (item.Severity == DependencySeverity.Critical)
            {
                labels.Add(item.Label);
            }
        }

        if (labels.Count == 0)
        {
            return "";
        }

        if (labels.Count == 1)
        {
            return "PyGenesis no está listo para arrancar: falta " + labels[0] + ".";
        }

        int extra = labels.Count - 3;
        string joined = string.Join(", ", TakeFirst(labels, 3));
        if (extra > 0)
        {
            joined += "…";
        }

        return "PyGenesis no está listo para arrancar: faltan " + labels.Count
            + " dependencias (" + joined + ").";
    }

    private static IEnumerable<string> TakeFirst(IReadOnlyList<string> list, int max)
    {
        for (int i = 0; i < list.Count && i < max; i++)
        {
            yield return list[i];
        }
    }

    public static IReadOnlyList<DependencyItem> RunAllChecks()
    {
        var items = new List<DependencyItem>();
        items.Add(CheckRuntimeRoot());
        items.Add(CheckBackend());
        items.Add(CheckPythonVenv());
        items.Add(CheckBackendEnv());
        items.Add(CheckBridgeScript());
        items.Add(CheckLlamaBinariesItem());
        items.Add(CheckGgufModel());
        items.Add(CheckBackendStart());
        return items;
    }

    public static LlamaBinaryCheckResult CheckLlamaBinaries()
    {
        string binDir = Path.Combine(PyGenesisRuntimePaths.GetInferenceDataRoot(), "bin");
        var required = PyGenesisBinaryManifest.RequiredFiles;
        var missing = new List<string>();
        int present = 0;

        foreach (string fileName in required)
        {
            if (File.Exists(Path.Combine(binDir, fileName)))
            {
                present++;
            }
            else
            {
                missing.Add(fileName);
            }
        }

        return new LlamaBinaryCheckResult
        {
            BinDirectory = binDir,
            PresentCount = present,
            TotalCount = required.Count,
            MissingFiles = missing
        };
    }

    /// <summary>Mensaje para TryPreflight del puente (primer fallo crítico de inferencia).</summary>
    public static bool TryBuildBridgePreflightMessage(out string message)
    {
        var bridge = CheckBridgeScript();
        if (bridge.Severity == DependencySeverity.Critical)
        {
            message = bridge.Detail;
            return false;
        }

        var binaries = CheckLlamaBinaries();
        if (!binaries.IsComplete)
        {
            message = FormatMissingBinariesMessage(binaries);
            return false;
        }

        var gguf = CheckGgufModel();
        if (gguf.Severity == DependencySeverity.Critical)
        {
            message = gguf.Detail;
            return false;
        }

        message = "Runtime OK — data: " + PyGenesisRuntimePaths.GetInferenceDataRoot()
            + " | scripts: " + PyGenesisRuntimePaths.GetInferenceScriptsRoot()
            + " | binarios llama.cpp " + PyGenesisBinaryManifest.LlamaBuild
            + " (" + binaries.PresentCount + "/" + binaries.TotalCount + ")";
        return true;
    }

    public static string FormatMissingBinariesMessage(LlamaBinaryCheckResult result)
    {
        var sb = new StringBuilder();
        sb.Append("Binarios llama.cpp incompletos (")
            .Append(PyGenesisBinaryManifest.LlamaBuild)
            .Append("): ")
            .Append(result.PresentCount)
            .Append("/")
            .Append(result.TotalCount)
            .Append(" en:\n")
            .Append(result.BinDirectory)
            .Append("\n\nFaltan:\n");

        int shown = 0;
        foreach (string file in result.MissingFiles)
        {
            sb.Append("  • ").AppendLine(file);
            shown++;
            if (shown >= 12 && result.MissingFiles.Count > 12)
            {
                sb.Append("  • … y ").Append(result.MissingFiles.Count - shown).AppendLine(" más");
                break;
            }
        }

        sb.Append("\nDescarga el ZIP pre-filtrado PyGenesis (Vulkan, Windows x64) o copia desde ")
            .Append(PyGenesisBinaryManifest.LlamaBuild)
            .Append("-bin-win-vulkan-x64.zip (ver bin/README.txt).");

        string url = PyGenesisBinaryManifest.DownloadUrl;
        if (!string.IsNullOrWhiteSpace(url))
        {
            sb.Append("\nURL: ").Append(url);
        }

        return sb.ToString();
    }

    private static DependencyItem CheckRuntimeRoot()
    {
        string root = PyGenesisRuntimePaths.GetToolsRoot();
        bool ok = Directory.Exists(root);
        return new DependencyItem
        {
            Id = IdRuntimeRoot,
            Label = "Runtime root",
            Severity = ok ? DependencySeverity.Ok : DependencySeverity.Critical,
            Detail = ok
                ? root
                : "No se encontró la carpeta del runtime PyGenesis.\nEjecuta install_pygenesis.ps1 o indica la ruta con PyGenesisRuntimePaths.SetToolsRoot."
        };
    }

    private static DependencyItem CheckBackend()
    {
        string backendDir = PyGenesisRuntimePaths.BackendDirectory;
        string mainPy = Path.Combine(backendDir, "main.py");
        bool ok = File.Exists(mainPy);
        return new DependencyItem
        {
            Id = IdBackend,
            Label = "Backend Python",
            Severity = ok ? DependencySeverity.Ok : DependencySeverity.Critical,
            Detail = ok ? backendDir : "Falta pygenesis_backend/main.py en:\n" + backendDir
        };
    }

    private static DependencyItem CheckPythonVenv()
    {
        string py = Path.Combine(PyGenesisRuntimePaths.BackendDirectory, ".venv", "Scripts", "python.exe");
        bool ok = File.Exists(py);
        return new DependencyItem
        {
            Id = IdPythonVenv,
            Label = "Entorno virtual Python",
            Severity = ok ? DependencySeverity.Ok : DependencySeverity.Critical,
            Detail = ok ? py : "Falta .venv del backend. Ejecuta Tools\\install\\install_pygenesis.ps1"
        };
    }

    private static DependencyItem CheckBackendEnv()
    {
        string envFile = Path.Combine(PyGenesisRuntimePaths.BackendDirectory, ".env");
        bool ok = File.Exists(envFile);
        return new DependencyItem
        {
            Id = IdBackendEnv,
            Label = "Configuración .env",
            Severity = ok ? DependencySeverity.Ok : DependencySeverity.Warning,
            Detail = ok ? envFile : "Falta .env — copia .env.example en " + PyGenesisRuntimePaths.BackendDirectory
        };
    }

    private static DependencyItem CheckBridgeScript()
    {
        string script = PyGenesisRuntimePaths.BridgeStartScriptPath;
        bool ok = File.Exists(script);
        string root = PyGenesisRuntimePaths.GetToolsRoot();
        return new DependencyItem
        {
            Id = IdBridgeScript,
            Label = "Script puente (start_bridge.ps1)",
            Severity = ok ? DependencySeverity.Ok : DependencySeverity.Critical,
            Detail = ok
                ? script
                : "No se encontró start_bridge.ps1 en:\n" + script
                    + "\n\nRuntime detectado: " + root
                    + "\nSi instalaste en %USERPROFILE%\\.pygenesis, confirma la ruta con PyGenesisRuntimePaths.SetToolsRoot."
        };
    }

    private static DependencyItem CheckLlamaBinariesItem()
    {
        var result = CheckLlamaBinaries();
        bool ok = result.IsComplete;
        return new DependencyItem
        {
            Id = IdLlamaBinaries,
            Label = "Binarios llama.cpp (" + PyGenesisBinaryManifest.LlamaBuild + ")",
            Severity = ok ? DependencySeverity.Ok : DependencySeverity.Critical,
            Detail = ok
                ? result.PresentCount + "/" + result.TotalCount + " en " + result.BinDirectory
                : FormatMissingBinariesMessage(result)
        };
    }

    private static DependencyItem CheckGgufModel()
    {
        string gguf = PyGenesisRuntimePaths.GgufModelPath;
        bool ok = File.Exists(gguf);
        return new DependencyItem
        {
            Id = IdGgufModel,
            Label = "Modelo GGUF",
            Severity = ok ? DependencySeverity.Ok : DependencySeverity.Critical,
            Detail = ok
                ? gguf
                : "Falta el modelo GGUF en:\n" + gguf
                    + "\n\nData root inferencia: " + PyGenesisRuntimePaths.GetInferenceDataRoot()
                    + "\nDescárgalo de Hugging Face (SuNavar/Pygenesis-Unity) o ejecuta install_pygenesis.ps1"
        };
    }

    private static DependencyItem CheckBackendStart()
    {
        string bat = PyGenesisBackendSettings.BackendStartBatPath;
        bool ok = File.Exists(bat);
        return new DependencyItem
        {
            Id = IdBackendStart,
            Label = "Arranque backend (.bat)",
            Severity = ok ? DependencySeverity.Ok : DependencySeverity.Critical,
            Detail = ok ? bat : "Falta start_backend_unity.bat en:\n" + bat
        };
    }
}
