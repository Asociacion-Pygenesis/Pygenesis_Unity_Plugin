using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using UnityEngine;
using UnityEngine.Networking;
using Debug = UnityEngine.Debug;

/// <summary>
/// Arranca el puente de inferencia (start_bridge.ps1) si no responde en el puerto público.
/// </summary>
public static class PyGenesisBridgeLauncher
{
    private const int BridgePublicPort = 8081;
    private static Process bridgeProcess;

    public static bool IsManagedBridgeRunning()
    {
        return bridgeProcess != null && !bridgeProcess.HasExited;
    }

    /// <summary>Comprueba GGUF y llama-server antes de lanzar el puente.</summary>
    public static bool TryPreflight(out string message)
    {
        string root = PyGenesisRuntimePaths.GetToolsRoot();
        string gguf = PyGenesisRuntimePaths.GgufModelPath;
        string server = PyGenesisRuntimePaths.LlamaServerExePath;
        string script = PyGenesisRuntimePaths.BridgeStartScriptPath;

        if (!File.Exists(script))
        {
            message = "No se encontró start_bridge.ps1 en:\n" + script
                + "\n\nRuntime detectado: " + root
                + "\nSi instalaste en %USERPROFILE%\\.pygenesis, ejecuta en consola:\n"
                + "PyGenesisRuntimePaths.SetToolsRoot(@\"" + root + "\");";
            return false;
        }

        if (!File.Exists(server))
        {
            message = "Falta llama-server.exe en:\n" + server
                + "\n\nData root inferencia: " + PyGenesisRuntimePaths.GetInferenceDataRoot()
                + "\nCopia bin/ desde llama-bXXXX-bin-win-vulkan-x64.zip (ver bin/README.txt)";
            return false;
        }

        if (!File.Exists(gguf))
        {
            message = "Falta el modelo GGUF en:\n" + gguf
                + "\n\nData root inferencia: " + PyGenesisRuntimePaths.GetInferenceDataRoot()
                + "\nScripts puente: " + PyGenesisRuntimePaths.GetInferenceScriptsRoot()
                + "\n\nDescárgalo de Hugging Face (SuNavar/Pygenesis-Unity) o ejecuta install_pygenesis.ps1";
            return false;
        }

        message = "Runtime OK — data: " + PyGenesisRuntimePaths.GetInferenceDataRoot()
            + " | scripts: " + PyGenesisRuntimePaths.GetInferenceScriptsRoot();
        return true;
    }

    public static bool TryEnsureBridgeRunning(out string message)
    {
        if (!TryPreflight(out message))
        {
            return false;
        }

        if (IsBridgeReachableSync())
        {
            message = "Puente de inferencia ya activo en :" + BridgePublicPort + ".";
            return true;
        }

        if (IsManagedBridgeRunning())
        {
            message = "Puente iniciado por Unity; esperando respuesta en :" + BridgePublicPort + "…";
            return true;
        }

        string scriptPath = PyGenesisRuntimePaths.BridgeStartScriptPath;

        try
        {
            string inferenceDir = PyGenesisRuntimePaths.InferenceDirectory;
            PyGenesisBackendLogStore.AddLine(
                "[Unity] Starting inference bridge…",
                PyGenesisBackendLogStore.LogType.Info);

            var psi = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + scriptPath + "\"",
                WorkingDirectory = inferenceDir,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
            };

            bridgeProcess = new Process
            {
                StartInfo = psi,
                EnableRaisingEvents = true,
            };

            bridgeProcess.OutputDataReceived += OnBridgeOutput;
            bridgeProcess.ErrorDataReceived += OnBridgeOutput;
            bridgeProcess.Exited += (_, __) =>
            {
                PyGenesisBackendLogStore.AddLine(
                    "[Unity] Inference bridge process exited (revisa errores arriba: binarios, GGUF, Vulkan).",
                    PyGenesisBackendLogStore.LogType.Warning);
            };

            if (!bridgeProcess.Start())
            {
                message = "No se pudo lanzar el puente de inferencia.";
                return false;
            }

            bridgeProcess.BeginOutputReadLine();
            bridgeProcess.BeginErrorReadLine();

            message = "Puente de inferencia arrancando (:" + BridgePublicPort + ")…";
            return true;
        }
        catch (Exception ex)
        {
            message = "Error al arrancar el puente: " + ex.Message;
            Debug.LogWarning("PyGenesis: " + message);
            return false;
        }
    }

    /// <summary>Espera hasta que :8081 responda o el proceso del puente termine.</summary>
    public static bool WaitForBridgeReady(float timeoutSeconds, out string message)
    {
        var sw = Stopwatch.StartNew();
        while (sw.Elapsed.TotalSeconds < timeoutSeconds)
        {
            if (IsBridgeReachableSync())
            {
                message = "Puente listo en :" + BridgePublicPort + ".";
                return true;
            }

            if (bridgeProcess != null)
            {
                try
                {
                    if (bridgeProcess.HasExited)
                    {
                        message =
                            "El puente terminó antes de abrir el puerto "
                            + BridgePublicPort
                            + ". Revisa los logs (llama-server.exe, DLL Vulkan, GGUF).";
                        return false;
                    }
                }
                catch
                {
                }
            }

            Thread.Sleep(500);
        }

        message =
            "El puente aún no responde en :"
            + BridgePublicPort
            + " tras "
            + (int)timeoutSeconds
            + " s. Si el GGUF es grande, puede tardar más; el backend reintentará el warmup.";
        return false;
    }

    private static void OnBridgeOutput(object sender, DataReceivedEventArgs e)
    {
        if (string.IsNullOrWhiteSpace(e.Data))
        {
            return;
        }

        var type = PyGenesisBackendLogClassifier.ClassifyLine(e.Data);
        PyGenesisBackendLogStore.AddLine("[bridge] " + e.Data, type);
    }

    public static bool IsBridgeReachableSync()
    {
        string url = "http://127.0.0.1:" + BridgePublicPort + "/health";
        using (var request = UnityWebRequest.Get(url))
        {
            request.timeout = 2;
            var op = request.SendWebRequest();
            while (!op.isDone)
            {
                // Espera síncrona breve al pulsar Start Backend.
            }

#if UNITY_2020_1_OR_NEWER
            if (request.result != UnityWebRequest.Result.Success)
#else
            if (request.isNetworkError || request.isHttpError)
#endif
            {
                return false;
            }

            return request.responseCode > 0 && request.responseCode < 500;
        }
    }
}
