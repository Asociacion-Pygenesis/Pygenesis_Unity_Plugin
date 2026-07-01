/// <summary>
/// Clasifica líneas de log del proceso backend (stdout/stderr) para la UI.
/// </summary>
public static class PyGenesisBackendLogClassifier
{
    public static PyGenesisBackendLogStore.LogType ClassifyLine(string line)
    {
        if (string.IsNullOrWhiteSpace(line))
            return PyGenesisBackendLogStore.LogType.Info;

        string lower = line.ToLowerInvariant();

        // Uvicorn / FastAPI info (aunque venga por stderr)
        if (
            lower.Contains("info:") ||
            lower.Contains("uvicorn running on") ||
            lower.Contains("application startup complete") ||
            lower.Contains("started server process") ||
            lower.Contains("waiting for application startup") ||
            lower.Contains("waiting for requests") ||
            lower.Contains("shutting down") ||
            lower.Contains("finished server process")
        )
        {
            return PyGenesisBackendLogStore.LogType.Info;
        }

        if (
            lower.Contains("warning") ||
            lower.Contains("warn")
        )
        {
            return PyGenesisBackendLogStore.LogType.Warning;
        }

        if (
            lower.Contains("error") ||
            lower.Contains("exception") ||
            lower.Contains("traceback") ||
            lower.Contains("failed")
        )
        {
            return PyGenesisBackendLogStore.LogType.Error;
        }

        return PyGenesisBackendLogStore.LogType.Info;
    }
}
