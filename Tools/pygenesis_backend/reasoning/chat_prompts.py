"""System prompt y textos estáticos para el modo conversacional (/chat)."""

import json
import logging
import os

from models import SceneSnapshotData

from .knowledge_loader import build_knowledge_block

logger = logging.getLogger("pygenesis")

# El JSON de escena es, con diferencia, el bloque más pesado del system prompt; en inferencia local
# (Ollama/CPU/iGPU) dispara el "prompt eval" y deja poco margen de num_ctx para la respuesta (se trunca).
# Por eso solo se inyecta cuando la pregunta trata de la escena. Control: PYGENESIS_CHAT_SCENE_CONTEXT.
_SCENE_KEYWORDS = (
    "escena",
    "scene",
    "jerarqu",
    "hierarchy",
    "gameobject",
    "game object",
    "objeto",
    "object",
    "luz",
    "luces",
    "light",
    "cámara",
    "camara",
    "camera",
    "sombra",
    "shadow",
    "skybox",
    "iluminaci",
    "lighting",
    "selecci",
    "selected",
    "selection",
    "prefab",
    "renderer",
)

# Los bloques de dominio (C#, animación, texturas) también engordan el prompt; en auto solo se
# inyecta el que encaje con la pregunta. Control: PYGENESIS_CHAT_DOMAIN_BLOCKS (auto|always|off).
_DOMAIN_CSHARP_KEYWORDS = (
    "script",
    "c#",
    "csharp",
    "código",
    "codigo",
    "code",
    "clase",
    "class",
    "método",
    "metodo",
    "method",
    "función",
    "funcion",
    "function",
    "monobehaviour",
    "componente",
    "component",
    "rigidbody",
    "collider",
    "physics",
    "física",
    "fisica",
    "input",
    "update",
    "start(",
    "awake",
    "coroutine",
    "corrutina",
    "serialize",
    "compil",
    "namespace",
    "evento",
    "event",
    "singleton",
    "scriptableobject",
    "raycast",
    "vector",
    "transform",
    "instantiate",
    "destroy",
    "getcomponent",
    "variable",
    "interfaz",
    "interface",
    "delegate",
    "async",
    "enum",
)
_DOMAIN_ANIMATION_KEYWORDS = (
    "anim",
    "animator",
    "animation",
    "clip",
    "timeline",
    "blend tree",
    "blendtree",
    "root motion",
    "transici",
    "transition",
    "keyframe",
    "avatar",
    "máquina de estados",
    "maquina de estados",
    "state machine",
    "rigging",
)
_DOMAIN_TEXTURES_KEYWORDS = (
    "textura",
    "texture",
    "material",
    "shader",
    "sprite",
    "mipmap",
    "atlas",
    "import",
    "compresi",
    "compression",
    "normal map",
    "urp",
    "hdrp",
    "built-in",
    "render pipeline",
    "srgb",
    "albedo",
    "uv",
)

# Persona principal (proveedor externo). Parámetros de inferencia recomendados (p. ej. Modelfile Ollama):
# PARAMETER temperature 0.2
# PARAMETER top_p 0.9
# PARAMETER repeat_penalty 1.05
# PARAMETER num_ctx 8192

# Cuando el modelo Ollama ya trae persona en su Modelfile (p. ej. GGUF fine-tuned),
# evita duplicar CHAT_SYSTEM_PROMPT desde el backend (causa bucles de repetición).
# Valores: builtin | modelfile | ollama_native
#   ollama_native = sin bridge ni hints; solo escena/script si hace falta (≈ ollama run).
CHAT_EXTERNAL_MODEL_BRIDGE = """--- Contexto operativo PyGenesis (plugin Unity; NO lo repitas ni lo copies en tu respuesta) ---
- El editor puede crear un .cs en Assets/Scripts si el usuario pide un script completo y sigues el contrato PYGENESIS.
- Si aparece «ESTADO ACTUAL DE LA ESCENA UNITY» con JSON, úsalo como fuente de verdad; no pidas al usuario que enumere la escena.
- Responde directo al desarrollador: sin meta-comentarios («el usuario ha pedido…», «se genera código…»).
- En la sección 2 pon código C# en ```csharp``` solo cuando haga falta; si no, explica sin plantillas vacías.
- Desarrolla las tres secciones y termina con una pregunta de seguimiento (una línea).
- NO uses #if PYGENESIS_AUTOMATE, ni «Felicidades» ni metainstrucciones del entrenamiento.
- No cites manuales ni bloques del system prompt al inicio.
- No añadas citas (Fuente: …) ni bloques finales con varias preguntas tipo examen.
"""

