using System;
using System.Diagnostics;
using System.IO;
using UnityEditor;
using UnityEngine;
using Debug = UnityEngine.Debug;

/// <summary>Acciones de la ventana Setup (rutas, instalador, .env, explorador).</summary>
public static class PyGenesisSetupActions
{
    public static string ResolveInstallScriptPath()
    {
        foreach (string candidate in InstallScriptCandidates())
        {
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        return null;
    }

    public static bool TryApplyToolsRoot(string path, out string message)
    {
        path = (path ?? "").Trim();
        if (string.IsNullOrEmpty(path))
        {
            message = "Indica una carpeta de runtime válida.";
            return false;
        }

        try
        {
            path = Path.GetFullPath(path);
        }
        catch (Exception ex)
        {
            message = "Ruta no válida: " + ex.Message;
            return false;
        }

        if (!Directory.Exists(path))
        {
            message = "La carpeta no existe:\n" + path;
            return false;
        }

        PyGenesisRuntimePaths.SetToolsRoot(path);
        PyGenesisBinaryManifest.InvalidateCache();
        message = "Runtime root: " + path;
        return true;
    }

    public static bool TryUseDefaultUserRuntime(out string message)
    {
        string userRoot = PyGenesisRuntimePaths.UserRuntimeRoot;
        if (!Directory.Exists(userRoot))
        {
            try
            {
                Directory.CreateDirectory(userRoot);
            }
            catch (Exception ex)
            {
                message = "No se pudo crear " + userRoot + ": " + ex.Message;
                return false;
            }
        }

        return TryApplyToolsRoot(userRoot, out message);
    }

    public static bool TryBrowseToolsRoot(out string message)
    {
        string start = PyGenesisRuntimePaths.GetToolsRoot();
        if (!Directory.Exists(start))
        {
            start = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        }

        string picked = EditorUtility.OpenFolderPanel("Carpeta runtime PyGenesis", start, "");
        if (string.IsNullOrEmpty(picked))
        {
            message = "Selección cancelada.";
            return false;
        }

        return TryApplyToolsRoot(picked, out message);
    }

    public static bool TryCreateEnvFromExample(out string message)
    {
        string backendDir = PyGenesisRuntimePaths.BackendDirectory;
        string example = Path.Combine(backendDir, ".env.example");
        string envFile = Path.Combine(backendDir, ".env");

        if (!File.Exists(example))
        {
            message = "No se encontró .env.example en:\n" + backendDir;
            return false;
        }

        if (File.Exists(envFile))
        {
            message = ".env ya existe en:\n" + envFile;
            return true;
        }

        try
        {
            File.Copy(example, envFile);
            message = ".env creado en:\n" + envFile;
            return true;
        }
        catch (Exception ex)
        {
            message = "Error al crear .env: " + ex.Message;
            return false;
        }
    }

    public static bool TryRunInstallScript(out string message)
    {
        string script = ResolveInstallScriptPath();
        if (string.IsNullOrEmpty(script))
        {
            message = "No se encontró install_pygenesis.ps1.\nClona el repositorio PyGenesis o copia Tools/install/ junto al proyecto.";
            return false;
        }

        return TryLaunchPowerShellScript(script, "", out message,
            "Instalador lanzado:\n" + script + "\n\nCuando termine, pulsa «Volver a comprobar» en Setup.");
    }

    public static bool TryRunLlamaBinariesInstall(out string message)
    {
        string script = ResolveLlamaBinariesScriptPath();
        if (string.IsNullOrEmpty(script))
        {
            message = "No se encontró install_llama_binaries.ps1.\nCopia Tools/install/ del repositorio PyGenesis.";
            return false;
        }

        string binDir = Path.Combine(PyGenesisRuntimePaths.GetInferenceDataRoot(), "bin");
        string args = "-BinDir \"" + binDir + "\"";
        return TryLaunchPowerShellScript(script, args, out message,
            "Descarga de binarios iniciada.\nDestino: " + binDir
            + "\n\nCuando termine la ventana PowerShell, pulsa «Volver a comprobar».");
    }

    public static string ResolveLlamaBinariesScriptPath()
    {
        foreach (string candidate in LlamaBinariesScriptCandidates())
        {
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        return null;
    }

    public static void OpenInFileManager(string path)
    {
        path = (path ?? "").Trim();
        if (string.IsNullOrEmpty(path))
        {
            return;
        }

        try
        {
            if (File.Exists(path))
            {
                path = Path.GetDirectoryName(path);
            }

            if (!Directory.Exists(path))
            {
                EditorUtility.DisplayDialog("PyGenesis Setup", "La ruta no existe:\n" + path, "OK");
                return;
            }

            path = Path.GetFullPath(path);
            Process.Start(new ProcessStartInfo
            {
                FileName = path,
                UseShellExecute = true,
            });
        }
        catch (Exception ex)
        {
            Debug.LogWarning("PyGenesis Setup: no se pudo abrir " + path + ": " + ex.Message);
        }
    }

    public static void OpenUrl(string url)
    {
        if (string.IsNullOrWhiteSpace(url))
        {
            return;
        }

        Application.OpenURL(url);
    }

    private static bool TryLaunchPowerShellScript(string scriptPath, string extraArguments, out string message, string successMessage)
    {
        try
        {
            string workDir = Path.GetDirectoryName(scriptPath);
            string args = "-NoProfile -ExecutionPolicy Bypass -File \"" + scriptPath + "\"";
            if (!string.IsNullOrWhiteSpace(extraArguments))
            {
                args += " " + extraArguments;
            }

            var psi = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = args,
                WorkingDirectory = workDir,
                UseShellExecute = true,
            };

            Process proc = Process.Start(psi);
            if (proc == null)
            {
                message = "No se pudo lanzar PowerShell.";
                return false;
            }

            message = successMessage;
            return true;
        }
        catch (Exception ex)
        {
            message = "Error al lanzar script: " + ex.Message;
            Debug.LogWarning("PyGenesis Setup: " + message);
            return false;
        }
    }

    private static System.Collections.Generic.IEnumerable<string> LlamaBinariesScriptCandidates()
    {
        string projectInstall = Path.GetFullPath(
            Path.Combine(Application.dataPath, "..", "Tools", "install", "install_llama_binaries.ps1"));
        yield return projectInstall;

        string toolsRoot = PyGenesisRuntimePaths.GetToolsRoot();
        yield return Path.Combine(toolsRoot, "install", "install_llama_binaries.ps1");

        string parentInstall = Path.GetFullPath(Path.Combine(toolsRoot, "..", "install", "install_llama_binaries.ps1"));
        if (!string.Equals(parentInstall, projectInstall, StringComparison.OrdinalIgnoreCase))
        {
            yield return parentInstall;
        }
    }

    private static System.Collections.Generic.IEnumerable<string> InstallScriptCandidates()
    {
        string projectInstall = Path.GetFullPath(
            Path.Combine(Application.dataPath, "..", "Tools", "install", "install_pygenesis.ps1"));
        yield return projectInstall;

        string toolsRoot = PyGenesisRuntimePaths.GetToolsRoot();
        yield return Path.Combine(toolsRoot, "install", "install_pygenesis.ps1");

        string parentInstall = Path.GetFullPath(Path.Combine(toolsRoot, "..", "install", "install_pygenesis.ps1"));
        if (!string.Equals(parentInstall, projectInstall, StringComparison.OrdinalIgnoreCase))
        {
            yield return parentInstall;
        }
    }
}
