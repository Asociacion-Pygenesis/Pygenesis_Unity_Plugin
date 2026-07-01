using System.Collections.Generic;
using System.Text;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>
/// Construye <see cref="PyGenesisAnalyzeRequest"/> para command <c>analyze_scene</c>
/// y <see cref="PyGenesisSceneSnapshotData"/> reutilizable por el chat.
/// </summary>
public static partial class PyGenesisAnalyzeRequestBuilder
{
    private const int MaxRootsListed = 50;
    private const int MaxObjectsCounted = 800;
    private const int MaxFlatSample = 60;
    private const int MaxChildNamesPreview = 8;
    private const int MaxFirstLevelChildrenPerRoot = 12;
    private const int MaxFlatWithSecondLevel = 28;
    private const int MaxChildrenPerFlatDetail = 10;
    private const int MaxLightsIndex = 40;
    private const int MaxCamerasIndex = 40;

    /// <summary>Instantánea de la escena activa (Analyze Scene, POST /chat, etc.).</summary>
    public static PyGenesisSceneSnapshotData BuildSceneSnapshotData()
    {
        var scene = EditorSceneManager.GetActiveScene();
        var snap = new PyGenesisSceneSnapshotData
        {
            note = "",
            scene_asset_path = scene.path ?? ""
        };

        if (!scene.IsValid() || !scene.isLoaded)
        {
            snap.note = "Active scene is invalid or not loaded.";
            return snap;
        }

        GameObject[] rootObjects = scene.GetRootGameObjects();
        snap.root_count = rootObjects.Length;

        int listed = 0;
        foreach (GameObject go in rootObjects)
        {
            if (listed >= MaxRootsListed)
            {
                break;
            }

            snap.roots.Add(BuildRootInfo(go));
            listed++;
        }

        var note = new StringBuilder();
        if (rootObjects.Length > MaxRootsListed)
        {
            note.Append("Roots list truncated to ").Append(MaxRootsListed).Append(". ");
        }

        snap.total_estimated = CountSceneObjectsApprox(scene, MaxObjectsCounted);
        if (snap.total_estimated >= MaxObjectsCounted)
        {
            note.Append("Object count capped at ").Append(MaxObjectsCounted).Append(" (BFS). ");
        }

        CollectFlatSample(scene, snap.flat_sample, MaxFlatSample, MaxFlatWithSecondLevel);
        if (snap.flat_sample.Count >= MaxFlatSample)
        {
            note.Append("flat_sample shows first ").Append(MaxFlatSample).Append(" objects in BFS order. ");
        }

        CollectLightsIndex(scene, snap.lights_index, MaxLightsIndex);
        if (snap.lights_index.Count >= MaxLightsIndex)
        {
            note.Append("lights_index capped at ").Append(MaxLightsIndex).Append(" (BFS); scene may have more lights. ");
        }

        CollectCamerasIndex(scene, snap.cameras_index, MaxCamerasIndex);
        if (snap.cameras_index.Count >= MaxCamerasIndex)
        {
            note.Append("cameras_index capped at ").Append(MaxCamerasIndex).Append(" (BFS); scene may have more cameras. ");
        }

        note.Append("direct_children_detail on first ").Append(MaxFlatWithSecondLevel).Append(" BFS objects; first_level_children per root (max ")
            .Append(MaxFirstLevelChildrenPerRoot).Append(" each). ");
        note.Append("light_inspector / camera_inspector on nodes with those components; lights_index and cameras_index list all found (capped). ");

        snap.note = note.ToString().Trim();
        if (string.IsNullOrEmpty(snap.note))
        {
            snap.note = "";
        }

        return snap;
    }

    public static PyGenesisAnalyzeRequest BuildFromScene()
    {
        var scene = EditorSceneManager.GetActiveScene();
        return new PyGenesisAnalyzeRequest
        {
            command = "analyze_scene",
            scene_name = scene.name,
            selection = null,
            scene_snapshot = BuildSceneSnapshotData()
        };
    }

    private static void CollectLightsIndex(Scene scene, List<PyGenesisSceneLightEntry> outList, int maxLights)
    {
        GameObject[] roots = scene.GetRootGameObjects();
        var queue = new Queue<GameObject>();
        foreach (GameObject r in roots)
        {
            queue.Enqueue(r);
        }

        while (queue.Count > 0)
        {
            GameObject go = queue.Dequeue();
            Light light = go.GetComponent<Light>();
            if (light != null && outList.Count < maxLights)
            {
                outList.Add(new PyGenesisSceneLightEntry
                {
                    hierarchy_path = GetHierarchyPath(go.transform),
                    name = go.name,
                    object_active = go.activeInHierarchy,
                    light = BuildLightInspectorFromComponent(light)
                });
            }

            Transform tr = go.transform;
            for (int i = 0; i < tr.childCount; i++)
            {
                queue.Enqueue(tr.GetChild(i).gameObject);
            }
        }
    }