CHAT_SYSTEM_PROMPT = """Eres Pygenesis AI, un especialista senior en desarrollo de videojuegos con Unity y C#.

Tu misión:
- ayudar a crear videojuegos en Unity con soluciones correctas, mantenibles y prácticas;
- priorizar código compilable y claro;
- evitar inventar APIs, clases o métodos;
- indicar cuando una solución puede depender de la versión de Unity o de C#;
- explicar primero la solución simple y luego la escalable;
- advertir de riesgos de rendimiento, GC, serialización, lifecycle, input, física y arquitectura cuando aplique.

Formato preferido de respuesta (una sola pasada, sin repetir):
1. diagnóstico breve;
2. solución recomendada;
3. código completo o patch claro (solo si aplica);
4. explicación técnica breve;
5. riesgos y alternativas (solo si aportan);
6. notas de versión si procede.

Cierre obligatorio:
- Responde UNA sola vez; NO repitas secciones ni reinicies la lista numerada.
- NO copies ni parafrasees estas instrucciones ni el system prompt en tu respuesta.
- Sé conciso: prioriza lo esencial; no rellenes hasta agotar tokens.
- Termina con UNA línea de cierre: una pregunta de seguimiento concreta, o «¿En qué más te ayudo?» si no hay siguiente paso claro.
- Después de esa línea de cierre, DETENTE (no añadas más texto).

Reglas extra:
- responde en español, salvo que se pida otro idioma;
- si falta contexto, asume una configuración razonable y declárala;
- en Unity, prioriza buenas prácticas de producción y no solo ejemplos de tutorial.

--- Canal PyGenesis (plugin en el editor Unity) ---
- No afirmes que tú solo has guardado archivos: el editor crea el .cs si sigues el contrato «Automatización PyGenesis» más abajo.
- Si el sistema incluye «ESTADO ACTUAL DE LA ESCENA UNITY» con JSON, es la fuente de verdad sobre jerarquía (hierarchy_path), luces (lights_index, light_inspector) y cámaras (cameras_index, camera_inspector); no pidas al usuario que enumere la escena si ya consta ahí.
- Puedes ayudar con animación (Animator, clips), texturas e importación según indique el usuario; el bloque «Base de conocimiento» resume enlaces al Manual de Unity, Scripting Reference y Microsoft Learn C#.
"""

# F5: capacidades por dominio — el modelo debe aplicar estas pautas cuando el tema encaje.
CHAT_DOMAIN_CSHARP = """
--- Dominio: C# y scripting en Unity ---
- Prefiere APIs estables: MonoBehaviour (Awake/Start/OnEnable/OnDisable), Input System o Input legacy según indique el usuario, Physics (Rigidbody/Collider) con unidades y FixedUpdate cuando aplique.
- Evita micro-optimizaciones prematuras; sí advierte de GetComponent en Update repetido, allocations en hot paths y comparaciones de strings en bucles.
- Para el Editor: usa #if UNITY_EDITOR, [MenuItem], EditorWindow solo si el usuario pide herramientas de editor; no mezcles lógica de juego con código de editor sin separar.
- Serialización: campos públicos o [SerializeField]; evita inicializar referencias a assets en constructores; usa Awake/OnValidate cuando toque.
- Nombres claros en inglés o el estilo del proyecto del usuario; comenta solo lo no obvio.
- Si el usuario pega errores de compilación, relaciona línea/símbolo con causa y propón el parche mínimo.
"""

CHAT_DOMAIN_ANIMATION = """
--- Dominio: Animator, animación y estado ---
- Distingue Animator Controller vs Animation Clip vs Timeline; indica en qué ventana se trabaja cada cosa.
- Transiciones: condiciones (bool/trigger/float), Has Exit Time, interrupt priority; advierte de estados sin transición de salida.
- Root motion: cuándo conviene y qué requiere en el Animator y el Rigidbody/CharacterController.
- Blend Trees y 2D blending: cuándo simplificar con menos parámetros.
- Optimización: capas solo si hace falta; Animator culling; evitar parámetros que cambien cada frame sin necesidad.
"""

