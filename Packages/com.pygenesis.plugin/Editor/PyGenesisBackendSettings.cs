/// <summary>
/// Punto único para host, puerto y rutas del backend Python.
/// </summary>
public static class PyGenesisBackendSettings
{
    public const string Host = "127.0.0.1";
    public const int Port = 8765;

    /// <summary>
    /// Segundos para POST largos de análisis. Debe ser ≥ timeout del backend
    /// (<c>PYGENESIS_LLM_TIMEOUT_SECONDS</c> en .env; p. ej. 600) más un margen.
    /// </summary>
    public const int RequestTimeoutSeconds = 630;

    /// <summary>
    /// Timeout para <c>/chat/stream</c>. <b>0 = sin límite en Unity</b> (la API lo ignora):
    /// respuestas largas en Ollama pueden tardar muchos minutos; el tope real lo ponen
    /// <c>PYGENESIS_LLM_TIMEOUT_SECONDS</c> (backend, p. ej. 600) y <c>PYGENESIS_LLM_CHAT_MAX_TOKENS</c>.
    /// </summary>
    public const int ChatStreamTimeoutSeconds = 0;

    public static string BaseUrl => $"http://{Host}:{Port}";
    public static string HealthUrl => $"{BaseUrl}/health";
    public static string AnalyzeSelectionUrl => $"{BaseUrl}/analyze-selection";
    public static string ChatCapabilitiesUrl => $"{BaseUrl}/chat/capabilities";
    public static string ChatUrl => $"{BaseUrl}/chat";
    public static string ChatStreamUrl => $"{BaseUrl}/chat/stream";

    public static string BackendStartBatPath => PyGenesisRuntimePaths.BackendStartBatPath;
}
