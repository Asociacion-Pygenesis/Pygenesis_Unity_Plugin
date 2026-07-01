using System.Collections.Generic;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

/// <summary>
/// Ventana conversacional con Pygenesis AI (POST /chat). Carga saludo desde GET /chat/capabilities.
/// </summary>
public class PyGenesisChatWindow : EditorWindow
{
    private enum LineRole
    {
        User,
        Assistant,
        System
    }

    private class ChatLine
    {
        public LineRole Role;
        public string Text;
    }

    private readonly List<ChatLine> _lines = new();
    private Vector2 _scroll;
    private string _input = "";
    private bool _waitingCapabilities;
    private bool _waitingReply;
    private bool _waitingAnalyze;

    /// <summary>Línea del asistente que se va rellenando mientras llega el streaming.</summary>
    private ChatLine _streamingLine;

    /// <summary>
    /// Abre el chat junto a <see cref="PyGenesisWindow"/> (no junto a Scene).
    /// Para dejarla flotante: arrastra la pestaña del chat fuera del dock, o usa el menú contextual de la pestaña → Float.
    /// </summary>
    [MenuItem("PyGenesis/Chat with Pygenesis AI")]
    public static void Open()
    {
        var win = GetWindow<PyGenesisChatWindow>(typeof(PyGenesisWindow));
        win.titleContent = new GUIContent("Pygenesis Chat");
        win.minSize = new Vector2(420, 320);
    }

    private void OnEnable()
    {
        _lines.Clear();
        _waitingCapabilities = true;
        _waitingReply = false;
        _input = "";

        PyGenesisChatHttpClient.GetCapabilities(OnCapabilitiesLoaded);
    }

    private void OnCapabilitiesLoaded(bool ok, string json)
    {
        _waitingCapabilities = false;

        if (!ok || string.IsNullOrWhiteSpace(json))
        {
            _lines.Add(new ChatLine
            {
                Role = LineRole.System,
                Text = "Could not load /chat/capabilities. Start the backend (Tools/pygenesis_backend) and check http://127.0.0.1:8765"
            });
        }
        else
        {
            try
            {
                var cap = JsonConvert.DeserializeObject<PyGenesisChatCapabilitiesDto>(json);
                if (cap != null)
                {
                    var sb = new System.Text.StringBuilder();
                    if (!string.IsNullOrWhiteSpace(cap.greeting))
                    {
                        sb.AppendLine(cap.greeting.Trim());
                        sb.AppendLine();
                    }

                    if (cap.capabilities != null)
                    {
                        sb.AppendLine("Capabilities:");
                        foreach (var c in cap.capabilities)
                        {
                            if (c == null)
                                continue;
                            sb.Append("• ");
                            sb.Append(string.IsNullOrWhiteSpace(c.title) ? c.id : c.title);
                            if (!string.IsNullOrWhiteSpace(c.description))
                            {
                                sb.Append(": ");
                                sb.Append(c.description);
                            }

                            sb.AppendLine();
                        }
                    }

                    _lines.Add(new ChatLine
                    {
                        Role = LineRole.Assistant,
                        Text = sb.ToString().Trim()
                    });
                }
            }
            catch (System.Exception ex)
            {
                _lines.Add(new ChatLine
                {
                    Role = LineRole.System,
                    Text = "Failed to parse capabilities: " + ex.Message
                });
            }
        }

        Repaint();
    }

