/// <summary>
/// Fachada opcional: delega en el builder de peticiones y en el cliente HTTP.
/// </summary>
public static class PyGenesisBridge
{
    public static PyGenesisAnalyzeRequest BuildRequestFromSelection()
    {
        return PyGenesisAnalyzeRequestBuilder.BuildFromSelection();
    }

    public static void AnalyzeSelection(System.Action<string> onDone, System.Action<string> onError)
    {
        PyGenesisBackendHttpClient.AnalyzeSelection(onDone, onError);
    }

    public static void CheckBackendHealth(System.Action<bool, string> onDone)
    {
        PyGenesisBackendHttpClient.CheckBackendHealth(onDone);
    }
}
