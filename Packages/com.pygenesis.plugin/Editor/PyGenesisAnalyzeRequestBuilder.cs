using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

/// <summary>
/// Construye el DTO de análisis a partir del estado del editor (selección y escena).
/// </summary>
public static partial class PyGenesisAnalyzeRequestBuilder
{
    public static PyGenesisAnalyzeRequest BuildFromSelection()
    {
        GameObject selected = Selection.activeGameObject;

        var request = new PyGenesisAnalyzeRequest
        {
            command = "analyze_selection",
            scene_name = EditorSceneManager.GetActiveScene().name,
            selection = null
        };

        if (selected == null)
        {
            Debug.Log("PyGenesis: No active selection. Sending request with selection = null.");
            return request;
        }

        Transform t = selected.transform;

        request.selection = new PyGenesisSelectionData
        {
            name = selected.name,
            type = selected.GetType().Name,
            has_collider = selected.GetComponent<Collider>() != null,
            has_renderer = selected.GetComponent<Renderer>() != null,
            has_animator = selected.GetComponent<Animator>() != null,
            has_rigidbody = selected.GetComponent<Rigidbody>() != null,
            transform = new PyGenesisTransformData
            {
                position = ToFloatArray(t.position),
                rotation = ToFloatArray(t.eulerAngles),
                scale = ToFloatArray(t.localScale)
            }
        };

        return request;
    }

    private static float[] ToFloatArray(Vector3 v)
    {
        return new[] { v.x, v.y, v.z };
    }
}