    private void OnGUI()
    {
        GUILayout.Space(8);
        EditorGUILayout.LabelField("Pygenesis AI — Chat", EditorStyles.boldLabel);
        EditorGUILayout.HelpBox(
            "Conversation uses the backend POST /chat. Select any message text and press Ctrl+C to copy (e.g. code from the model).",
            MessageType.None);

        if (_waitingCapabilities)
        {
            EditorGUILayout.LabelField("Loading greeting…", EditorStyles.miniLabel);
        }

        _scroll = EditorGUILayout.BeginScrollView(_scroll);
        foreach (var line in _lines)
        {
            DrawChatLine(line);
        }

        EditorGUILayout.EndScrollView();

        EditorGUI.BeginDisabledGroup(_waitingCapabilities || _waitingReply || _waitingAnalyze);
        _input = EditorGUILayout.TextArea(_input, GUILayout.MinHeight(48));
        EditorGUILayout.BeginHorizontal();
        if (GUILayout.Button("Send", GUILayout.Height(26)))
        {
            SendUserMessage();
        }

        if (GUILayout.Button("Analyze selection", GUILayout.Height(26), GUILayout.Width(140)))
        {
            RequestAnalyzeSelection();
        }

        if (GUILayout.Button("Clear history", GUILayout.Height(26), GUILayout.Width(110)))
        {
            _lines.Clear();
        }

        EditorGUILayout.EndHorizontal();
        EditorGUI.EndDisabledGroup();

        if (_waitingReply)
        {
            EditorGUILayout.LabelField("Waiting for model…", EditorStyles.miniLabel);
        }

        if (_waitingAnalyze)
        {
            EditorGUILayout.LabelField("Analyzing selection…", EditorStyles.miniLabel);
        }
    }

    /// <summary>F4: mismo flujo que la ventana principal — POST /analyze-selection e inyectar resultado en el hilo.</summary>
    private void RequestAnalyzeSelection()
    {
        if (_waitingCapabilities || _waitingReply || _waitingAnalyze)
        {
            return;
        }

        _lines.Add(new ChatLine
        {
            Role = LineRole.User,
            Text = "[Analyze selection] Current editor selection"
        });
        _waitingAnalyze = true;
        Repaint();

        PyGenesisBackendHttpClient.AnalyzeSelection(OnAnalyzeSelectionDone, OnAnalyzeSelectionError);
    }

    private void OnAnalyzeSelectionDone(string rawJson)
    {
        _waitingAnalyze = false;

        try
        {
            var r = MiniJsonParser.ParseAnalyzeResponse(rawJson);
            var sb = new System.Text.StringBuilder();
            sb.AppendLine("Selection analysis (from backend):");
            sb.AppendLine(r.GetDisplayMessage());

            if (r.issues != null && r.issues.Count > 0)
            {
                sb.AppendLine();
                sb.AppendLine("Issues:");
                foreach (var issue in r.issues)
                {
                    if (issue == null)
                    {
                        continue;
                    }

                    string sev = string.IsNullOrEmpty(issue.severity) ? "info" : issue.severity;
                    string title = string.IsNullOrEmpty(issue.title) ? issue.issue_id : issue.title;
                    sb.Append("• [");
                    sb.Append(sev);
                    sb.Append("] ");
                    sb.Append(title);
                    if (!string.IsNullOrWhiteSpace(issue.message))
                    {
                        sb.Append(": ");
                        sb.Append(issue.message.Trim());
                    }

                    sb.AppendLine();
                }
            }

            if (r.suggestions != null && r.suggestions.Count > 0)
            {
                sb.AppendLine();
                sb.AppendLine("Suggestions:");
                foreach (var s in r.suggestions)
                {
                    if (s == null)
                    {
                        continue;
                    }

                    string label = string.IsNullOrWhiteSpace(s.label) ? s.action : s.label;
                    sb.Append("• ");
                    sb.AppendLine(label);
                    if (!string.IsNullOrWhiteSpace(s.description))
                    {
                        sb.Append("  ");
                        sb.AppendLine(s.description.Trim());
                    }
                }
            }

            _lines.Add(new ChatLine
            {
                Role = LineRole.Assistant,
                Text = sb.ToString().Trim()
            });
        }
        catch (System.Exception ex)
        {
            _lines.Add(new ChatLine
            {
                Role = LineRole.System,
                Text = "Could not parse analyze response: " + ex.Message + "\n" + rawJson
            });
        }

        Repaint();
    }

