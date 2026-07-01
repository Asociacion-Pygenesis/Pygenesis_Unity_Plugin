/// <summary>
/// Fachada opcional: delega en el control de proceso y en el cierre por puerto (Windows).
/// </summary>
public static class PyGenesisBackendLauncher
{
    public static bool IsBackendProcessRunning()
    {
        return PyGenesisBackendProcessController.IsRunning();
    }

    public static bool StartBackend(out string message)
    {
        return PyGenesisBackendProcessController.Start(out message);
    }

    public static bool StopBackend(out string message)
    {
        return PyGenesisBackendProcessController.Stop(out message);
    }

    public static bool KillProcessUsingPort(int port, out string message)
    {
        return PyGenesisWindowsPortProcessKiller.TryKillProcessOnPort(port, out message);
    }
}