    private static void CollectCamerasIndex(Scene scene, List<PyGenesisSceneCameraEntry> outList, int maxCameras)
    {
        GameObject[] roots = scene.GetRootGameObjects();
        var queue = new Queue<GameObject>();
        foreach (GameObject r in roots)
        {
            queue.Enqueue(r);
        }

        while (queue.Count > 0)
        {
            GameObject go = queue.Dequeue();
            Camera camera = go.GetComponent<Camera>();
            if (camera != null && outList.Count < maxCameras)
            {
                outList.Add(new PyGenesisSceneCameraEntry
                {
                    hierarchy_path = GetHierarchyPath(go.transform),
                    name = go.name,
                    object_active = go.activeInHierarchy,
                    camera = BuildCameraInspectorFromComponent(camera)
                });
            }

            Transform tr = go.transform;
            for (int i = 0; i < tr.childCount; i++)
            {
                queue.Enqueue(tr.GetChild(i).gameObject);
            }
        }
    }

    private static PyGenesisCameraInspectorInfo BuildCameraInspectorFromComponent(Camera camera)
    {
        return new PyGenesisCameraInspectorInfo
        {
            orthographic = camera.orthographic,
            orthographic_size = camera.orthographicSize,
            field_of_view = camera.fieldOfView,
            near_clip_plane = camera.nearClipPlane,
            far_clip_plane = camera.farClipPlane,
            depth = camera.depth,
            clear_flags = camera.clearFlags.ToString(),
            culling_mask_summary = SummarizeCullingMask(camera.cullingMask),
            enabled = camera.enabled,
            target_display = camera.targetDisplay
        };
    }

    private static PyGenesisCameraInspectorInfo BuildCameraInspectorIfPresent(GameObject go)
    {
        Camera camera = go.GetComponent<Camera>();
        return camera != null ? BuildCameraInspectorFromComponent(camera) : null;
    }

    private static PyGenesisLightInspectorInfo BuildLightInspectorFromComponent(Light light)
    {
        Color c = light.color;
        return new PyGenesisLightInspectorInfo
        {
            light_type = light.type.ToString(),
            color_rgb = new[] { c.r, c.g, c.b },
            intensity = light.intensity,
            shadow_type = light.shadows.ToString(),
            range = light.range,
            spot_angle = light.spotAngle,
            inner_spot_angle = light.innerSpotAngle,
            enabled = light.enabled,
            bake_type = light.lightmapBakeType.ToString(),
            culling_mask_summary = SummarizeCullingMask(light.cullingMask)
        };
    }

    private static PyGenesisLightInspectorInfo BuildLightInspectorIfPresent(GameObject go)
    {
        Light light = go.GetComponent<Light>();
        return light != null ? BuildLightInspectorFromComponent(light) : null;
    }

    private static string SummarizeCullingMask(int mask)
    {
        if (mask == 0)
        {
            return "Nothing";
        }

        if (mask == ~0)
        {
            return "Everything";
        }

        var names = new List<string>();
        for (int i = 0; i < 32 && names.Count < 8; i++)
        {
            if ((mask & (1 << i)) == 0)
            {
                continue;
            }

            string ln = LayerMask.LayerToName(i);
            names.Add(string.IsNullOrEmpty(ln) ? $"Layer{i}" : ln);
        }

        string s = string.Join(", ", names);
        int bits = 0;
        for (int i = 0; i < 32; i++)
        {
            if ((mask & (1 << i)) != 0)
            {
                bits++;
            }
        }

        if (bits > names.Count)
        {
            s += ", …";
        }

        return s;
    }

    private static PyGenesisSceneRootInfo BuildRootInfo(GameObject go)
    {
        bool hasLight = go.GetComponent<Light>() != null;
        bool hasCamera = go.GetComponent<Camera>() != null;
        var root = new PyGenesisSceneRootInfo
        {
            name = go.name,
            hierarchy_path = GetHierarchyPath(go.transform),
            active = go.activeSelf,
            tag = string.IsNullOrEmpty(go.tag) ? "" : go.tag,
            layer_name = LayerMask.LayerToName(go.layer),
            child_count = go.transform.childCount,
            has_collider = HasAnyCollider(go),
            has_renderer = go.GetComponent<Renderer>() != null,
            has_animator = go.GetComponent<Animator>() != null,
            has_rigidbody = go.GetComponent<Rigidbody>() != null || go.GetComponent<Rigidbody2D>() != null,
            has_camera = hasCamera,
            has_light = hasLight,
            is_static = go.isStatic,
            direct_children_preview = GetDirectChildrenPreview(go.transform, MaxChildNamesPreview)
        };
        root.first_level_children = BuildChildBriefList(go, MaxFirstLevelChildrenPerRoot);
        if (hasLight)
        {
            root.light_inspector = BuildLightInspectorIfPresent(go);
        }

        if (hasCamera)
        {
            root.camera_inspector = BuildCameraInspectorIfPresent(go);
        }

        return root;
    }