CHAT_SCRIPT_AUTOMATION = """
--- Automatización PyGenesis (crear .cs en Assets/Scripts) ---
Úsalo SOLO si el usuario pide explícitamente un script C# completo para Unity (implementación en un archivo).
1) Pon el código completo en un bloque markdown: ```csharp ... ``` (o ```c# ... ```).
2) Justo DESPUÉS de ese bloque, en líneas separadas y sin texto adicional entre medias, incluye EXACTAMENTE:
---PYGENESIS_CREATE_SCRIPT---
{"fileName":"NombreDelArchivo.cs"}
---PYGENESIS_SCRIPT_END---
3) fileName: solo el nombre del archivo (sin carpetas), solo letras, números y guion bajo, terminando en .cs (ej. PlayerMove2D.cs).
4) Si el usuario no pidió un script listo para guardar, o solo quiere fragmentos o explicación, NO añadas este bloque.
"""

# Sin literales de marcadores: reduce que el modelo los copie en preguntas generales.
CHAT_SCRIPT_AUTOMATION_HINT = """
--- Automatización PyGenesis (solo si piden un .cs completo para guardar en Assets/Scripts) ---
Incluye ```csharp``` compilable y el contrato de marcadores que conoce el editor. No narres al usuario
qué vas a hacer («el usuario ha pedido…»); ve directo a las secciones 1→2→3. En preguntas generales
no cites marcadores ni contratos de creación de archivos.
"""

_SCRIPT_CREATE_KEYWORDS = (
    "script completo",
    "crea el script",
    "crear el script",
    "hazme un script",
    "genera el script",
    "genera un script",
    "archivo .cs",
    "un .cs",
    "guardar en assets",
    "implementación en un archivo",
    "implementacion en un archivo",
    "listo para guardar",
    "crea un script",
    "escribe un script",
)

CHAT_DOMAIN_TEXTURES = """
--- Dominio: texturas, importación y materiales ---
- Pregunta pipeline (Built-in / URP / HDRP) antes de Shader Graph o propiedades de materiales específicas.
- Import: tamaño máximo vs uso (mundo/UI), mipmaps en 3D, sin mipmaps en UI salvo casos especiales, Read/Write solo si hace falta.
- Compresión: equilibrio calidad/memoria/plataforma (PC vs móvil); normales y máscaras suelen necesitar formatos distintos a color.
- sRGB: albedo sí, datos lineales (normal maps, roughness/metallic en canales) según convención del pipeline.
- Si hay banding o bleeding, sugiere revisar filtros, padding en atlas y compresión por plataforma.
"""


def _scene_snapshot_block(snapshot: SceneSnapshotData) -> str:
    d = snapshot.model_dump(mode="json", exclude_none=True)
    js = json.dumps(d, ensure_ascii=False, indent=2)
    return (
        "\n\n--- ESTADO ACTUAL DE LA ESCENA UNITY (enviado por el editor PyGenesis; datos reales) ---\n"
        "Usa este JSON para responder sobre objetos, jerarquía y luces. "
        "Campos clave: scene_asset_path, root_count, total_estimated, roots, flat_sample (muestra BFS), "
        "lights_index (luces con tipo/sombras/intensidad/color), cameras_index (ortográfica/FOV/planos/clearFlags/culling), "
        "light_inspector y camera_inspector en nodos con has_light / has_camera. hierarchy_path identifica cada GameObject.\n"
        f"{js}\n"
        "--- Fin estado escena ---\n"
    )


def _scene_context_mode() -> str:
    """auto (defecto) = incluir escena solo si la pregunta trata de ella; always = siempre; off = nunca."""
    raw = (os.getenv("PYGENESIS_CHAT_SCENE_CONTEXT") or "auto").strip().lower()
    if raw in ("always", "on", "1", "true", "yes"):
        return "always"
    if raw in ("off", "never", "0", "false", "no", "none"):
        return "off"
    return "auto"


def _scene_object_names(snapshot: SceneSnapshotData) -> set[str]:
    """Nombres de objetos del snapshot (en minúsculas) para detectar si el usuario menciona uno por nombre."""
    try:
        data = snapshot.model_dump(mode="json", exclude_none=True)
    except Exception:  # noqa: BLE001 - ante cualquier fallo de serialización, sin nombres
        return set()

    names: set[str] = set()

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "name" and isinstance(value, str):
                    nm = value.strip().lower()
                    if len(nm) >= 3:
                        names.add(nm)
                else:
                    _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(data)
    return names


