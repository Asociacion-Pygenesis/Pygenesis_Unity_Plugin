using System.Collections;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

[InitializeOnLoad]
public static class EditorCoroutineRunner
{
    private static readonly List<IEnumerator> Coroutines = new();

    static EditorCoroutineRunner()
    {
        EditorApplication.update += Update;
    }

    public static void StartEditorCoroutine(IEnumerator coroutine)
    {
        if (coroutine == null)
        {
            Debug.LogWarning("EditorCoroutineRunner: Tried to start a null coroutine.");
            return;
        }

        Coroutines.Add(coroutine);
    }

    private static void Update()
    {
        for (int i = Coroutines.Count - 1; i >= 0; i--)
        {
            try
            {
                if (!Coroutines[i].MoveNext())
                {
                    Coroutines.RemoveAt(i);
                }
            }
            catch (System.Exception ex)
            {
                Debug.LogError("EditorCoroutineRunner exception: " + ex);
                Coroutines.RemoveAt(i);
            }
        }
    }
}