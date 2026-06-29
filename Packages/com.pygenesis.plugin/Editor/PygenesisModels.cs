using System;
using System.Collections.Generic;

[Serializable]
public class PyGenesisTransformData
{
    public float[] position;
    public float[] rotation;
    public float[] scale;
}

[Serializable]
public class PyGenesisSelectionData
{
    public string name;
    public string type;
    public bool has_collider;
    public bool has_renderer;
    public bool has_animator;
    public bool has_rigidbody;
    public PyGenesisTransformData transform;
}

/// <summary>Propiedades del componente <see cref="UnityEngine.Light"/> (inspector).</summary>
[Serializable]
public class PyGenesisLightInspectorInfo
{
    public string light_type;
    public float[] color_rgb;
    public float intensity;
    public string shadow_type;
    public float range;
    public float spot_angle;
    public float inner_spot_angle;
    public bool enabled;
    public string bake_type;
    public string culling_mask_summary;
}

[Serializable]
public class PyGenesisSceneLightEntry
{
    public string hierarchy_path;
    public string name;
    public bool object_active;
    public PyGenesisLightInspectorInfo light;
}

/// <summary>Propiedades del componente <see cref="UnityEngine.Camera"/> (inspector).</summary>
[Serializable]
public class PyGenesisCameraInspectorInfo
{
    public bool orthographic;
    public float orthographic_size;
    public float field_of_view;
    public float near_clip_plane;
    public float far_clip_plane;
    public float depth;
    public string clear_flags;
    public string culling_mask_summary;
    public bool enabled;
    public int target_display;
}

[Serializable]
public class PyGenesisSceneCameraEntry
{
    public string hierarchy_path;
    public string name;
    public bool object_active;
    public PyGenesisCameraInspectorInfo camera;
}

[Serializable]
public class PyGenesisSceneRootInfo
{
    public string name;
    public string hierarchy_path;
    public bool active;
    public string tag;
    public string layer_name;
    public int child_count;
    public bool has_collider;
    public bool has_renderer;
    public bool has_animator;
    public bool has_rigidbody;
    public bool has_camera;
    public bool has_light;
    public bool is_static;
    public string direct_children_preview;
    public System.Collections.Generic.List<PyGenesisSceneChildBrief> first_level_children = new();
    public PyGenesisLightInspectorInfo light_inspector;
    public PyGenesisCameraInspectorInfo camera_inspector;
}

[Serializable]
public class PyGenesisSceneChildBrief
{
    public string name;
    public string hierarchy_path;
    public bool active;
    public string tag;
    public string layer_name;
    public int child_count;
    public bool has_collider;
    public bool has_renderer;
    public bool has_animator;
    public bool has_rigidbody;
    public bool has_camera;
    public bool has_light;
    public bool is_static;
    public PyGenesisLightInspectorInfo light_inspector;
    public PyGenesisCameraInspectorInfo camera_inspector;
}

[Serializable]
public class PyGenesisSceneFlatObjectInfo
{
    public string hierarchy_path;
    public string name;
    public bool active;
    public string tag;
    public string layer_name;
    public bool has_collider;
    public bool has_renderer;
    public bool has_animator;
    public bool has_rigidbody;
    public bool has_camera;
    public bool has_light;
    public bool is_static;
    public System.Collections.Generic.List<PyGenesisSceneChildBrief> direct_children_detail = new();
    public PyGenesisLightInspectorInfo light_inspector;
    public PyGenesisCameraInspectorInfo camera_inspector;
}

[Serializable]
public class PyGenesisSceneSnapshotData
{
    public int root_count;
    public int total_estimated;
    public System.Collections.Generic.List<PyGenesisSceneRootInfo> roots = new();
    public System.Collections.Generic.List<PyGenesisSceneFlatObjectInfo> flat_sample = new();
    public System.Collections.Generic.List<PyGenesisSceneLightEntry> lights_index = new();
    public System.Collections.Generic.List<PyGenesisSceneCameraEntry> cameras_index = new();
    public string scene_asset_path;
    public string note = "";
}

[Serializable]
public class PyGenesisAnalyzeRequest
{
    public string command;
    public string scene_name;
    public PyGenesisSelectionData selection;
    public PyGenesisSceneSnapshotData scene_snapshot;
}

[Serializable]
public class PyGenesisSuggestedAction
{
    public string label;
    public string action;
    public string description;
    public string rule_id;
    public string params_json;
}

[Serializable]
public class PyGenesisAnalyzeResponse
{
    public string api_version;
    /// <summary>Origen del análisis: llm, rules, hybrid (según backend).</summary>
    public string mode;
    /// <summary>Texto legacy; el backend 4.x puede priorizar <see cref="summary"/>.</summary>
    public string message;
    /// <summary>Resumen principal del análisis (API 4.x). Si <see cref="message"/> viene vacío, la UI usa esto.</summary>
    public string summary;
    public List<PyGenesisDetectedIssue> issues = new();
    public List<PyGenesisSuggestedAction> suggestions = new();

    /// <summary>Texto extra desde metadata.object_insights (análisis por objeto); lo añade <see cref="GetDisplayMessage"/>.</summary>
    public string object_insights_appendix;

    /// <summary>Texto útil para mostrar: message si no está vacío; si no, summary; si no, fallback.</summary>
    public string GetDisplayMessage(string fallbackIfEmpty = "No analysis text returned.")
    {
        string modeTag = "";
        string mo = (mode ?? "").Trim().ToLowerInvariant();
        if (!string.IsNullOrEmpty(mo))
        {
            if (mo == "llm")
                modeTag = "[LLM] ";
            else if (mo == "rules")
                modeTag = "[Reglas] ";
            else if (mo == "hybrid")
                modeTag = "[Híbrido] ";
            else
                modeTag = "[" + mo + "] ";
        }

        string m = (message ?? "").Trim();
        string body;
        if (!string.IsNullOrEmpty(m))
        {
            body = m;
        }
        else
        {
            string s = (summary ?? "").Trim();
            body = !string.IsNullOrEmpty(s) ? s : fallbackIfEmpty;
        }

        string appendix = (object_insights_appendix ?? "").Trim();
        if (string.IsNullOrEmpty(appendix))
        {
            return modeTag + body;
        }

        return modeTag + body + "\n\n" + appendix;
    }
}

[Serializable]
public class PyGenesisDetectedIssue
{
    public string issue_id;
    public string title;
    public string message;
    public string severity;
}