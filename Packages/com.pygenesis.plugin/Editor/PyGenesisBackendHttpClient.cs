using System.Collections;
using System.Text;
using Newtonsoft.Json;
using UnityEngine;
using UnityEngine.Networking;

/// <summary>
/// Peticiones HTTP al backend (health y analyze). Sin lógica de UI ni de proceso.
/// </summary>
public static class PyGenesisBackendHttpClient
{
    public static void CheckBackendHealth(System.Action<bool, string> onDone)
    {
        EditorCoroutineRunner.StartEditorCoroutine(GetHealthRequest(onDone));
    }

    public static void AnalyzeSelection(System.Action<string> onDone, System.Action<string> onError)
    {
        var requestData = PyGenesisAnalyzeRequestBuilder.BuildFromSelection();
        PostAnalyzeRequestData(requestData, onDone, onError);
    }

    /// <summary>Análisis de la escena activa (command analyze_scene + scene_snapshot).</summary>
    public static void AnalyzeScene(System.Action<string> onDone, System.Action<string> onError)
    {
        var requestData = PyGenesisAnalyzeRequestBuilder.BuildFromScene();
        PostAnalyzeRequestData(requestData, onDone, onError);
    }

    private static void PostAnalyzeRequestData(
        PyGenesisAnalyzeRequest requestData,
        System.Action<string> onDone,
        System.Action<string> onError)
    {
        string json = JsonConvert.SerializeObject(
            requestData,
            new JsonSerializerSettings
            {
                NullValueHandling = NullValueHandling.Include
            }
        );

        Debug.Log("PyGenesis request JSON: " + json);

        EditorCoroutineRunner.StartEditorCoroutine(PostAnalyzeRequest(json, onDone, onError));
    }

    private static IEnumerator GetHealthRequest(System.Action<bool, string> onDone)
    {
        using (UnityWebRequest request = UnityWebRequest.Get(PyGenesisBackendSettings.HealthUrl))
        {
            var operation = request.SendWebRequest();

            while (!operation.isDone)
            {
                yield return null;
            }

            bool ok = request.result == UnityWebRequest.Result.Success && request.responseCode == 200;
            string responseText = request.downloadHandler != null ? request.downloadHandler.text : "";

            Debug.Log("PyGenesis health responseCode: " + request.responseCode);
            Debug.Log("PyGenesis health result: " + request.result);
            Debug.Log("PyGenesis health response: " + responseText);

            onDone?.Invoke(ok, responseText);
        }
    }

    private static IEnumerator PostAnalyzeRequest(
        string json,
        System.Action<string> onDone,
        System.Action<string> onError)
    {
        string url = PyGenesisBackendSettings.AnalyzeSelectionUrl;
        Debug.Log("PyGenesis sending request to: " + url);
        Debug.Log("PyGenesis request JSON: " + json);

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            byte[] bodyRaw = Encoding.UTF8.GetBytes(json);

            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json; charset=utf-8");
            request.timeout = PyGenesisBackendSettings.RequestTimeoutSeconds;

            var operation = request.SendWebRequest();

            while (!operation.isDone)
            {
                yield return null;
            }

            Debug.Log("PyGenesis responseCode: " + request.responseCode);
            Debug.Log("PyGenesis result: " + request.result);
            Debug.Log("PyGenesis error: " + request.error);
            Debug.Log("PyGenesis raw response: " + request.downloadHandler.text);

            if (request.result == UnityWebRequest.Result.Success)
            {
                onDone?.Invoke(request.downloadHandler.text);
            }
            else
            {
                string fullError = FormatHttpError(request, url);
                Debug.LogError("PyGenesis backend error:\n" + fullError);
                onError?.Invoke(fullError);
            }
        }
    }

    /// <summary>
    /// HTTP 0 en Unity suele significar que no hubo respuesta TCP (backend parado, puerto incorrecto o firewall).
    /// </summary>
    private static string FormatHttpError(UnityWebRequest request, string url)
    {
        long code = request.responseCode;
        string unityErr = request.error ?? "";
        string body = request.downloadHandler != null ? request.downloadHandler.text : "";

        if (code == 0L)
        {
            return
                "No response from server (HTTP 0). The backend may not be listening yet, the port may be wrong, or a firewall blocked the connection.\n" +
                "URL: " + url + "\n" +
                "Unity: " + unityErr + "\n" +
                "Wait a few seconds after Start Backend, then use Check Backend.";
        }

        if (!string.IsNullOrEmpty(unityErr) &&
            unityErr.IndexOf("timeout", System.StringComparison.OrdinalIgnoreCase) >= 0)
        {
            return
                "Request timed out in the Unity plugin after " + PyGenesisBackendSettings.RequestTimeoutSeconds +
                " seconds. Analysis/chat may need longer on local Ollama — raise PYGENESIS_LLM_TIMEOUT_SECONDS " +
                "and RequestTimeoutSeconds together.\n" +
                "HTTP Error: " + code +
                "\nUnity Error: " + unityErr +
                "\nResponse: " + body;
        }

        return
            "HTTP Error: " + code +
            "\nUnity Error: " + unityErr +
            "\nResponse: " + body;
    }
}
