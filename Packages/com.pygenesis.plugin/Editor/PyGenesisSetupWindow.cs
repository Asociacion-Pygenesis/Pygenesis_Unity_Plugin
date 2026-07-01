using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

/// <summary>Ventana de comprobación e instalación del runtime PyGenesis.</summary>
public class PyGenesisSetupWindow : EditorWindow
{
    private Vector2 _scroll;
    private List<PyGenesisDependencyChecker.DependencyItem> _checks = new();
    private string _runtimeRootField = "";
    private string _statusLine = "";
    private readonly Dictionary<string, bool> _foldouts = new();

    [MenuItem("PyGenesis/Setup")]
    public static void ShowWindow()
    {
        GetWindow<PyGenesisSetupWindow>("PyGenesis Setup");
    }

    private void OnEnable()
    {
        _runtimeRootField = PyGenesisRuntimePaths.GetToolsRoot();
        RefreshChecks();
    }

    private void OnFocus()
    {
        RefreshChecks();
    }

    private void RefreshChecks()
    {
        PyGenesisBinaryManifest.InvalidateCache();
        _checks = new List<PyGenesisDependencyChecker.DependencyItem>(PyGenesisDependencyChecker.RunAllChecks());
        _runtimeRootField = PyGenesisRuntimePaths.GetToolsRoot();
        Repaint();
    }

    private void OnGUI()
    {
        GUILayout.Space(8);
        GUILayout.Label("PyGenesis Setup", EditorStyles.boldLabel);
        GUILayout.Space(4);

        DrawSummary();
        GUILayout.Space(8);
        DrawRuntimeRootSection();
        GUILayout.Space(8);
        DrawChecklist();
        GUILayout.Space(8);
        DrawActions();
        GUILayout.Space(6);

        if (!string.IsNullOrWhiteSpace(_statusLine))
        {
            EditorGUILayout.HelpBox(_statusLine, MessageType.Info);
        }
    }

    private void DrawSummary()
    {
        int critical = _checks.Count(c => c.Severity == PyGenesisDependencyChecker.DependencySeverity.Critical);
        int warnings = _checks.Count(c => c.Severity == PyGenesisDependencyChecker.DependencySeverity.Warning);

        GUIStyle style = new GUIStyle(EditorStyles.boldLabel);
        if (critical == 0)
        {
            style.normal.textColor = new Color(0.15f, 0.65f, 0.2f);
            EditorGUILayout.LabelField("● Listo para arrancar el backend", style);
            if (warnings > 0)
            {
                EditorGUILayout.LabelField(
                    warnings + " aviso(s) opcional(es) — puedes usar PyGenesis → Open Assistant.",
                    EditorStyles.wordWrappedLabel);
            }
            else
            {
                EditorGUILayout.LabelField(
                    "Todas las dependencias críticas están presentes.",
                    EditorStyles.wordWrappedLabel);
            }
        }
        else
        {
            style.normal.textColor = new Color(0.85f, 0.55f, 0.15f);
            EditorGUILayout.LabelField("● Faltan " + critical + " dependencia(s) crítica(s)", style);
            EditorGUILayout.LabelField(
                PyGenesisDependencyChecker.GetSetupBannerSummary(),
                EditorStyles.wordWrappedLabel);
        }

        EditorGUILayout.LabelField(
            "Plataforma: Windows x64 · llama.cpp " + PyGenesisBinaryManifest.LlamaBuild + " (Vulkan)",
            EditorStyles.miniLabel);
    }

    private void DrawRuntimeRootSection()
    {
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("Runtime root", EditorStyles.boldLabel);

        EditorGUILayout.LabelField(
            "Carpeta con pygenesis_backend/ y pygenesis_inference/ (Tools/ del repo o %USERPROFILE%\\.pygenesis).",
            EditorStyles.wordWrappedLabel);

        EditorGUILayout.BeginHorizontal();
        _runtimeRootField = EditorGUILayout.TextField(_runtimeRootField);
        if (GUILayout.Button("Aplicar", GUILayout.Width(64)))
        {
            if (PyGenesisSetupActions.TryApplyToolsRoot(_runtimeRootField, out string msg))
            {
                SetStatus(msg);
                RefreshChecks();
            }
            else
            {
                EditorUtility.DisplayDialog("PyGenesis Setup", msg, "OK");
            }
        }
        EditorGUILayout.EndHorizontal();

        EditorGUILayout.BeginHorizontal();
        if (GUILayout.Button("Usar ~/.pygenesis"))
        {
            if (PyGenesisSetupActions.TryUseDefaultUserRuntime(out string msg))
            {
                SetStatus(msg);
                RefreshChecks();
            }
            else
            {
                EditorUtility.DisplayDialog("PyGenesis Setup", msg, "OK");
            }
        }

        if (GUILayout.Button("Examinar…"))
        {
            if (PyGenesisSetupActions.TryBrowseToolsRoot(out string msg))
            {
                SetStatus(msg);
                RefreshChecks();
            }
        }

        if (GUILayout.Button("Volver a comprobar"))
        {
            RefreshChecks();
            SetStatus("Comprobación actualizada.");
        }
        EditorGUILayout.EndHorizontal();

        EditorGUILayout.EndVertical();
    }

