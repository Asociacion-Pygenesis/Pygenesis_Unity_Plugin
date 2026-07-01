using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Manifiesto de binarios llama.cpp (Vulkan, Windows x64). Fuente: Tools/install/llama_binaries_manifest.json
/// y copia embebida en el paquete del plugin.
/// </summary>
public static class PyGenesisBinaryManifest
{
    private const string ManifestFileName = "llama_binaries_manifest.json";

    private static JObject _cached;

    public static string LlamaBuild => LoadRoot()?["llama_build"]?.ToString() ?? "b9694";

    public static string Platform => LoadRoot()?["platform"]?.ToString() ?? "win-vulkan-x64";

    public static string DownloadUrl => LoadRoot()?["download"]?["url"]?.ToString() ?? "";

    public static IReadOnlyList<string> RequiredFiles
    {
        get
        {
            var root = LoadRoot();
            var list = new List<string>();
            if (root?["required_files"] is JArray arr)
            {
                foreach (var token in arr)
                {
                    string name = token?.ToString()?.Trim();
                    if (!string.IsNullOrEmpty(name))
                    {
                        list.Add(name);
                    }
                }
            }

            if (list.Count == 0)
            {
                list.Add("llama-server.exe");
            }

            return list;
        }
    }

    public static void InvalidateCache()
    {
        _cached = null;
    }

    private static JObject LoadRoot()
    {
        if (_cached != null)
        {
            return _cached;
        }

        foreach (string path in CandidateManifestPaths())
        {
            if (string.IsNullOrEmpty(path) || !File.Exists(path))
            {
                continue;
            }

            try
            {
                _cached = JObject.Parse(File.ReadAllText(path));
                return _cached;
            }
            catch (Exception ex)
            {
                Debug.LogWarning("PyGenesis: no se pudo leer " + path + ": " + ex.Message);
            }
        }

        return null;
    }

    private static IEnumerable<string> CandidateManifestPaths()
    {
        string toolsInstall = Path.Combine(PyGenesisRuntimePaths.GetToolsRoot(), "install", ManifestFileName);
        yield return toolsInstall;

        string projectToolsInstall = Path.GetFullPath(
            Path.Combine(Application.dataPath, "..", "Tools", "install", ManifestFileName));
        if (!string.Equals(projectToolsInstall, toolsInstall, StringComparison.OrdinalIgnoreCase))
        {
            yield return projectToolsInstall;
        }

        string embedded = ResolveEmbeddedManifestPath();
        if (!string.IsNullOrEmpty(embedded))
        {
            yield return embedded;
        }
    }

    private static string ResolveEmbeddedManifestPath()
    {
        string[] guids = AssetDatabase.FindAssets(Path.GetFileNameWithoutExtension(ManifestFileName));
        string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));

        foreach (string guid in guids)
        {
            string assetPath = AssetDatabase.GUIDToAssetPath(guid);
            if (!assetPath.EndsWith(ManifestFileName, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            return Path.GetFullPath(Path.Combine(projectRoot, assetPath));
        }

        return null;
    }
}
