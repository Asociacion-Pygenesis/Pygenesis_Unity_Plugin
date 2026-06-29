using System.Collections;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.Networking;

/// <summary>
/// HTTP para /chat/capabilities, /chat y /chat/stream (conversación con Pygenesis AI).
/// </summary>
public static class PyGenesisChatHttpClient
{
    public static void GetCapabilities(System.Action<bool, string> onDone)
    {
        EditorCoroutineRunner.StartEditorCoroutine(GetCapabilitiesRequest(onDone));
    }

    public static void SendChat(string requestJson, System.Action<bool, string> onDone)
    {
        EditorCoroutineRunner.StartEditorCoroutine(PostChatRequest(requestJson, onDone));
    }

    /// <summary>
    /// Envía el chat en streaming (POST /chat/stream). <paramref name="onDelta"/> recibe fragmentos
    /// de texto a medida que llegan; <paramref name="onComplete"/> se llama al terminar con el
    /// contenido final canónico y la metadata (o un error).
    /// </summary>
    public static void SendChatStream(
        string requestJson,
        System.Action<string> onDelta,
        System.Action<bool, string, JObject, string> onComplete)
    {
        EditorCoroutineRunner.StartEditorCoroutine(PostChatStreamRequest(requestJson, onDelta, onComplete));
    }

    private static IEnumerator GetCapabilitiesRequest(System.Action<bool, string> onDone)
    {
        using (UnityWebRequest request = UnityWebRequest.Get(PyGenesisBackendSettings.ChatCapabilitiesUrl))
        {
            var op = request.SendWebRequest();
            while (!op.isDone)
            {
                yield return null;
            }

            bool ok = request.result == UnityWebRequest.Result.Success && request.responseCode == 200;
            string text = request.downloadHandler != null ? request.downloadHandler.text : "";
            onDone?.Invoke(ok, text);
        }
    }

    private static IEnumerator PostChatRequest(string json, System.Action<bool, string> onDone)
    {
        string url = PyGenesisBackendSettings.ChatUrl;
        byte[] bodyRaw = Encoding.UTF8.GetBytes(json);

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json; charset=utf-8");
            request.timeout = PyGenesisBackendSettings.RequestTimeoutSeconds;

            var op = request.SendWebRequest();
            while (!op.isDone)
            {
                yield return null;
            }

            bool success = request.result == UnityWebRequest.Result.Success && request.responseCode == 200;
            string text = request.downloadHandler != null ? request.downloadHandler.text : "";

            if (!success)
            {
                text = FormatChatHttpError(request, url, text);
            }

            onDone?.Invoke(success, text);
        }
    }

    private static IEnumerator PostChatStreamRequest(
        string json,
        System.Action<string> onDelta,
        System.Action<bool, string, JObject, string> onComplete)
    {
        string url = PyGenesisBackendSettings.ChatStreamUrl;
        byte[] bodyRaw = Encoding.UTF8.GetBytes(json);

        string finalContent = null;
        JObject finalMeta = null;
        string errorDetail = null;

        System.Action<string> onLine = (line) =>
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                return;
            }

            JObject evt;
            try
            {
                evt = JObject.Parse(line);
            }
            catch (System.Exception)
            {
                return;
            }

            string type = evt["type"]?.Value<string>();
            if (type == "delta")
            {
                string text = evt["text"]?.Value<string>() ?? "";
                if (text.Length > 0)
                {
                    onDelta?.Invoke(text);
                }
            }
            else if (type == "done")
            {
                JToken contentTok = evt["content"];
                if (contentTok == null || contentTok.Type == JTokenType.Null)
                {
                    finalContent = null;
                }
                else
                {
                    finalContent = contentTok.Value<string>();
                }
                finalMeta = evt["metadata"] as JObject;
            }
            else if (type == "error")
            {
                errorDetail = evt["detail"]?.Value<string>() ?? "Unknown stream error";
            }
            else if (evt["detail"] != null)
            {
                // Cuerpo de error no-stream (p. ej. 503 del gate del backend: {"detail": "..."}).
                errorDetail = evt["detail"].Value<string>();
            }
        };

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            var streamHandler = new PyGenesisChatStreamDownloadHandler(onLine);
            request.downloadHandler = streamHandler;
            request.SetRequestHeader("Content-Type", "application/json; charset=utf-8");
            request.SetRequestHeader("Accept", "application/x-ndjson");
            request.timeout = PyGenesisBackendSettings.ChatStreamTimeoutSeconds;

            var op = request.SendWebRequest();
            while (!op.isDone)
            {
                yield return null;
            }

            bool transportOk = request.result == UnityWebRequest.Result.Success && request.responseCode == 200;

            if (!string.IsNullOrEmpty(errorDetail))
            {
                onComplete?.Invoke(false, null, null, errorDetail);
            }
            else if (!transportOk)
            {
                string body = streamHandler.RawText;
                onComplete?.Invoke(false, null, null, FormatChatHttpError(request, url, body));
            }
            else
            {
                onComplete?.Invoke(true, finalContent ?? "", finalMeta, null);
            }
        }
    }

    private static string FormatChatHttpError(UnityWebRequest request, string url, string body)
    {
        long code = request.responseCode;
        string unityErr = request.error ?? "";

        if (code == 0L)
        {
            return
                "No response from server (HTTP 0). Is the backend running on " + url + "? " + unityErr;
        }

        if (!string.IsNullOrEmpty(unityErr) &&
            unityErr.IndexOf("timeout", System.StringComparison.OrdinalIgnoreCase) >= 0)
        {
            return
                "Request timed out in the Unity plugin after " + PyGenesisBackendSettings.ChatStreamTimeoutSeconds +
                " seconds while streaming a long Ollama reply. Try a shorter question, lower " +
                "PYGENESIS_LLM_CHAT_MAX_TOKENS (e.g. 2048), or raise ChatStreamTimeoutSeconds.\n" +
                "HTTP " + code + " " + unityErr + "\n" + body;
        }

        return "HTTP " + code + " " + unityErr + "\n" + body;
    }
}
