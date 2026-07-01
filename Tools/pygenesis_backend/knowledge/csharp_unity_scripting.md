# C# y scripting en Unity — fuentes documentadas

Este fichero orienta al asistente hacia **documentación oficial** de lenguaje y de API Unity; no sustituye a esas fuentes.

## C# (lenguaje)

Microsoft documenta el lenguaje C# de forma independiente de Unity:

- Centro de documentación C#: https://learn.microsoft.com/dotnet/csharp/
- Tour del lenguaje: https://learn.microsoft.com/dotnet/csharp/tour-of-csharp/
- Fundamentos (tipos, clases, interfaces): https://learn.microsoft.com/dotnet/csharp/fundamentals/
- Programación orientada a objetos: https://learn.microsoft.com/dotnet/csharp/fundamentals/object-oriented/
- Asincronía (`async`/`await`): https://learn.microsoft.com/dotnet/csharp/asynchronous-programming/
- Guía de codificación .NET (estilo): https://learn.microsoft.com/dotnet/csharp/fundamentals/coding-style/coding-conventions

**Nota:** Unity usa un runtime y versiones de C# concretas según versión del editor (p. ej. características disponibles). Si el usuario pregunta por una característica moderna de C#, conviene mencionar compatibilidad con su Unity.

## Unity Scripting Reference (API)

Toda la API de `UnityEngine`, `UnityEditor`, etc.:

- https://docs.unity3d.com/ScriptReference/

Puntos de entrada habituales:

| Concepto | Enlace |
|----------|--------|
| MonoBehaviour (ciclo de vida) | https://docs.unity3d.com/ScriptReference/MonoBehaviour.html |
| ScriptableObject | https://docs.unity3d.com/ScriptReference/ScriptableObject.html |
| Object (Destroy, Instantiate) | https://docs.unity3d.com/ScriptReference/Object.html |
| Physics | https://docs.unity3d.com/ScriptReference/Physics.html |
| Input (legacy) | https://docs.unity3d.com/ScriptReference/Input.html |

## Manual vs Scripting Reference

- **Manual**: flujos en el editor, conceptos, ventanas.
- **Scripting Reference**: clases, métodos, propiedades exactas en C#.

## Buenas prácticas al responder código

- Cita la Scripting Reference para APIs de Unity; cita Learn Microsoft para reglas puramente de C#.
- Si hay ambigüedad (varias sobrecargas), indica qué overload o enlace revisar.
