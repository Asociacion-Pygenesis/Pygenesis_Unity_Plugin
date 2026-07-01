# Unity User Manual — guía de referencia para el asistente

Este fichero no reproduce el Manual de Unity; resume **qué cubre** y enlaza a las secciones oficiales para que el modelo oriente al usuario y cite fuentes correctas.

## Qué es el Manual

El **Unity User Manual** documenta el editor, flujos de trabajo, ventanas, importación de assets, física, animación, audio, iluminación, UI, compilación de jugadores y paquetes. La versión debe coincidir con la del proyecto (Unity Hub → Documentation o selector de versión en docs).

- Índice general del Manual: https://docs.unity3d.com/Manual/index.html

## Conceptos centrales (enlazar según tema)

| Tema | Enlace útil (Manual) |
|------|----------------------|
| Visión general del editor | https://docs.unity3d.com/Manual/UnityOverview.html |
| GameObjects y componentes | https://docs.unity3d.com/Manual/GameObjects.html |
| Escenas | https://docs.unity3d.com/Manual/CreatingScenes.html |
| Prefabs | https://docs.unity3d.com/Manual/Prefabs.html |
| Transform y jerarquía | https://docs.unity3d.com/Manual/class-Transform.html |
| Tags y Layers | https://docs.unity3d.com/Manual/Tags.html |
| Física (overview) | https://docs.unity3d.com/Manual/PhysicsSection.html |
| Rigidbody | https://docs.unity3d.com/Manual/class-Rigidbody.html |
| Colliders | https://docs.unity3d.com/Manual/CollidersOverview.html |
| Animator y Mecanim (sección) | https://docs.unity3d.com/Manual/AnimationSection.html |
| Iluminación (overview) | https://docs.unity3d.com/Manual/Lighting.html |
| Calidad y gráficos | https://docs.unity3d.com/Manual/graphics-tiers.html |
| UI: uGUI Canvas | https://docs.unity3d.com/Manual/UISystem.html |
| Input System (paquete) | https://docs.unity3d.com/Packages/com.unity.inputsystem@latest |

## Scripting Reference (API de runtime), no confundir con el Manual

La API de clases (`MonoBehaviour`, `Physics`, etc.) está en la **Scripting Reference**, no en el Manual largo:

- https://docs.unity3d.com/ScriptReference/

## Buenas prácticas al responder

- Si el usuario no indica versión de Unity, advierte que nombres de menús o paquetes pueden variar.
- Para pasos del editor, prefiere el Manual; para firmas de métodos y propiedades C#, la Scripting Reference.
- Indica al usuario que puede usar el buscador oficial de documentación en docs.unity3d.com con su versión.