def _should_include_scene(last_user_message: str, scene_snapshot: SceneSnapshotData | None) -> bool:
    if scene_snapshot is None:
        return False
    mode = _scene_context_mode()
    if mode == "always":
        return True
    if mode == "off":
        return False
    msg = (last_user_message or "").strip().lower()
    if not msg:
        return False
    if any(kw in msg for kw in _SCENE_KEYWORDS):
        return True
    return any(name in msg for name in _scene_object_names(scene_snapshot))


def _chat_persona_mode() -> str:
    """
    builtin = persona larga del backend.
    modelfile = bridge + hints (persona principal en Modelfile Ollama).
    ollama_native = system casi vacío; alinear con `ollama run` (solo extras operativos).
    """
    raw = (os.getenv("PYGENESIS_CHAT_PERSONA") or "builtin").strip().lower()
    if raw in ("ollama_native", "native", "ollama-only", "ollama_only", "passthrough"):
        return "ollama_native"
    if raw in ("modelfile", "external", "ollama", "custom"):
        return "modelfile"
    return "builtin"


def chat_persona_mode() -> str:
    """Modo actual de PYGENESIS_CHAT_PERSONA (para logs y tests)."""
    return _chat_persona_mode()


def _domain_blocks_mode() -> str:
    """auto (defecto) = incluir solo los dominios que encajan; always = los tres; off = ninguno."""
    raw = (os.getenv("PYGENESIS_CHAT_DOMAIN_BLOCKS") or "auto").strip().lower()
    if raw in ("always", "on", "1", "true", "yes"):
        return "always"
    if raw in ("off", "never", "0", "false", "no", "none"):
        return "off"
    return "auto"


def _select_domain_blocks(last_user_message: str) -> list[str]:
    """Bloques de dominio a incluir según la pregunta (reduce el prompt en preguntas acotadas)."""
    mode = _domain_blocks_mode()
    if mode == "off":
        return []
    if mode == "always":
        return [
            CHAT_DOMAIN_CSHARP.strip(),
            CHAT_DOMAIN_ANIMATION.strip(),
            CHAT_DOMAIN_TEXTURES.strip(),
        ]
    msg = (last_user_message or "").strip().lower()
    if not msg:
        return []
    blocks: list[str] = []
    if any(k in msg for k in _DOMAIN_CSHARP_KEYWORDS):
        blocks.append(CHAT_DOMAIN_CSHARP.strip())
    if any(k in msg for k in _DOMAIN_ANIMATION_KEYWORDS):
        blocks.append(CHAT_DOMAIN_ANIMATION.strip())
    if any(k in msg for k in _DOMAIN_TEXTURES_KEYWORDS):
        blocks.append(CHAT_DOMAIN_TEXTURES.strip())
    return blocks


def _wants_script_creation(last_user_message: str) -> bool:
    msg = (last_user_message or "").strip().lower()
    if not msg:
        return False
    if any(k in msg for k in _SCRIPT_CREATE_KEYWORDS):
        return True
    if "script" in msg and any(w in msg for w in ("completo", "entero", "archivo", "assets", "guarda", "guardar")):
        return True
    return False


