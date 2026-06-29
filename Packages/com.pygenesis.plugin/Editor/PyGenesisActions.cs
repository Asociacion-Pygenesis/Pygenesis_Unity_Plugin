using UnityEditor;
using UnityEngine;
using System.Collections.Generic;
using Newtonsoft.Json;

public static class PyGenesisActions
{
    // Tipo del handler: recibe el GO y los params del backend
    public delegate void ActionHandler(GameObject go, Dictionary<string, object> parms);

    // Catálogo: id de acción → handler
    public static readonly Dictionary<string, ActionHandler> Catalog = new()
    {
        // ── Ya existentes ──────────────────────────────────────────
        { "rename_object",        RenameObject        },
        { "set_scale",            SetScale            },
        { "set_position",         SetPosition         },

        // ── Nuevos: componentes ────────────────────────────────────
        { "add_component",        AddComponent        },
        { "remove_component",     RemoveComponent     },

        // ── Nuevos: jerarquía ──────────────────────────────────────
        { "set_parent",           SetParent           },
        { "create_child",         CreateChild         },
        { "create_empty_parent",  CreateEmptyParent   },

        // ── Nuevos: prefabs ────────────────────────────────────────
        { "create_prefab",        CreatePrefab        },
        { "unpack_prefab",        UnpackPrefab        },

        // ── Nuevos: estado ─────────────────────────────────────────
        { "set_active",           SetActive           },
        { "set_static",           SetStatic           },
        { "set_tag",              SetTag              },
        { "set_layer",            SetLayer            },

        // ── Nuevos: material/renderer ──────────────────────────────
        { "set_material_color",   SetMaterialColor    },
    };

    // ── Punto de entrada ───────────────────────────────────────────
    public static void Execute(string actionId, GameObject go,
                               Dictionary<string, object> parms)
    {
        if (!Catalog.TryGetValue(actionId, out var handler))
        {
            Debug.LogWarning($"[PyGenesis] Acción desconocida: '{actionId}'");
            return;
        }
        handler(go, parms ?? new Dictionary<string, object>());
    }

    /// <summary>Aplica una sugerencia del análisis (id + params_json) al GameObject.</summary>
    public static void ExecuteAction(PyGenesisSuggestedAction suggestion, GameObject go)
    {
        if (suggestion == null || go == null)
            return;

        var actionId = suggestion.action;
        if (string.IsNullOrWhiteSpace(actionId))
        {
            Debug.LogWarning("[PyGenesis] La sugerencia no tiene action id.");
            return;
        }

        Dictionary<string, object> parms = new();
        if (!string.IsNullOrWhiteSpace(suggestion.params_json))
        {
            try
            {
                parms = JsonConvert.DeserializeObject<Dictionary<string, object>>(suggestion.params_json)
                    ?? new Dictionary<string, object>();
            }
            catch (System.Exception ex)
            {
                Debug.LogWarning($"[PyGenesis] params_json inválido: {ex.Message}");
            }
        }

        Execute(actionId, go, parms);
    }

    // ══════════════════════════════════════════════════════════════
    // HELPERS
    // ══════════════════════════════════════════════════════════════

    static string S(Dictionary<string, object> p, string key, string def = "")
        => p.TryGetValue(key, out var v) ? v?.ToString() ?? def : def;

    static float F(Dictionary<string, object> p, string key, float def = 0f)
        => p.TryGetValue(key, out var v) && float.TryParse(v?.ToString(),
           System.Globalization.NumberStyles.Float,
           System.Globalization.CultureInfo.InvariantCulture, out var r) ? r : def;

    static bool B(Dictionary<string, object> p, string key, bool def = false)
        => p.TryGetValue(key, out var v) && v is bool b ? b
           : bool.TryParse(v?.ToString(), out var r) ? r : def;

    // ══════════════════════════════════════════════════════════════
    // ACCIONES — COMPONENTES
    // ══════════════════════════════════════════════════════════════

    static void AddComponent(GameObject go, Dictionary<string, object> p)
    {
        var typeName = S(p, "component");
        var type = ResolveComponentType(typeName);
        if (type == null)
        {
            Debug.LogWarning($"[PyGenesis] Componente no reconocido: '{typeName}'");
            return;
        }
        if (go.GetComponent(type) != null)
        {
            Debug.Log($"[PyGenesis] '{typeName}' ya existe en {go.name}");
            return;
        }
        Undo.AddComponent(go, type);
        Debug.Log($"[PyGenesis] Añadido {typeName} a {go.name}");
    }

    static void RemoveComponent(GameObject go, Dictionary<string, object> p)
    {
        var typeName = S(p, "component");
        var type = ResolveComponentType(typeName);
        if (type == null) return;

        var comp = go.GetComponent(type);
        if (comp == null)
        {
            Debug.LogWarning($"[PyGenesis] No existe '{typeName}' en {go.name}");
            return;
        }
        Undo.DestroyObjectImmediate(comp);
    }

    // Resuelve nombre de tipo (corto o completo)
    static System.Type ResolveComponentType(string name)
    {
        // Primero busca en UnityEngine directamente
        var t = System.Type.GetType($"UnityEngine.{name}, UnityEngine");
        if (t != null) return t;

        // Busca en todos los assemblies cargados
        foreach (var asm in System.AppDomain.CurrentDomain.GetAssemblies())
        {
            t = asm.GetType(name, false, true);
            if (t != null && t.IsSubclassOf(typeof(Component))) return t;
        }
        return null;
    }

    // ══════════════════════════════════════════════════════════════
    // ACCIONES — JERARQUÍA
    // ══════════════════════════════════════════════════════════════