    private void OnAnalyzeSelectionError(string err)
    {
        _waitingAnalyze = false;
        _lines.Add(new ChatLine
        {
            Role = LineRole.System,
            Text = "Analyze selection failed:\n" + err
        });
        Repaint();
    }

    private static void DrawChatLine(ChatLine line)
    {
        string prefix = line.Role switch
        {
            LineRole.User => "[You]",
            LineRole.Assistant => "[Pygenesis AI]",
            _ => "[System]"
        };

        Color prev = GUI.contentColor;
        if (line.Role == LineRole.User)
        {
            GUI.contentColor = new Color(0.75f, 0.9f, 1f);
        }
        else if (line.Role == LineRole.Assistant)
        {
            GUI.contentColor = new Color(0.85f, 1f, 0.85f);
        }
        else
        {
            GUI.contentColor = new Color(1f, 0.85f, 0.6f);
        }

        EditorGUILayout.LabelField(prefix, EditorStyles.boldLabel);
        DrawSelectableMessageBody(line.Text ?? "");
        GUI.contentColor = prev;
        GUILayout.Space(8);
    }

    /// <summary>Texto del mensaje seleccionable (Ctrl+C) para copiar código u otras respuestas largas.</summary>
    private static void DrawSelectableMessageBody(string text)
    {
        var style = new GUIStyle(EditorStyles.textArea)
        {
            wordWrap = true,
            richText = false,
            padding = new RectOffset(4, 4, 4, 4),
        };
        style.normal.background = null;
        style.focused.background = null;
        style.hover.background = null;
        style.active.background = null;

        float width = EditorGUIUtility.currentViewWidth - 24f;
        if (width < 120f)
        {
            width = 120f;
        }

        float height = style.CalcHeight(new GUIContent(text), width);
        height = Mathf.Max(height, EditorGUIUtility.singleLineHeight);

        EditorGUILayout.SelectableLabel(text, style, GUILayout.Height(height));
    }

    private void SendUserMessage()
    {
        string trimmed = (_input ?? "").Trim();
        if (string.IsNullOrEmpty(trimmed))
        {
            return;
        }

        _input = "";
        _lines.Add(new ChatLine { Role = LineRole.User, Text = trimmed });
        _waitingReply = true;

        // Placeholder que se irá rellenando con los fragmentos del modelo.
        _streamingLine = new ChatLine { Role = LineRole.Assistant, Text = "" };
        _lines.Add(_streamingLine);
        Repaint();

        var req = BuildChatRequest();
        string json = JsonConvert.SerializeObject(req, new JsonSerializerSettings
        {
            NullValueHandling = NullValueHandling.Include
        });

        PyGenesisChatHttpClient.SendChatStream(json, OnChatStreamDelta, OnChatStreamComplete);
    }

    private void OnChatStreamDelta(string textChunk)
    {
        if (_streamingLine == null || string.IsNullOrEmpty(textChunk))
        {
            return;
        }

        _streamingLine.Text += textChunk;
        _scroll.y = float.MaxValue;
        Repaint();
    }

