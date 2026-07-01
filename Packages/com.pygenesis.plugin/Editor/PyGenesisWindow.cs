using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

public partial class PyGenesisWindow : EditorWindow
{
    private string backendMessage = "Press 'Analyze Selection' to begin.";
    private Vector2 scroll;
    private Vector2 logScroll;
    private List<PyGenesisSuggestedAction> actions = new();
    private List<PyGenesisDetectedIssue> analysisIssues = new();
    private List<PyGenesisBackendLogStore.LogEntry> cachedLogs = new();

    private bool isLoading = false;

    private GameObject lastAnalyzedObject = null;
    private string lastAnalyzedObjectName = "";

    private bool backendOnline = false;
    private bool backendDetectedByHealth = false;
    private string backendStatusText = "Unknown";
    /// <summary>Extracto devuelto por el backend tras calentar el LLM (/health → llm_warmup).</summary>
    private string llmWarmupPreview = "";
    private bool isCheckingBackend = false;
    /// <summary>True si /health devolvió 200 y el backend declara <c>llm_ready</c> (o no envía el campo).</summary>
    private bool llmModelReady = true;
    private float _nextLlmReadyPollTime;

    private bool showInfoLogs = true;
    private bool showWarningLogs = true;
    private bool showErrorLogs = true;

    /// <summary>F3: si es true, al recibir health OK se abre la ventana de chat (tras Start Backend).</summary>
    private bool _openChatAfterBackendReady;

    [MenuItem("PyGenesis/Open Assistant")]
    public static void ShowWindow()
    {
        GetWindow<PyGenesisWindow>("PyGenesis");
    }

    private void OnEnable()
    {
        EditorApplication.update += OnEditorUpdate;
        CheckBackendStatus();
    }

    private void OnFocus()
    {
        Repaint();
    }

    private void OnDisable()
    {
        EditorApplication.update -= OnEditorUpdate;
    }

    private void OnEditorUpdate()
    {
        var latestLogs = PyGenesisBackendLogStore.GetEntriesSnapshot();
        bool logCountChanged = cachedLogs == null || latestLogs.Count != cachedLogs.Count;

        cachedLogs = latestLogs;

        if (backendDetectedByHealth && !backendOnline && !isCheckingBackend && !isLoading)
        {
            float now = (float)EditorApplication.timeSinceStartup;
            if (now >= _nextLlmReadyPollTime)
            {
                _nextLlmReadyPollTime = now + 2f;
                CheckBackendStatus();
            }
        }

        if (logCountChanged || isCheckingBackend || isLoading || (backendDetectedByHealth && !backendOnline))
        {
            Repaint();
        }
    }

    /// <summary>Interpreta <c>llm_ready</c>, <c>llm_warmup</c> y <c>llm_warmup_error</c> de GET /health.</summary>
    private PyGenesisHealthStatus.ParsedHealth ApplyHealthResponse(bool httpOk, string responseText)
    {
        var parsed = PyGenesisHealthStatus.Parse(httpOk, responseText);
        llmModelReady = parsed.LlmReady;
        llmWarmupPreview = PyGenesisHealthStatus.FormatWarmupPreview(parsed);
        return parsed;
    }

    private void CheckBackendStatus()
    {
        isCheckingBackend = true;
        backendStatusText = "Checking backend...";
        Repaint();

        PyGenesisBackendHttpClient.CheckBackendHealth((ok, responseText) =>
        {
            isCheckingBackend = false;

            bool processRunning = PyGenesisBackendLauncher.IsBackendProcessRunning();
            backendDetectedByHealth = ok;
            var health = ApplyHealthResponse(ok, responseText);
            backendOnline = ok && llmModelReady;

            if (ok && !llmModelReady)
            {
                _nextLlmReadyPollTime = (float)EditorApplication.timeSinceStartup + 2f;
            }

            int port = PyGenesisBackendSettings.Port;

            if (ok && processRunning && llmModelReady)
            {
                backendStatusText = "Backend is running and managed by Unity.";
            }
            else if (ok && processRunning && !llmModelReady)
            {
                backendStatusText = PyGenesisHealthStatus.FormatLlmNotReadyMessage(health, port, unityManagesBackend: true);
            }
            else if (ok && !processRunning && llmModelReady)
            {
                backendStatusText =
                    $"A backend is already running on port {port}, but it is not managed by Unity.";
            }
            else if (ok && !processRunning && !llmModelReady)
            {
                backendStatusText = PyGenesisHealthStatus.FormatLlmNotReadyMessage(health, port, unityManagesBackend: false);
            }
            else if (!ok && processRunning)
            {
                backendStatusText = "Backend process exists, but no health response was received.";
            }
            else
            {
                backendStatusText = "No response from backend.";
            }

            if (_openChatAfterBackendReady)
            {
                _openChatAfterBackendReady = false;
                if (ok && llmModelReady)
                {
                    PyGenesisChatWindow.Open();
                }
            }

            Repaint();
        });
    }

