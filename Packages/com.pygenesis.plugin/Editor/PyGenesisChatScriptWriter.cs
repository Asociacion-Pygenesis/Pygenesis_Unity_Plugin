using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;
using Newtonsoft.Json.Linq;

/// <summary>
/// Crea un .cs bajo Assets/ a partir de metadata.create_script devuelta por POST /chat.
/// </summary>
public static class PyGenesisChatScriptWriter
{
    private const ImportAssetOptions kReimport =
        ImportAssetOptions.ForceUpdate | ImportAssetOptions.ForceSynchronousImport;

    /// <summary>
    /// Escribe el archivo, refresca la base de assets e importa. Solo rutas bajo Assets/ y terminadas en .cs.
    /// </summary>
    public static bool TryCreateFromChatMetadata(JObject metadata, out string message)
    {
        message = null;

        if (metadata == null)
        {
            return false;
        }

        JToken token = metadata["create_script"];
        if (token == null || token.Type != JTokenType.Object)
        {
            return false;
        }

        var jobj = (JObject)token;
        string assetPath = jobj.Value<string>("asset_path") ?? jobj.Value<string>("assetPath");
        string content = jobj.Value<string>("content");

        if (string.IsNullOrWhiteSpace(assetPath) || content == null)
        {
            message = "create_script incompleto (asset_path o content).";
            return false;
        }

        if (string.IsNullOrWhiteSpace(content))
        {
            message = "create_script con contenido vacío.";
            return false;
        }

        assetPath = assetPath.Trim().Replace("\\", "/");
        if (!assetPath.StartsWith("Assets/", System.StringComparison.Ordinal) || assetPath.Contains(".."))
        {
            message = "Ruta no permitida (solo bajo Assets/).";
            return false;
        }

        if (!assetPath.EndsWith(".cs", System.StringComparison.OrdinalIgnoreCase))
        {
            message = "Solo se pueden crear archivos .cs.";
            return false;
        }

        string relativeFromAssets = assetPath.Substring("Assets/".Length);
        string fullPath = Path.GetFullPath(Path.Combine(
            Application.dataPath,
            relativeFromAssets.Replace('/', Path.DirectorySeparatorChar)));

        string dir = Path.GetDirectoryName(fullPath);
        if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
        {
            Directory.CreateDirectory(dir);
        }

        try
        {
            File.WriteAllText(fullPath, content, new UTF8Encoding(false));
        }
        catch (System.Exception ex)
        {
            message = "Error al escribir archivo: " + ex.Message;
            Debug.LogError("[PyGenesis] " + message + "\n" + fullPath);
            return false;
        }

        if (!File.Exists(fullPath))
        {
            message = "El archivo no existe tras escribir: " + fullPath;
            Debug.LogError("[PyGenesis] " + message);
            return false;
        }

        string pathForDb = assetPath;
        Debug.Log("[PyGenesis] Script escrito en disco: " + fullPath);

        // ImportAsset sobre un fichero recién creado a menudo no hace nada hasta Refresh.
        // delayCall: asegura ejecución en el siguiente tick del editor (p. ej. tras corrutina HTTP).
        EditorApplication.delayCall += () => ImportWrittenScript(pathForDb, fullPath);

        message = assetPath;
        return true;
    }

    private static void ImportWrittenScript(string assetPath, string fullPathOnDisk)
    {
        try
        {
            AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate);
            AssetDatabase.ImportAsset(assetPath, kReimport);

#if UNITY_2020_2_OR_NEWER
            UnityEditor.Compilation.CompilationPipeline.RequestScriptCompilation();
#endif

            Object asset = AssetDatabase.LoadAssetAtPath<Object>(assetPath);
            if (asset != null)
            {
                EditorGUIUtility.PingObject(asset);
                Selection.activeObject = asset;
                Debug.Log("[PyGenesis] Script importado y seleccionado en el Project: " + assetPath);
            }
            else
            {
                Debug.LogWarning(
                    "[PyGenesis] Refresh/ImportAsset ejecutados pero LoadAssetAtPath devolvió null. " +
                    "Comprueba en el explorador: " + fullPathOnDisk);
            }
        }
        catch (System.Exception ex)
        {
            Debug.LogError("[PyGenesis] Error al importar script: " + ex + "\n" + fullPathOnDisk);
        }
    }
}
