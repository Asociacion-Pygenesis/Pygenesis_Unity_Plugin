using Newtonsoft.Json.Linq;

/// <summary>Interpreta GET /health del backend para mensajes de UI.</summary>
public static class PyGenesisHealthStatus
{
    public struct ParsedHealth
    {
        public bool LlmReady;
        public string WarmupPreview;
        public string WarmupError;
        public string BridgeStatus;
        public string BridgeDetail;
    }

    public static ParsedHealth Parse(bool httpOk, string responseText)
    {
        var parsed = new ParsedHealth { LlmReady = httpOk };
        if (!httpOk)
        {
            return parsed;
        }

        parsed.LlmReady = true;
        try
        {
            var jo = JObject.Parse(responseText);
            var lr = jo["llm_ready"];
            if (lr != null && lr.Type == JTokenType.Boolean)
            {
                parsed.LlmReady = lr.Value<bool>();
            }

            parsed.WarmupPreview = jo["llm_warmup"]?.ToString()?.Trim() ?? "";
            parsed.WarmupError = jo["llm_warmup_error"]?.ToString()?.Trim() ?? "";

            var bridge = jo["inference_bridge"] as JObject;
            if (bridge != null)
            {
                parsed.BridgeStatus = bridge["status"]?.ToString()?.Trim() ?? "";
                parsed.BridgeDetail = bridge["detail"]?.ToString()?.Trim() ?? "";
            }
        }
        catch
        {
            parsed.LlmReady = true;
        }

        return parsed;
    }

    public static string FormatLlmNotReadyMessage(ParsedHealth health, int backendPort, bool unityManagesBackend)
    {
        string err = health.WarmupError ?? "";
        bool bridgeUnavailable = err.IndexOf("Puente de inferencia no disponible", System.StringComparison.OrdinalIgnoreCase) >= 0
            || err.IndexOf("10061", System.StringComparison.OrdinalIgnoreCase) >= 0
            || err.IndexOf("deneg", System.StringComparison.OrdinalIgnoreCase) >= 0
            || err.IndexOf("refused", System.StringComparison.OrdinalIgnoreCase) >= 0
            || err.IndexOf("ConnectError", System.StringComparison.OrdinalIgnoreCase) >= 0
            || (health.BridgeStatus == "error");

        if (bridgeUnavailable)
        {
            string hint = " Comprueba: bin/llama-server.exe + DLL (bin/README.txt), GGUF en models/, logs del puente.";
            if (unityManagesBackend)
            {
                return "Puente (:8081) no responde — conexión rechazada."
                    + hint
                    + " Pulsa Stop Backend → Start Backend. El backend reintenta cada ~15 s.";
            }

            return "Backend en :" + backendPort + "; puente (:8081) no disponible." + hint;
        }

        if (!string.IsNullOrWhiteSpace(err))
        {
            return "Backend activo; modelo LLM aún no listo. " + err;
        }

        return unityManagesBackend
            ? "Backend HTTP activo; esperando modelo LLM (carga inicial o reintento automático)…"
            : "Backend en :" + backendPort + "; modelo LLM aún no listo (llm_ready=false).";
    }

    public static string FormatWarmupPreview(ParsedHealth health)
    {
        if (!string.IsNullOrWhiteSpace(health.WarmupPreview))
        {
            return health.WarmupPreview;
        }

        if (!string.IsNullOrWhiteSpace(health.WarmupError))
        {
            return "Error carga LLM: " + health.WarmupError;
        }

        return "";
    }
}
