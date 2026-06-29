using System;
using System.Collections.Generic;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

public static class MiniJsonParser
{
    private class RawAnalyzeResponse
    {
        public string api_version;
        public string mode;
        public string message;
        public string summary;
        public List<RawSuggestedAction> suggestions;
        public List<RawDetectedIssue> issues;
    }

    private class RawSuggestedAction
    {
        public string label;
        public string action;
        public string description;
        public string rule_id;
        public object @params;
    }

    private class RawDetectedIssue
    {
        public string issue_id;
        public string title;
        public string message;
        public string severity;
    }

    public static PyGenesisAnalyzeResponse ParseAnalyzeResponse(string json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            throw new Exception("Empty JSON response.");
        }

        JObject root = JObject.Parse(json);
        var raw = root.ToObject<RawAnalyzeResponse>();

        if (raw == null)
        {
            throw new Exception("Could not parse backend response.");
        }

        var result = new PyGenesisAnalyzeResponse
        {
            api_version = raw.api_version ?? "",
            mode = raw.mode ?? "",
            message = raw.message ?? "",
            summary = raw.summary ?? "",
            issues = new List<PyGenesisDetectedIssue>(),
            suggestions = new List<PyGenesisSuggestedAction>()
        };

        result.object_insights_appendix = BuildObjectInsightsAppendix(root["metadata"] as JObject);

        if (raw.issues != null)
        {
            foreach (var issue in raw.issues)
            {
                result.issues.Add(new PyGenesisDetectedIssue
                {
                    issue_id = issue.issue_id ?? "",
                    title = issue.title ?? "",
                    message = issue.message ?? "",
                    severity = issue.severity ?? "info"
                });
            }
        }

        if (raw.suggestions != null)
        {
            foreach (var s in raw.suggestions)
            {
                result.suggestions.Add(new PyGenesisSuggestedAction
                {
                    label = s.label ?? "",
                    action = s.action ?? "",
                    description = s.description ?? "",
                    rule_id = s.rule_id ?? "",
                    params_json = s.@params != null
                        ? JsonConvert.SerializeObject(s.@params)
                        : "{}"
                });
            }
        }

        return result;
    }

    private static string BuildObjectInsightsAppendix(JObject metadata)
    {
        if (metadata == null)
        {
            return null;
        }

        JArray arr = metadata["object_insights"] as JArray;
        if (arr == null || arr.Count == 0)
        {
            return null;
        }

        const int maxLines = 32;
        var sb = new StringBuilder();
        sb.AppendLine("--- Notas por objeto (hierarchy_path) ---");
        int n = 0;
        foreach (JToken item in arr)
        {
            if (n >= maxLines)
            {
                sb.AppendLine("…");
                break;
            }

            if (item is not JObject o)
            {
                continue;
            }

            string path = o["hierarchy_path"]?.ToString() ?? "";
            string obs = o["observation"]?.ToString() ?? "";
            if (string.IsNullOrEmpty(path) && string.IsNullOrEmpty(obs))
            {
                continue;
            }

            sb.Append("• ");
            if (!string.IsNullOrEmpty(path))
            {
                sb.Append(path);
                sb.Append(": ");
            }

            sb.AppendLine(obs);
            n++;
        }

        return sb.Length > 0 ? sb.ToString().TrimEnd() : null;
    }
}