    private static PyGenesisSceneFlatObjectInfo BuildFlatInfo(GameObject go, bool includeDirectChildrenDetail)
    {
        bool hasLight = go.GetComponent<Light>() != null;
        bool hasCamera = go.GetComponent<Camera>() != null;
        var flat = new PyGenesisSceneFlatObjectInfo
        {
            hierarchy_path = GetHierarchyPath(go.transform),
            name = go.name,
            active = go.activeSelf,
            tag = string.IsNullOrEmpty(go.tag) ? "" : go.tag,
            layer_name = LayerMask.LayerToName(go.layer),
            has_collider = HasAnyCollider(go),
            has_renderer = go.GetComponent<Renderer>() != null,
            has_animator = go.GetComponent<Animator>() != null,
            has_rigidbody = go.GetComponent<Rigidbody>() != null || go.GetComponent<Rigidbody2D>() != null,
            has_camera = hasCamera,
            has_light = hasLight,
            is_static = go.isStatic
        };
        if (includeDirectChildrenDetail)
        {
            flat.direct_children_detail = BuildChildBriefList(go, MaxChildrenPerFlatDetail);
        }

        if (hasLight)
        {
            flat.light_inspector = BuildLightInspectorIfPresent(go);
        }

        if (hasCamera)
        {
            flat.camera_inspector = BuildCameraInspectorIfPresent(go);
        }

        return flat;
    }

    private static PyGenesisSceneChildBrief BuildChildBrief(GameObject go)
    {
        bool hasLight = go.GetComponent<Light>() != null;
        bool hasCamera = go.GetComponent<Camera>() != null;
        var brief = new PyGenesisSceneChildBrief
        {
            name = go.name,
            hierarchy_path = GetHierarchyPath(go.transform),
            active = go.activeSelf,
            tag = string.IsNullOrEmpty(go.tag) ? "" : go.tag,
            layer_name = LayerMask.LayerToName(go.layer),
            child_count = go.transform.childCount,
            has_collider = HasAnyCollider(go),
            has_renderer = go.GetComponent<Renderer>() != null,
            has_animator = go.GetComponent<Animator>() != null,
            has_rigidbody = go.GetComponent<Rigidbody>() != null || go.GetComponent<Rigidbody2D>() != null,
            has_camera = hasCamera,
            has_light = hasLight,
            is_static = go.isStatic
        };
        if (hasLight)
        {
            brief.light_inspector = BuildLightInspectorIfPresent(go);
        }

        if (hasCamera)
        {
            brief.camera_inspector = BuildCameraInspectorIfPresent(go);
        }

        return brief;
    }

    private static List<PyGenesisSceneChildBrief> BuildChildBriefList(GameObject parent, int maxChildren)
    {
        var list = new List<PyGenesisSceneChildBrief>();
        Transform t = parent.transform;
        for (int i = 0; i < t.childCount && list.Count < maxChildren; i++)
        {
            list.Add(BuildChildBrief(t.GetChild(i).gameObject));
        }

        return list;
    }

    private static bool HasAnyCollider(GameObject go)
    {
        return go.GetComponent<Collider>() != null || go.GetComponent<Collider2D>() != null;
    }

    private static string GetDirectChildrenPreview(Transform t, int maxNames)
    {
        if (t.childCount == 0)
        {
            return "";
        }

        var names = new List<string>();
        for (int i = 0; i < t.childCount && names.Count < maxNames; i++)
        {
            names.Add(t.GetChild(i).name);
        }

        string s = string.Join(", ", names);
        if (t.childCount > maxNames)
        {
            s += ", …";
        }

        return s;
    }

    private static void CollectFlatSample(
        Scene scene,
        List<PyGenesisSceneFlatObjectInfo> outList,
        int maxItems,
        int maxWithSecondLevel)
    {
        GameObject[] roots = scene.GetRootGameObjects();
        var queue = new Queue<GameObject>();
        foreach (GameObject r in roots)
        {
            queue.Enqueue(r);
        }

        int n = 0;
        while (queue.Count > 0 && n < maxItems)
        {
            GameObject go = queue.Dequeue();
            bool detail = n < maxWithSecondLevel;
            outList.Add(BuildFlatInfo(go, detail));
            n++;
            Transform tr = go.transform;
            for (int i = 0; i < tr.childCount; i++)
            {
                queue.Enqueue(tr.GetChild(i).gameObject);
            }
        }
    }

    private static string GetHierarchyPath(Transform t)
    {
        var parts = new List<string>();
        Transform cur = t;
        while (cur != null)
        {
            parts.Add(cur.name);
            cur = cur.parent;
        }

        parts.Reverse();
        return string.Join("/", parts);
    }

    private static int CountSceneObjectsApprox(Scene scene, int cap)
    {
        GameObject[] roots = scene.GetRootGameObjects();
        var queue = new Queue<GameObject>();
        foreach (GameObject r in roots)
        {
            queue.Enqueue(r);
        }

        int n = 0;
        while (queue.Count > 0 && n < cap)
        {
            GameObject go = queue.Dequeue();
            n++;
            Transform tr = go.transform;
            for (int i = 0; i < tr.childCount; i++)
            {
                queue.Enqueue(tr.GetChild(i).gameObject);
            }
        }

        return n;
    }
}