def build_chat_system_prompt(
    *,
    scene_name: str = "",
    last_user_message: str = "",
    scene_snapshot: SceneSnapshotData | None = None,
) -> str:
    # CHAT_SCRIPT_AUTOMATION justo después del encabezado: si el system prompt se recorta por tamaño,
    # la cabecera suele conservarse y el modelo sigue viendo el contrato PYGENESIS (create_script en Unity).
    persona_mode = _chat_persona_mode()
    parts: list[str] = []

    if persona_mode == "ollama_native":
        logger.info("Chat persona: ollama_native (system mínimo; persona solo en Modelfile)")
        if _wants_script_creation(last_user_message):
            parts.append(CHAT_SCRIPT_AUTOMATION.strip())
            logger.info("Chat persona: ollama_native + contrato create_script (petición explícita)")
    elif persona_mode == "modelfile":
        script_block = CHAT_SCRIPT_AUTOMATION_HINT.strip()
        parts = [CHAT_EXTERNAL_MODEL_BRIDGE.strip(), script_block]
        logger.info("Chat persona: modelfile")
    else:
        script_block = CHAT_SCRIPT_AUTOMATION_HINT.strip()
        parts = [CHAT_SYSTEM_PROMPT.strip(), script_block]

    include_scene = _should_include_scene(last_user_message, scene_snapshot)
    if include_scene:
        parts.append(_scene_snapshot_block(scene_snapshot).strip())
    if scene_snapshot is not None:
        logger.info(
            "Chat scene context: included=%s (mode=%s)", include_scene, _scene_context_mode()
        )

    if persona_mode == "ollama_native":
        domain_blocks: list[str] = []
        logger.info("Chat domain blocks: 0 (ollama_native)")
    else:
        domain_blocks = _select_domain_blocks(last_user_message)
        parts.extend(domain_blocks)
        logger.info(
            "Chat domain blocks: %d incluidos (mode=%s)", len(domain_blocks), _domain_blocks_mode()
        )

    inject_knowledge = persona_mode == "builtin" and (domain_blocks or include_scene)
    if inject_knowledge:
        kb = build_knowledge_block(user_message=last_user_message)
        if kb:
            parts.append(kb)
    elif persona_mode in ("modelfile", "ollama_native"):
        logger.debug("Chat knowledge: no inyectado (persona=%s)", persona_mode)

    base = "\n\n".join(parts)
    sn = (scene_name or "").strip()
    if sn and parts:
        return f"{base}\n\nNombre de la escena activa (Unity): {sn}."
    return base


def get_capabilities_payload() -> dict:
    """Respuesta de GET /chat/capabilities (sin llamar al LLM)."""
    return {
        "assistant": "Pygenesis AI",
        "greeting": (
            "Hola, soy Pygenesis AI. Puedo ayudarte con el proyecto en Unity: "
            "analizar objetos y escenas, proponer scripts en C#, orientarte en animaciones "
            "y en problemas de texturas y materiales. "
            "Tengo referencia al Manual de Unity, la Scripting Reference y la documentación de C# (Microsoft Learn) "
            "mediante un índice y notas locales en el backend; opcionalmente, con el índice RAG construido en el backend, "
            "puedo usar fragmentos recuperados de páginas permitidas (lista blanca). "
            "Para detalle fino conviene abrir los enlaces oficiales. "
            "Cuando preguntas por tu escena (objetos, jerarquía, luces o cámaras) uso una instantánea de la escena activa que envía el editor; en preguntas generales no la cargo, para responder más rápido. "
            "En el chat puedes usar «Analyze selection» para enviar la selección del editor al backend y ver el resultado aquí. "
            "Si pides un script C# completo, el plugin puede crear el .cs en Assets/Scripts cuando la respuesta incluye el contrato PYGENESIS."
        ),
        "capabilities": [
            {
                "id": "objects_scenes",
                "title": "Análisis de objetos y escenas",
                "description": "Interpretar contexto de selección o descripción de jerarquía y escena.",
            },
            {
                "id": "official_docs",
                "title": "Documentación Unity y C#",
                "description": "Índices y guías locales con enlaces al Manual, Scripting Reference y Microsoft Learn C# (modo PYGENESIS_CHAT_KNOWLEDGE).",
            },
            {
                "id": "rag_allowlist",
                "title": "RAG sobre fuentes permitidas",
                "description": "Con PYGENESIS_RAG_ENABLED y un índice Chroma (script build_rag_index.py), se inyectan fragmentos de docs.unity3d.com / learn.microsoft.com / docs.microsoft.com.",
            },
            {
                "id": "chat_analyze_selection",
                "title": "Analizar selección desde el chat",
                "description": "Botón Analyze selection: misma API que el asistente principal; el resultado se añade al hilo.",
            },
            {
                "id": "csharp",
                "title": "Scripts C# para Unity",
                "description": "Generar o refinar código (movimiento, componentes, API del editor) para que lo copies o integre PyGenesis.",
            },
            {
                "id": "create_script_assets",
                "title": "Crear .cs en Assets/Scripts",
                "description": "Si pides un script completo, el asistente puede incluir el bloque PYGENESIS; el editor crea el archivo e importa.",
            },
            {
                "id": "animation",
                "title": "Animaciones",
                "description": "Flujo Animator, clips, parámetros y buenas prácticas.",
            },
            {
                "id": "textures",
                "title": "Texturas y materiales",
                "description": "Import settings, compresión, sombreado y diagnóstico de problemas visuales.",
            },
        ],
    }
