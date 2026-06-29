using System.Diagnostics;
using System.IO;
using UnityEngine;
using Debug = UnityEngine.Debug;

/// <summary>
/// Arranca y detiene el proceso del backend Python gestionado por el editor.
/// </summary>
public static class PyGenesisBackendProcessController
{
    private static Process backendProcess;

    public static bool IsRunning()
    {
        return backendProcess != null && !backendProcess.HasExited;
    }

    public static bool Start(out string message)
    {
        try
        {
            if (IsRunning())
            {
                message = "Backend is already running.";
                Debug.Log("PyGenesis: " + message);
                return true;
            }

            string batPath = PyGenesisBackendSettings.BackendStartBatPath;

            if (!File.Exists(batPath))
            {
                message = "Backend start script not found: " + batPath;
                Debug.LogError("PyGenesis: " + message);
                return false;
            }

            PyGenesisBackendLogStore.Clear();

            if (!PyGenesisBridgeLauncher.TryEnsureBridgeRunning(out string bridgeMessage))
            {
                message = bridgeMessage;
                PyGenesisBackendLogStore.AddLine("[Unity] " + bridgeMessage, PyGenesisBackendLogStore.LogType.Error);
                Debug.LogError("PyGenesis: " + message);
                return false;
            }

            PyGenesisBackendLogStore.AddLine("[Unity] " + bridgeMessage, PyGenesisBackendLogStore.LogType.Info);

            const float bridgeWaitSeconds = 45f;
            if (!PyGenesisBridgeLauncher.WaitForBridgeReady(bridgeWaitSeconds, out string waitMessage))
            {
                PyGenesisBackendLogStore.AddLine("[Unity] " + waitMessage, PyGenesisBackendLogStore.LogType.Warning);
            }
            else
            {
                PyGenesisBackendLogStore.AddLine("[Unity] " + waitMessage, PyGenesisBackendLogStore.LogType.Info);
            }

            PyGenesisBackendLogStore.AddLine("[Unity] Starting backend...", PyGenesisBackendLogStore.LogType.Info);

            var processStartInfo = new ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = $"/C \"{batPath}\"",
                WorkingDirectory = Path.GetDirectoryName(batPath),
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };

            processStartInfo.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";

            backendProcess = new Process
            {
                StartInfo = processStartInfo,
                EnableRaisingEvents = true
            };

            backendProcess.OutputDataReceived += OnOutputDataReceived;
            backendProcess.ErrorDataReceived += OnErrorDataReceived;
            backendProcess.Exited += OnProcessExited;

            bool started = backendProcess.Start();

            if (!started)
            {
                message = "Failed to launch backend process.";
                Debug.LogError("PyGenesis: " + message);
                return false;
            }

            backendProcess.BeginOutputReadLine();
            backendProcess.BeginErrorReadLine();

            message = "Backend started.";
            Debug.Log("PyGenesis: " + message);
            return true;
        }
        catch (System.Exception ex)
        {
            message = "Failed to start backend: " + ex.Message;
            Debug.LogError("PyGenesis: " + message);
            return false;
        }
    }

    public static bool Stop(out string message)
    {
        try
        {
            if (!IsRunning())
            {
                backendProcess = null;
                message = "Backend is not running.";
                Debug.Log("PyGenesis: " + message);
                return false;
            }

            int pid = backendProcess.Id;

            var killInfo = new ProcessStartInfo
            {
                FileName = "taskkill",
                Arguments = $"/PID {pid} /T /F",
                CreateNoWindow = true,
                UseShellExecute = false
            };

            using (var killProcess = Process.Start(killInfo))
            {
                if (killProcess != null)
                {
                    killProcess.WaitForExit(5000);
                }
            }

            PyGenesisBackendLogStore.AddLine("[Unity] Backend stop requested.", PyGenesisBackendLogStore.LogType.Warning);

            try
            {
                backendProcess.Refresh();
            }
            catch
            {
            }

            backendProcess = null;
            message = "Backend stopped.";
            Debug.Log("PyGenesis: " + message);
            return true;
        }
        catch (System.Exception ex)
        {
            message = "Failed to stop backend: " + ex.Message;
            Debug.LogError("PyGenesis: " + message);
            return false;
        }
    }

    private static void OnOutputDataReceived(object sender, DataReceivedEventArgs e)
    {
        if (!string.IsNullOrWhiteSpace(e.Data))
        {
            var type = PyGenesisBackendLogClassifier.ClassifyLine(e.Data);
            PyGenesisBackendLogStore.AddLine(e.Data, type);
        }
    }

    private static void OnErrorDataReceived(object sender, DataReceivedEventArgs e)
    {
        if (!string.IsNullOrWhiteSpace(e.Data))
        {
            var type = PyGenesisBackendLogClassifier.ClassifyLine(e.Data);
            PyGenesisBackendLogStore.AddLine(e.Data, type);
        }
    }

    private static void OnProcessExited(object sender, System.EventArgs e)
    {
        PyGenesisBackendLogStore.AddLine("[Unity] Backend process exited.", PyGenesisBackendLogStore.LogType.Warning);
    }
}