    private void StartBackend()
    {
        PyGenesisBackendHttpClient.CheckBackendHealth((ok, responseText) =>
        {
            int port = PyGenesisBackendSettings.Port;

            if (ok)
            {
                var health = ApplyHealthResponse(ok, responseText);
                backendDetectedByHealth = true;
                backendOnline = ok && llmModelReady;
                if (!llmModelReady)
                {
                    backendStatusText = PyGenesisHealthStatus.FormatLlmNotReadyMessage(health, port, unityManagesBackend: true);
                    _nextLlmReadyPollTime = (float)EditorApplication.timeSinceStartup + 2f;
                }
                else
                {
                    backendStatusText = $"A backend is already running on port {port}.";
                }

                Repaint();
                return;
            }

            bool started = PyGenesisBackendLauncher.StartBackend(out string message);
            backendStatusText = message;
            backendOnline = false;
            backendDetectedByHealth = false;
            llmModelReady = false;
            Repaint();

            if (started)
            {
                _openChatAfterBackendReady = true;
                EditorCoroutineRunner.StartEditorCoroutine(DelayedBackendStartupValidation(3.0f));
            }
        });
    }

    private void StopBackend()
    {
        bool stopped = PyGenesisBackendLauncher.StopBackend(out string message);
        backendStatusText = message;
        backendOnline = false;
        backendDetectedByHealth = false;
        llmModelReady = false;
        llmWarmupPreview = "";
        _nextLlmReadyPollTime = 0f;
        actions.Clear();
        analysisIssues.Clear();

        if (stopped)
        {
            backendMessage = "Backend stopped.";
        }

        Repaint();
        EditorCoroutineRunner.StartEditorCoroutine(DelayedBackendStartupValidation(1.0f));
    }

    private void ForceKillBackendPort()
    {
        bool killed = PyGenesisBackendLauncher.KillProcessUsingPort(PyGenesisBackendSettings.Port, out string message);
        backendStatusText = message;

        if (killed)
        {
            backendOnline = false;
            backendDetectedByHealth = false;
            llmModelReady = false;
            llmWarmupPreview = "";
            _nextLlmReadyPollTime = 0f;
            actions.Clear();
            analysisIssues.Clear();
            backendMessage = "External backend process was terminated.";
        }

        Repaint();
        EditorCoroutineRunner.StartEditorCoroutine(DelayedBackendStartupValidation(1.0f));
    }

    private System.Collections.IEnumerator DelayedBackendStartupValidation(float delaySeconds)
    {
        float startTime = (float)EditorApplication.timeSinceStartup;

        while ((float)EditorApplication.timeSinceStartup - startTime < delaySeconds)
        {
            yield return null;
        }

        CheckBackendStatus();

        if (!PyGenesisBackendLauncher.IsBackendProcessRunning() && !backendDetectedByHealth)
        {
            backendOnline = false;
            backendStatusText = "Backend process exited during startup. Check backend logs.";
            Repaint();
        }
    }

    private void ApplyActionToAnalyzedObject(PyGenesisSuggestedAction action)
    {
        if (lastAnalyzedObject == null)
        {
            Debug.LogWarning("PyGenesis: The analyzed object reference is missing or the object was destroyed.");
            return;
        }

        PyGenesisActions.ExecuteAction(action, lastAnalyzedObject);
    }

    private void HandleResponse(string rawJson)
    {
        isLoading = false;

        try
        {
            var parsed = MiniJsonParser.ParseAnalyzeResponse(rawJson);
            backendMessage = parsed.GetDisplayMessage();
            analysisIssues = parsed.issues ?? new List<PyGenesisDetectedIssue>();
            actions = parsed.suggestions ?? new List<PyGenesisSuggestedAction>();
            Repaint();
        }
        catch (System.Exception ex)
        {
            backendMessage = "Response parsing error: " + ex.Message;
            Repaint();
        }
    }

    private void HandleError(string error)
    {
        isLoading = false;
        backendMessage = "Backend error: " + error;
        analysisIssues.Clear();
        actions.Clear();
        backendOnline = false;
        backendDetectedByHealth = false;
        backendStatusText = "Backend request failed.";
        Repaint();
    }
}
