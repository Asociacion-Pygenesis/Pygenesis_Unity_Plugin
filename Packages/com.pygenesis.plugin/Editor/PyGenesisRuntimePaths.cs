using System;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Resuelve la carpeta <c>Tools/</c> del runtime PyGenesis (backend + inferencia).
/// Orden Tools root: EditorPrefs → %USERPROFILE%/.pygenesis (instalado) → Tools del proyecto.
/// Modelo y llama-server: %USERPROFILE%/.pygenesis/pygenesis_inference si están ahí (portátil).
/// </summary>
public static class PyGenesisRuntimePaths
{
    private const string ToolsRootPrefKey = "PyGenesis.ToolsRoot";
    private const string DefaultGgufFileName = "pygenesis-unity-q4km.gguf";

    public static string UserRuntimeRoot =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".pygenesis");

    public static string GetToolsRoot()
    {
        string custom = (EditorPrefs.GetString(ToolsRootPrefKey, "") ?? "").Trim();
        if (!string.IsNullOrEmpty(custom))
        {
            string full = Path.GetFullPath(custom);
            if (Directory.Exists(full))
            {
                return full;
            }
        }

        string userRoot = UserRuntimeRoot;
        if (Directory.Exists(Path.Combine(userRoot, "pygenesis_backend")))
        {
            return userRoot;
        }
        if (Directory.Exists(Path.Combine(userRoot, "Tools", "pygenesis_backend")))
        {
            return Path.Combine(userRoot, "Tools");
        }

        string projectTools = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "Tools"));
        if (Directory.Exists(Path.Combine(projectTools, "pygenesis_backend")))
        {
            return projectTools;
        }

        if (Directory.Exists(Path.Combine(userRoot, "pygenesis_inference")))
        {
            return userRoot;
        }

        return projectTools;
    }

    public static void SetToolsRoot(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            EditorPrefs.DeleteKey(ToolsRootPrefKey);
            return;
        }
        EditorPrefs.SetString(ToolsRootPrefKey, Path.GetFullPath(path.Trim()));
    }

    /// <summary>Donde viven scripts (start_bridge.ps1, dump_launch_info.py).</summary>
    public static string GetInferenceScriptsRoot()
    {
        foreach (string candidate in InferenceRootCandidates())
        {
            if (File.Exists(Path.Combine(candidate, "start_bridge.ps1")))
            {
                return candidate;
            }
        }

        return Path.Combine(GetToolsRoot(), "pygenesis_inference");
    }

    /// <summary>Donde viven bin/ y models/ (puede ser ~/.pygenesis aunque el repo esté en el proyecto).</summary>
    public static string GetInferenceDataRoot()
    {
        if (TryReadUserConfig(out string runtimeRoot, out string modelPath))
        {
            if (!string.IsNullOrEmpty(runtimeRoot))
            {
                string fromConfig = Path.Combine(runtimeRoot, "pygenesis_inference");
                if (Directory.Exists(fromConfig) && HasInferenceAssets(fromConfig))
                {
                    return fromConfig;
                }
            }

            if (!string.IsNullOrEmpty(modelPath) && File.Exists(modelPath))
            {
                return Path.GetDirectoryName(Path.GetDirectoryName(modelPath));
            }
        }

        foreach (string candidate in InferenceRootCandidates())
        {
            if (HasInferenceAssets(candidate))
            {
                return candidate;
            }
        }

        return Path.Combine(GetToolsRoot(), "pygenesis_inference");
    }

    public static string BackendDirectory =>
        Path.Combine(GetToolsRoot(), "pygenesis_backend");

    public static string InferenceDirectory => GetInferenceScriptsRoot();

    public static string BackendStartBatPath =>
        Path.Combine(BackendDirectory, "start_backend_unity.bat");

    public static string BridgeStartScriptPath =>
        Path.Combine(GetInferenceScriptsRoot(), "start_bridge.ps1");

    public static string GgufModelPath => ResolveGgufPath();

    public static string LlamaServerExePath =>
        Path.Combine(GetInferenceDataRoot(), "bin", "llama-server.exe");

    private static string[] InferenceRootCandidates()
    {
        string userInf = Path.Combine(UserRuntimeRoot, "pygenesis_inference");
        string toolsInf = Path.Combine(GetToolsRoot(), "pygenesis_inference");
        if (string.Equals(userInf, toolsInf, StringComparison.OrdinalIgnoreCase))
        {
            return new[] { userInf };
        }
        return new[] { userInf, toolsInf };
    }

    private static bool HasInferenceAssets(string inferenceRoot)
    {
        if (string.IsNullOrEmpty(inferenceRoot) || !Directory.Exists(inferenceRoot))
        {
            return false;
        }

        if (File.Exists(Path.Combine(inferenceRoot, "bin", "llama-server.exe")))
        {
            return true;
        }

        string modelsDir = Path.Combine(inferenceRoot, "models");
        return Directory.Exists(modelsDir)
               && Directory.GetFiles(modelsDir, "*.gguf").Length > 0;
    }

    private static string ResolveGgufPath()
    {
        if (TryReadUserConfig(out _, out string modelPath)
            && !string.IsNullOrEmpty(modelPath)
            && File.Exists(modelPath))
        {
            return modelPath;
        }

        string dataRoot = GetInferenceDataRoot();
        string configured = Path.Combine(dataRoot, "models", DefaultGgufFileName);
        if (File.Exists(configured))
        {
            return configured;
        }

        string modelsDir = Path.Combine(dataRoot, "models");
        if (Directory.Exists(modelsDir))
        {
            string[] ggufs = Directory.GetFiles(modelsDir, "*.gguf");
            if (ggufs.Length == 1)
            {
                return ggufs[0];
            }

            if (ggufs.Length > 1)
            {
                string named = ggufs.FirstOrDefault(g =>
                    Path.GetFileName(g).IndexOf("pygenesis", StringComparison.OrdinalIgnoreCase) >= 0);
                if (!string.IsNullOrEmpty(named))
                {
                    return named;
                }
                return ggufs[0];
            }
        }

        return configured;
    }

    private static bool TryReadUserConfig(out string runtimeRoot, out string modelPath)
    {
        runtimeRoot = null;
        modelPath = null;
        string configPath = Path.Combine(UserRuntimeRoot, "config.json");
        if (!File.Exists(configPath))
        {
            return false;
        }

        try
        {
            var jo = JObject.Parse(File.ReadAllText(configPath));
            runtimeRoot = jo["runtime_root"]?.ToString()?.Trim();
            modelPath = jo["model_path"]?.ToString()?.Trim();
            return !string.IsNullOrEmpty(runtimeRoot) || !string.IsNullOrEmpty(modelPath);
        }
        catch
        {
            return false;
        }
    }
}