    static void SetParent(GameObject go, Dictionary<string, object> p)
    {
        var parentName = S(p, "parent_name");
        var parent = GameObject.Find(parentName);
        if (parent == null)
        {
            Debug.LogWarning($"[PyGenesis] No se encontró padre: '{parentName}'");
            return;
        }
        Undo.SetTransformParent(go.transform, parent.transform, $"Set parent of {go.name}");
    }

    static void CreateChild(GameObject go, Dictionary<string, object> p)
    {
        var childName = S(p, "name", "New Child");
        var child = new GameObject(childName);
        Undo.RegisterCreatedObjectUndo(child, $"Create child {childName}");
        Undo.SetTransformParent(child.transform, go.transform, "Parent new child");
        child.transform.localPosition = Vector3.zero;
    }

    static void CreateEmptyParent(GameObject go, Dictionary<string, object> p)
    {
        var parentName = S(p, "name", go.name + "_Parent");
        var parent = new GameObject(parentName);
        Undo.RegisterCreatedObjectUndo(parent, "Create empty parent");

        // El nuevo padre toma la posición del hijo
        parent.transform.position = go.transform.position;
        parent.transform.SetParent(go.transform.parent);

        Undo.SetTransformParent(go.transform, parent.transform, "Reparent under new parent");
    }

    // ══════════════════════════════════════════════════════════════
    // ACCIONES — PREFABS
    // ══════════════════════════════════════════════════════════════

    static void CreatePrefab(GameObject go, Dictionary<string, object> p)
    {
        var folder = S(p, "folder", "Assets/Prefabs");
        var fileName = S(p, "file_name", go.name + ".prefab");

        // Asegura que existe la carpeta
        if (!AssetDatabase.IsValidFolder(folder))
        {
            var parts = folder.Split('/');
            var current = parts[0];
            for (int i = 1; i < parts.Length; i++)
            {
                var next = current + "/" + parts[i];
                if (!AssetDatabase.IsValidFolder(next))
                    AssetDatabase.CreateFolder(current, parts[i]);
                current = next;
            }
        }

        var path = $"{folder}/{fileName}";
        PrefabUtility.SaveAsPrefabAssetAndConnect(go, path, InteractionMode.UserAction);
        AssetDatabase.Refresh();
        Debug.Log($"[PyGenesis] Prefab creado en {path}");
    }

    static void UnpackPrefab(GameObject go, Dictionary<string, object> p)
    {
        if (!PrefabUtility.IsPartOfPrefabInstance(go))
        {
            Debug.LogWarning($"[PyGenesis] {go.name} no es una instancia de prefab");
            return;
        }
        Undo.RecordObject(go, "Unpack Prefab");
        PrefabUtility.UnpackPrefabInstance(go,
            PrefabUnpackMode.Completely, InteractionMode.UserAction);
    }

    // ══════════════════════════════════════════════════════════════
    // ACCIONES — ESTADO / FLAGS
    // ══════════════════════════════════════════════════════════════

    static void SetActive(GameObject go, Dictionary<string, object> p)
    {
        var active = B(p, "active", true);
        Undo.RecordObject(go, $"Set active {active}");
        go.SetActive(active);
    }

    static void SetStatic(GameObject go, Dictionary<string, object> p)
    {
        var isStatic = B(p, "static", true);
        Undo.RecordObject(go, "Set static");
        go.isStatic = isStatic;

        // Opcionalmente propaga a hijos
        if (B(p, "recursive", false))
            foreach (Transform child in go.GetComponentsInChildren<Transform>(true))
                child.gameObject.isStatic = isStatic;
    }

    static void SetTag(GameObject go, Dictionary<string, object> p)
    {
        var tag = S(p, "tag", "Untagged");
        Undo.RecordObject(go, "Set tag");
        go.tag = tag;
    }

    static void SetLayer(GameObject go, Dictionary<string, object> p)
    {
        var layerName = S(p, "layer");
        var layerId = LayerMask.NameToLayer(layerName);
        if (layerId < 0)
        {
            Debug.LogWarning($"[PyGenesis] Layer desconocido: '{layerName}'");
            return;
        }
        Undo.RecordObject(go, "Set layer");
        go.layer = layerId;

        if (B(p, "recursive", false))
            foreach (Transform child in go.GetComponentsInChildren<Transform>(true))
            {
                Undo.RecordObject(child.gameObject, "Set layer recursive");
                child.gameObject.layer = layerId;
            }
    }

    static void RenameObject(GameObject go, Dictionary<string, object> p)
    {
        Undo.RecordObject(go, "Rename");
        go.name = S(p, "name", go.name);
    }

    static void SetScale(GameObject go, Dictionary<string, object> p)
    {
        Undo.RecordObject(go.transform, "Set scale");
        go.transform.localScale = new Vector3(F(p, "x", 1), F(p, "y", 1), F(p, "z", 1));
    }

    static void SetPosition(GameObject go, Dictionary<string, object> p)
    {
        Undo.RecordObject(go.transform, "Set position");
        go.transform.localPosition = new Vector3(F(p, "x"), F(p, "y"), F(p, "z"));
    }

    // ══════════════════════════════════════════════════════════════
    // ACCIONES — MATERIAL / RENDERER
    // ══════════════════════════════════════════════════════════════

    static void SetMaterialColor(GameObject go, Dictionary<string, object> p)
    {
        var renderer = go.GetComponent<Renderer>();
        if (renderer == null)
        {
            Debug.LogWarning($"[PyGenesis] {go.name} no tiene Renderer");
            return;
        }
        var color = new Color(F(p, "r", 1f), F(p, "g", 1f), F(p, "b", 1f), F(p, "a", 1f));
        Undo.RecordObject(renderer.sharedMaterial, "Set material color");
        renderer.sharedMaterial.color = color;
    }
}