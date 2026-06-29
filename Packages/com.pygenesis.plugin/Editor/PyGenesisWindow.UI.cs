using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public partial class PyGenesisWindow
{
    private void OnGUI()
    {
        GUILayout.Space(10);
        GUILayout.Label("PyGenesis Assistant", EditorStyles.boldLabel);
        GUILayout.Space(6);

        DrawBackendSection();

        GUILayout.Space(10);
        DrawSelectionSection();

        GUILayout.Space(10);
        DrawAnalyzeButtonSection();

        GUILayout.Space(15);
        GUILayout.Label("Analysis", EditorStyles.boldLabel);

        scroll = EditorGUILayout.BeginScrollView(scroll, GUILayout.Height(220));
        EditorGUILayout.HelpBox(backendMessage, MessageType.Info);

        if (analysisIssues != null && analysisIssues.Count > 0)
        {
            GUILayout.Space(8);
            GUILayout.Label("Detected issues", EditorStyles.boldLabel);
            DrawDetectedIssuesList(analysisIssues);
        }

        if (actions.Count > 0)
        {
            GUILayout.Space(10);
            GUILayout.Label("Suggested Actions", EditorStyles.boldLabel);

            foreach (var action in actions)
            {
                DrawActionCard(action);
            }
        }

        EditorGUILayout.EndScrollView();

        GUILayout.Space(12);
        DrawLogsSection();
    }

    private static void DrawDetectedIssuesList(System.Collections.Generic.List<PyGenesisDetectedIssue> issues)
    {
        EditorGUILayout.BeginVertical("box");

        foreach (var issue in issues)
        {
            string line1 = string.IsNullOrEmpty(issue.title)
                ? $"[{issue.severity}] {issue.message}"
                : $"[{issue.severity}] {issue.title}";
            string line2 = string.IsNullOrEmpty(issue.title) ? "" : issue.message;

            var parts = new System.Collections.Generic.List<string>();
            parts.Add(line1);
            if (!string.IsNullOrWhiteSpace(line2))
                parts.Add(line2);
            if (!string.IsNullOrWhiteSpace(issue.issue_id))
                parts.Add("id: " + issue.issue_id);

            string boxText = string.Join("\n", parts);
            MessageType boxType = SeverityToHelpBoxMessageType(issue.severity);

            EditorGUILayout.HelpBox(boxText, boxType);
            GUILayout.Space(4);
        }

        EditorGUILayout.EndVertical();
    }

    /// <summary>
    /// Colores del editor: Error (rojo), Warning (ámbar), Info (azul/gris).
    /// </summary>
    private static MessageType SeverityToHelpBoxMessageType(string severity)
    {
        if (string.IsNullOrEmpty(severity))
            return MessageType.Info;

        switch (severity.ToLowerInvariant())
        {
            case "critical":
            case "high":
                return MessageType.Error;
            case "medium":
                return MessageType.Warning;
            case "low":
            case "info":
            default:
                return MessageType.Info;
        }
    }

    private void DrawBackendSection()
    {
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("Backend", EditorStyles.boldLabel);

        bool httpUp = backendDetectedByHealth;
        bool canWork = backendOnline;

        string statusText = isCheckingBackend
            ? "Comprobando…"
            : (canWork ? "En línea" : (httpUp ? "Esperando modelo LLM" : "Sin conexión"));

        GUIStyle statusStyle = new GUIStyle(EditorStyles.boldLabel);
        if (isCheckingBackend)
        {
            statusStyle.normal.textColor = new Color(0.85f, 0.6f, 0.15f);
        }
        else if (canWork)
        {
            statusStyle.normal.textColor = new Color(0.15f, 0.65f, 0.2f);
        }
        else if (httpUp)
        {
            statusStyle.normal.textColor = new Color(0.85f, 0.55f, 0.15f);
        }
        else
        {
            statusStyle.normal.textColor = new Color(0.8f, 0.2f, 0.2f);
        }

        EditorGUILayout.LabelField($"Estado: ● {statusText}", statusStyle);

        if (!string.IsNullOrWhiteSpace(backendStatusText))
        {
            EditorGUILayout.LabelField("Info", backendStatusText, EditorStyles.wordWrappedLabel);
        }

        if (!string.IsNullOrWhiteSpace(llmWarmupPreview))
        {
            GUILayout.Space(4);
            EditorGUILayout.HelpBox(
                "LLM (calentamiento al arrancar):\n" + llmWarmupPreview,
                MessageType.Info);
        }

        GUILayout.Space(6);

        EditorGUILayout.BeginHorizontal();

        GUI.enabled = !isCheckingBackend;
        if (GUILayout.Button("Check Backend", GUILayout.Height(24)))
        {
            CheckBackendStatus();
        }

        bool backendProcessRunning = PyGenesisBackendLauncher.IsBackendProcessRunning();

        string backendButtonLabel;
        bool canStopManagedBackend = false;
        bool canStartBackend = false;

        if (backendProcessRunning)
        {
            backendButtonLabel = "Stop Backend";
            canStopManagedBackend = true;
        }
        else if (backendDetectedByHealth)
        {
            backendButtonLabel = "Backend Running";
        }
        else
        {
            backendButtonLabel = "Start Backend";
            canStartBackend = true;
        }

        GUI.enabled = !isCheckingBackend && (canStopManagedBackend || canStartBackend);

        if (GUILayout.Button(backendButtonLabel, GUILayout.Height(24)))
        {
            if (canStopManagedBackend)
            {
                StopBackend();
            }
            else if (canStartBackend)
            {
                StartBackend();
            }
        }

        GUI.enabled = true;

        EditorGUILayout.EndHorizontal();

        GUILayout.Space(4);
        if (GUILayout.Button("Open conversational chat (Pygenesis AI)", GUILayout.Height(22)))
        {
            PyGenesisChatWindow.Open();
        }

        if (backendDetectedByHealth && !backendProcessRunning)
        {
            GUILayout.Space(4);

            if (GUILayout.Button($"Force Kill Port {PyGenesisBackendSettings.Port}", GUILayout.Height(24)))
            {
                ForceKillBackendPort();
            }
        }

        EditorGUILayout.EndVertical();
    }

    private void DrawSelectionSection()
    {
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("Selection", EditorStyles.boldLabel);

        GameObject selected = Selection.activeGameObject;
        EditorGUILayout.LabelField("Selected Object", selected ? selected.name : "None");

        if (!string.IsNullOrEmpty(lastAnalyzedObjectName))
        {
            EditorGUILayout.LabelField("Last Analyzed", lastAnalyzedObjectName);
        }

        EditorGUILayout.EndVertical();
    }

    private void DrawAnalyzeButtonSection()
    {
        GUI.enabled = !isLoading && backendOnline;

        EditorGUILayout.BeginHorizontal();
        if (GUILayout.Button(isLoading ? "Analyzing..." : "Analyze Selection", GUILayout.Height(32)))
        {
            isLoading = true;
            backendMessage = "Analyzing...";
            actions.Clear();
            analysisIssues.Clear();

            GameObject current = Selection.activeGameObject;
            lastAnalyzedObject = current;
            lastAnalyzedObjectName = current != null ? current.name : "None";

            Repaint();

            PyGenesisBackendHttpClient.AnalyzeSelection(
                onDone: HandleResponse,
                onError: HandleError
            );
        }

        if (GUILayout.Button(isLoading ? "…" : "Analyze Scene", GUILayout.Height(32), GUILayout.Width(130)))
        {
            isLoading = true;
            backendMessage = "Analyzing scene...";
            actions.Clear();
            analysisIssues.Clear();

            lastAnalyzedObject = null;
            lastAnalyzedObjectName = EditorSceneManager.GetActiveScene().name + " (scene)";

            Repaint();

            PyGenesisBackendHttpClient.AnalyzeScene(
                onDone: HandleResponse,
                onError: HandleError
            );
        }

        EditorGUILayout.EndHorizontal();

        GUI.enabled = true;

        if (!backendOnline)
        {
            EditorGUILayout.HelpBox("Backend is offline. Start it or check the connection before analyzing.", MessageType.Warning);
        }
    }

    private void DrawActionCard(PyGenesisSuggestedAction action)
    {
        EditorGUILayout.BeginVertical("box");

        EditorGUILayout.LabelField(action.label, EditorStyles.boldLabel);

        if (!string.IsNullOrWhiteSpace(action.description))
        {
            EditorGUILayout.LabelField(action.description, EditorStyles.wordWrappedLabel);
        }

        if (!string.IsNullOrWhiteSpace(action.rule_id))
        {
            EditorGUILayout.LabelField("Rule: " + action.rule_id, EditorStyles.miniLabel);
        }

        GUILayout.Space(4);

        GUI.enabled = backendOnline && lastAnalyzedObject != null;
        if (GUILayout.Button("Apply", GUILayout.Height(24)))
        {
            ApplyActionToAnalyzedObject(action);
        }
        GUI.enabled = true;

        EditorGUILayout.EndVertical();
    }

    private void DrawLogsSection()
    {
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("Backend Logs", EditorStyles.boldLabel);

        EditorGUILayout.BeginHorizontal();

        if (GUILayout.Button("Clear Logs", GUILayout.Height(22)))
        {
            PyGenesisBackendLogStore.Clear();
            cachedLogs = new List<PyGenesisBackendLogStore.LogEntry>();
        }

        if (GUILayout.Button("Copy Logs", GUILayout.Height(22)))
        {
            EditorGUIUtility.systemCopyBuffer = PyGenesisBackendLogStore.GetAllText();
        }

        EditorGUILayout.EndHorizontal();

        GUILayout.Space(4);

        EditorGUILayout.BeginHorizontal();
        showInfoLogs = GUILayout.Toggle(showInfoLogs, "Info", GUILayout.Width(60));
        showWarningLogs = GUILayout.Toggle(showWarningLogs, "Warning", GUILayout.Width(80));
        showErrorLogs = GUILayout.Toggle(showErrorLogs, "Error", GUILayout.Width(70));
        EditorGUILayout.EndHorizontal();

        logScroll = EditorGUILayout.BeginScrollView(logScroll, GUILayout.Height(220));

        if (cachedLogs == null || cachedLogs.Count == 0)
        {
            EditorGUILayout.LabelField("No backend logs yet.");
        }
        else
        {
            foreach (var entry in cachedLogs)
            {
                if (!ShouldShowLog(entry.type))
                    continue;

                DrawLogEntry(entry);
            }
        }

        EditorGUILayout.EndScrollView();
        EditorGUILayout.EndVertical();
    }

    private bool ShouldShowLog(PyGenesisBackendLogStore.LogType type)
    {
        switch (type)
        {
            case PyGenesisBackendLogStore.LogType.Info:
                return showInfoLogs;

            case PyGenesisBackendLogStore.LogType.Warning:
                return showWarningLogs;

            case PyGenesisBackendLogStore.LogType.Error:
                return showErrorLogs;

            default:
                return true;
        }
    }

    private void DrawLogEntry(PyGenesisBackendLogStore.LogEntry entry)
    {
        string prefix = $"[{entry.timestamp}] [{entry.type}] ";
        string fullText = prefix + entry.message;

        GUIStyle style = new GUIStyle(EditorStyles.textArea)
        {
            wordWrap = true,
            richText = false
        };

        Color previousColor = GUI.contentColor;

        switch (entry.type)
        {
            case PyGenesisBackendLogStore.LogType.Info:
                GUI.contentColor = new Color(0.85f, 0.85f, 0.85f);
                break;

            case PyGenesisBackendLogStore.LogType.Warning:
                GUI.contentColor = new Color(0.95f, 0.75f, 0.30f);
                break;

            case PyGenesisBackendLogStore.LogType.Error:
                GUI.contentColor = new Color(0.95f, 0.35f, 0.35f);
                break;
        }

        EditorGUILayout.SelectableLabel(fullText, style, GUILayout.MinHeight(18));

        GUI.contentColor = previousColor;
    }
}