    private void OnChatStreamComplete(bool success, string finalContent, JObject metadata, string error)
    {
        _waitingReply = false;

        if (!success)
        {
            bool isTimeout = !string.IsNullOrEmpty(error) &&
                error.IndexOf("timeout", System.StringComparison.OrdinalIgnoreCase) >= 0;

            // Si no llegó a mostrarse nada, reutiliza la línea como mensaje de error; si ya había
            // texto parcial, conserva lo generado y avisa aparte.
            if (_streamingLine != null && string.IsNullOrEmpty(_streamingLine.Text))
            {
                _streamingLine.Role = LineRole.System;
                _streamingLine.Text = "Chat error:\n" + error;
            }
            else
            {
                if (_streamingLine != null && isTimeout)
                {
                    _streamingLine.Text += "\n\n[… reply incomplete — the connection timed out before Ollama finished]";
                }

                _lines.Add(new ChatLine { Role = LineRole.System, Text = "Chat error:\n" + error });
            }

            _streamingLine = null;
            Repaint();
            return;
        }

        // Passthrough (puente): el stream es vista previa; done.content es la respuesta canónica.
        bool passthrough = metadata != null &&
            metadata.TryGetValue("passthrough", out JToken passTok) &&
            passTok.Type == JTokenType.Boolean &&
            passTok.Value<bool>();

        if (_streamingLine != null)
        {
            string streamed = _streamingLine.Text ?? "";

            if (passthrough)
            {
                if (!string.IsNullOrWhiteSpace(finalContent))
                {
                    _streamingLine.Text = finalContent;
                }
                else if (string.IsNullOrEmpty(streamed) && metadata?["create_script"] == null)
                {
                    _streamingLine.Role = LineRole.System;
                    _streamingLine.Text = "Empty response.";
                }
            }
            else if (!string.IsNullOrWhiteSpace(finalContent))
            {
                bool repetitionTruncated = metadata != null &&
                    metadata.TryGetValue("repetition_truncated", out JToken repTok) &&
                    repTok.Type == JTokenType.Boolean &&
                    repTok.Value<bool>();

                bool finalLooksTruncated = finalContent.IndexOf("Código recortado", System.StringComparison.OrdinalIgnoreCase) >= 0
                    || finalContent.IndexOf("bucle detectado", System.StringComparison.OrdinalIgnoreCase) >= 0;
                bool streamedHasSourceTag = streamed.IndexOf("[Fuente", System.StringComparison.OrdinalIgnoreCase) >= 0;
                bool finalHasSourceTag = finalContent.IndexOf("[Fuente", System.StringComparison.OrdinalIgnoreCase) >= 0;
                bool preferStreamed = repetitionTruncated
                    || finalLooksTruncated
                    || (streamed.Length > finalContent.Length && !(streamedHasSourceTag && !finalHasSourceTag));
                _streamingLine.Text = preferStreamed ? streamed : finalContent;
            }
            else if (!string.IsNullOrEmpty(streamed))
            {
                // done sin content (passthrough sin flag legacy): conservar stream.
            }
            else if (metadata?["create_script"] == null)
            {
                _streamingLine.Role = LineRole.System;
                _streamingLine.Text = "Empty response.";
            }
            else
            {
                _lines.Remove(_streamingLine);
            }
        }

        if (!passthrough &&
            metadata != null &&
            PyGenesisChatScriptWriter.TryCreateFromChatMetadata(metadata, out string createdAssetPath) &&
            !string.IsNullOrEmpty(createdAssetPath))
        {
            _lines.Add(new ChatLine
            {
                Role = LineRole.System,
                Text = "[Plugin] Script creado e importado: " + createdAssetPath
            });
        }

        _streamingLine = null;
        Repaint();
    }

    private PyGenesisChatRequestDto BuildChatRequest()
    {
        var msgs = new List<PyGenesisChatMessageDto>();
        foreach (var line in _lines)
        {
            if (line.Role != LineRole.User && line.Role != LineRole.Assistant)
            {
                continue;
            }

            // No enviar el placeholder vacío del streaming (rompe el turno en Ollama).
            string content = line.Text ?? "";
            if (string.IsNullOrWhiteSpace(content))
            {
                continue;
            }

            msgs.Add(new PyGenesisChatMessageDto
            {
                role = line.Role == LineRole.User ? "user" : "assistant",
                content = content
            });
        }

        string scene = EditorSceneManager.GetActiveScene().name ?? "";

        return new PyGenesisChatRequestDto
        {
            messages = msgs,
            scene_name = scene,
            // El puente no usa snapshot de escena (system solo desde model_config.yaml).
            scene_snapshot = null
        };
    }

}
