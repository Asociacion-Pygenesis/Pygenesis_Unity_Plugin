using System.Diagnostics;
using System.Text.RegularExpressions;

/// <summary>
/// Windows: localizar PID con netstat/findstr y terminar con taskkill.
/// </summary>
public static class PyGenesisWindowsPortProcessKiller
{
    public static bool TryKillProcessOnPort(int port, out string message)
    {
        try
        {
            var findInfo = new ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = $"/C netstat -ano | findstr :{port}",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            using (var findProcess = Process.Start(findInfo))
            {
                if (findProcess == null)
                {
                    message = "Failed to inspect port usage.";
                    return false;
                }

                string output = findProcess.StandardOutput.ReadToEnd();
                string error = findProcess.StandardError.ReadToEnd();
                findProcess.WaitForExit();

                if (!string.IsNullOrWhiteSpace(error))
                {
                    message = "Error while inspecting port: " + error;
                    return false;
                }

                if (string.IsNullOrWhiteSpace(output))
                {
                    message = $"No process found using port {port}.";
                    return false;
                }

                string[] lines = output.Split(new[] { '\r', '\n' }, System.StringSplitOptions.RemoveEmptyEntries);

                foreach (string line in lines)
                {
                    string trimmed = line.Trim();
                    string[] parts = Regex.Split(trimmed, @"\s+");

                    if (parts.Length < 5)
                        continue;

                    string pidText = parts[parts.Length - 1];

                    if (int.TryParse(pidText, out int pid))
                    {
                        var killInfo = new ProcessStartInfo
                        {
                            FileName = "taskkill",
                            Arguments = $"/PID {pid} /T /F",
                            UseShellExecute = false,
                            CreateNoWindow = true
                        };

                        using (var killProcess = Process.Start(killInfo))
                        {
                            if (killProcess != null)
                            {
                                killProcess.WaitForExit(5000);
                            }
                        }

                        message = $"Killed process {pid} using port {port}.";
                        return true;
                    }
                }

                message = $"Could not resolve a PID for port {port}.";
                return false;
            }
        }
        catch (System.Exception ex)
        {
            message = "Failed to kill process using port: " + ex.Message;
            return false;
        }
    }
}