    private void DrawChecklist()
    {
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("Dependencias", EditorStyles.boldLabel);

        _scroll = EditorGUILayout.BeginScrollView(_scroll, GUILayout.MaxHeight(320));

        foreach (var check in _checks)
        {
            DrawCheckRow(check);
            GUILayout.Space(2);
        }

        EditorGUILayout.EndScrollView();
        EditorGUILayout.EndVertical();
    }

    private void DrawCheckRow(PyGenesisDependencyChecker.DependencyItem check)
    {
        EditorGUILayout.BeginHorizontal();

        GUIStyle iconStyle = new GUIStyle(EditorStyles.boldLabel);
        switch (check.Severity)
        {
            case PyGenesisDependencyChecker.DependencySeverity.Ok:
                iconStyle.normal.textColor = new Color(0.15f, 0.65f, 0.2f);
                GUILayout.Label("●", iconStyle, GUILayout.Width(14));
                break;
            case PyGenesisDependencyChecker.DependencySeverity.Warning:
                iconStyle.normal.textColor = new Color(0.85f, 0.6f, 0.15f);
                GUILayout.Label("●", iconStyle, GUILayout.Width(14));
                break;
            default:
                iconStyle.normal.textColor = new Color(0.85f, 0.25f, 0.25f);
                GUILayout.Label("●", iconStyle, GUILayout.Width(14));
                break;
        }

        string key = check.Id ?? check.Label;
        if (!_foldouts.ContainsKey(key))
        {
            _foldouts[key] = check.Severity != PyGenesisDependencyChecker.DependencySeverity.Ok;
        }

        _foldouts[key] = EditorGUILayout.Foldout(_foldouts[key], check.Label, true);

        EditorGUILayout.EndHorizontal();

        if (_foldouts[key] && !string.IsNullOrWhiteSpace(check.Detail))
        {
            EditorGUI.indentLevel++;
            EditorGUILayout.LabelField(check.Detail, EditorStyles.wordWrappedLabel);
            EditorGUI.indentLevel--;
        }
    }

    private void DrawActions()
    {
        EditorGUILayout.BeginVertical("box");
        GUILayout.Label("Acciones", EditorStyles.boldLabel);

        EditorGUILayout.BeginHorizontal();
        if (GUILayout.Button("Descargar binarios Vulkan (automático)", GUILayout.Height(26)))
        {
            if (PyGenesisSetupActions.TryRunLlamaBinariesInstall(out string msg))
            {
                SetStatus(msg);
            }
            else
            {
                EditorUtility.DisplayDialog("PyGenesis Setup", msg, "OK");
            }
        }

        if (GUILayout.Button("Instalar runtime (PowerShell)", GUILayout.Height(26)))
        {
            if (PyGenesisSetupActions.TryRunInstallScript(out string msg))
            {
                SetStatus(msg);
            }
            else
            {
                EditorUtility.DisplayDialog("PyGenesis Setup", msg, "OK");
            }
        }

        if (GUILayout.Button("Crear .env desde ejemplo", GUILayout.Height(26)))
        {
            if (PyGenesisSetupActions.TryCreateEnvFromExample(out string msg))
            {
                SetStatus(msg);
                RefreshChecks();
            }
            else
            {
                EditorUtility.DisplayDialog("PyGenesis Setup", msg, "OK");
            }
        }
        EditorGUILayout.EndHorizontal();

        EditorGUILayout.BeginHorizontal();
        if (GUILayout.Button("Abrir carpeta bin/", GUILayout.Height(24)))
        {
            string binDir = System.IO.Path.Combine(PyGenesisRuntimePaths.GetInferenceDataRoot(), "bin");
            PyGenesisSetupActions.OpenInFileManager(binDir);
        }

        if (GUILayout.Button("Abrir carpeta models/", GUILayout.Height(24)))
        {
            string modelsDir = System.IO.Path.Combine(PyGenesisRuntimePaths.GetInferenceDataRoot(), "models");
            PyGenesisSetupActions.OpenInFileManager(modelsDir);
        }

        if (GUILayout.Button("Abrir Open Assistant", GUILayout.Height(24)))
        {
            PyGenesisWindow.ShowWindow();
        }
        EditorGUILayout.EndHorizontal();

        EditorGUILayout.BeginHorizontal();
        if (GUILayout.Button("ZIP manual (navegador)", GUILayout.Height(24)))
        {
            string url = PyGenesisBinaryManifest.DownloadUrl;
            if (string.IsNullOrWhiteSpace(url))
            {
                PyGenesisSetupActions.OpenUrl("https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin/releases");
            }
            else
            {
                PyGenesisSetupActions.OpenUrl(url);
            }
            SetStatus("Descarga manual: extrae el ZIP en la carpeta bin/.");
        }

        if (GUILayout.Button("Modelo en Hugging Face", GUILayout.Height(24)))
        {
            PyGenesisSetupActions.OpenUrl("https://huggingface.co/SuNavar/Pygenesis-Unity");
        }

        if (GUILayout.Button("Guía INSTALL.md", GUILayout.Height(24)))
        {
            PyGenesisSetupActions.OpenUrl(
                "https://github.com/Asociacion-Pygenesis/Pygenesis_Unity_Plugin/blob/main/docs/INSTALL.md");
        }
        EditorGUILayout.EndHorizontal();

        EditorGUILayout.EndVertical();
    }

    private void SetStatus(string line)
    {
        _statusLine = line ?? "";
        Repaint();
    }
}
