using System;
using System.Collections.Generic;

public static class PyGenesisBackendLogStore
{
    public enum LogType
    {
        Info,
        Warning,
        Error
    }

    [Serializable]
    public class LogEntry
    {
        public string timestamp;
        public string message;
        public LogType type;
    }

    private static readonly object LockObj = new object();
    private static readonly List<LogEntry> Entries = new List<LogEntry>();
    private const int MaxLines = 500;

    public static void AddLine(string line, LogType type = LogType.Info)
    {
        if (string.IsNullOrWhiteSpace(line))
            return;

        lock (LockObj)
        {
            Entries.Add(new LogEntry
            {
                timestamp = DateTime.Now.ToString("HH:mm:ss"),
                message = line,
                type = type
            });

            if (Entries.Count > MaxLines)
            {
                int excess = Entries.Count - MaxLines;
                Entries.RemoveRange(0, excess);
            }
        }
    }

    public static List<LogEntry> GetEntriesSnapshot()
    {
        lock (LockObj)
        {
            return new List<LogEntry>(Entries);
        }
    }

    public static string GetAllText()
    {
        lock (LockObj)
        {
            List<string> lines = new List<string>();

            foreach (var entry in Entries)
            {
                lines.Add($"[{entry.timestamp}] [{entry.type}] {entry.message}");
            }

            return string.Join("\n", lines);
        }
    }

    public static void Clear()
    {
        lock (LockObj)
        {
            Entries.Clear();
        }
    }
}