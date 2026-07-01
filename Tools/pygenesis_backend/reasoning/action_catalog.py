"""
Catálogo canónico de acciones del backend.

FUENTE DE VERDAD: este catálogo se alinea a mano con `PyGenesisActions.Catalog`
en `Assets/Pygenesis/Editor/PyGenesisActions.cs` (lo que Unity sabe ejecutar).
Si añades/quitas una acción o un parámetro en el plugin, refléjalo aquí.

Se usa para:
  1. Generar el bloque de acciones del prompt del LLM (reasoning/prompts.py).
  2. Filtrar y validar el `plan` de salida (reasoning/output_validator.py).

Opción B (futura): un ActionRegistry dinámico (services/action_registry.py)
cargado desde Unity vía POST /actions/register puede inyectarse como
`param_validator` para sustituir este catálogo estático en runtime. Mientras
ese endpoint no esté activo, este catálogo es la única fuente.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ActionTarget = str   # "selected_object" | "scene" | "asset" | "multi_object"
ActionSafety = str   # "safe" | "review" | "dangerous"
ParamType   = str    # "float" | "str" | "bool"

# Tipos Python aceptados por cada ParamType (float acepta int por conveniencia).
PARAM_PYTYPES: Dict[ParamType, tuple] = {
    "float": (int, float),
    "str":   (str,),
    "bool":  (bool,),
}


@dataclass(frozen=True)
class ParamSpec:
    name: str
    ptype: ParamType = "str"
    required: bool = False


@dataclass(frozen=True)
class ActionDefinition:
    action_id: str
    label: str
    description: str
    target: ActionTarget
    safety: ActionSafety
    params: List[ParamSpec] = field(default_factory=list)
    supports_auto_apply: bool = True

    # ── Compatibilidad con reasoning/prompts.py y output_validator.py ──────────
    @property
    def required_params(self) -> List[str]:
        return [p.name for p in self.params if p.required]

    @property
    def optional_params(self) -> List[str]:
        return [p.name for p in self.params if not p.required]

    @property
    def param_types(self) -> Dict[str, tuple]:
        return {p.name: PARAM_PYTYPES[p.ptype] for p in self.params}


# ══════════════════════════════════════════════════════════════════════════════
# CATÁLOGO CANÓNICO — espejo de PyGenesisActions.Catalog (Unity)
# ══════════════════════════════════════════════════════════════════════════════

ACTION_CATALOG: Dict[str, ActionDefinition] = {
    # ── Transform / identidad ────────────────────────────────────────────────
    "rename_object": ActionDefinition(
        action_id="rename_object",
        label="Rename Object",
        description="Rename the selected object.",
        target="selected_object",
        safety="safe",
        params=[ParamSpec("name", "str", required=True)],
    ),
    "set_scale": ActionDefinition(
        action_id="set_scale",
        label="Set Scale",
        description="Set the local scale of the selected object.",
        target="selected_object",
        safety="safe",
        params=[
            ParamSpec("x", "float", required=True),
            ParamSpec("y", "float", required=True),
            ParamSpec("z", "float", required=True),
        ],
    ),
    "set_position": ActionDefinition(
        action_id="set_position",
        label="Set Position",
        description="Set the local position of the selected object.",
        target="selected_object",
        safety="safe",
        params=[
            ParamSpec("x", "float", required=True),
            ParamSpec("y", "float", required=True),
            ParamSpec("z", "float", required=True),
        ],
    ),

    # ── Componentes ──────────────────────────────────────────────────────────
    "add_component": ActionDefinition(
        action_id="add_component",
        label="Add Component",
        description="Add a component (by type name, e.g. Rigidbody) to the selected object.",
        target="selected_object",
        safety="review",
        params=[ParamSpec("component", "str", required=True)],
    ),
    "remove_component": ActionDefinition(
        action_id="remove_component",
        label="Remove Component",
        description="Remove a component (by type name) from the selected object.",
        target="selected_object",
        safety="review",
        params=[ParamSpec("component", "str", required=True)],
    ),

    # ── Jerarquía ──────────────────────────────────────────────────────────────
    "set_parent": ActionDefinition(
        action_id="set_parent",
        label="Set Parent",
        description="Reparent the selected object under an existing object found by name.",
        target="selected_object",
        safety="review",
        params=[ParamSpec("parent_name", "str", required=True)],
    ),
    "create_child": ActionDefinition(
        action_id="create_child",
        label="Create Child",
        description="Create a new empty child GameObject under the selected object.",
        target="selected_object",
        safety="safe",
        params=[ParamSpec("name", "str")],
    ),
    "create_empty_parent": ActionDefinition(
        action_id="create_empty_parent",
        label="Create Empty Parent",
        description="Insert a new empty parent above the selected object.",
        target="selected_object",
        safety="review",
        params=[ParamSpec("name", "str")],
    ),

    # ── Prefabs ────────────────────────────────────────────────────────────────
    "create_prefab": ActionDefinition(
        action_id="create_prefab",
        label="Create Prefab",
        description="Save the selected object as a prefab asset.",
        target="asset",
        safety="review",
        params=[ParamSpec("folder", "str"), ParamSpec("file_name", "str")],
    ),
    "unpack_prefab": ActionDefinition(
        action_id="unpack_prefab",
        label="Unpack Prefab",
        description="Unpack the selected prefab instance completely.",
        target="selected_object",
        safety="review",
    ),

    # ── Estado / flags ───────────────────────────────────────────────────────
    "set_active": ActionDefinition(
        action_id="set_active",
        label="Set Active",
        description="Enable or disable the selected object.",
        target="selected_object",
        safety="safe",
        params=[ParamSpec("active", "bool")],
    ),
    "set_static": ActionDefinition(
        action_id="set_static",
        label="Set Static",
        description="Mark the selected object as static (optionally recursive).",
        target="selected_object",
        safety="safe",
        params=[ParamSpec("static", "bool"), ParamSpec("recursive", "bool")],
    ),
    "set_tag": ActionDefinition(
        action_id="set_tag",
        label="Set Tag",
        description="Set the tag of the selected object.",
        target="selected_object",
        safety="safe",
        params=[ParamSpec("tag", "str")],
    ),
    "set_layer": ActionDefinition(
        action_id="set_layer",
        label="Set Layer",
        description="Set the layer of the selected object (optionally recursive).",
        target="selected_object",
        safety="safe",
        params=[ParamSpec("layer", "str", required=True), ParamSpec("recursive", "bool")],
    ),

    # ── Material / renderer ──────────────────────────────────────────────────
    "set_material_color": ActionDefinition(
        action_id="set_material_color",
        label="Set Material Color",
        description="Set the shared material color (RGBA 0..1) of the selected object's renderer.",
        target="selected_object",
        safety="safe",
        params=[
            ParamSpec("r", "float"),
            ParamSpec("g", "float"),
            ParamSpec("b", "float"),
            ParamSpec("a", "float"),
        ],
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
# ALIAS LEGACY → acción canónica
# ══════════════════════════════════════════════════════════════════════════════
# Acciones antiguas (catálogo previo / modelos entrenados con vocabulario viejo)
# que se traducen a una acción canónica que Unity sí sabe ejecutar.

@dataclass(frozen=True)
class ActionAlias:
    canonical: str
    inject: Dict[str, object] = field(default_factory=dict)   # params fijos a inyectar
    rename: Dict[str, str] = field(default_factory=dict)       # viejo_nombre → nuevo_nombre


ACTION_ALIASES: Dict[str, ActionAlias] = {
    "rename_selected":  ActionAlias("rename_object", rename={"new_name": "name"}),
    "add_box_collider": ActionAlias("add_component", inject={"component": "BoxCollider"}),
    "add_animator":     ActionAlias("add_component", inject={"component": "Animator"}),
    "add_rigidbody":    ActionAlias("add_component", inject={"component": "Rigidbody"}),
}


def resolve_action(action_id: str, params: dict | None = None) -> Tuple[str, dict]:
    """
    Resuelve un action_id (posible alias legacy) a su acción canónica y
    devuelve (canonical_id, params_resueltos).

    Para una acción no-alias devuelve el mismo id y una copia de los params.
    Para un alias: aplica renombrados de params y luego inyecta los fijos
    (los inyectados ganan, para garantizar p. ej. component=BoxCollider).
    """
    src = dict(params or {})
    alias = ACTION_ALIASES.get(action_id)
    if alias is None:
        return action_id, src

    renamed = {alias.rename.get(k, k): v for k, v in src.items()}
    renamed.update(alias.inject)
    return alias.canonical, renamed


# IDs aceptados de entrada (canónicos + alias legacy). Los alias NO se anuncian
# al LLM (ver reasoning/prompts.py), solo se aceptan de forma defensiva.
SUPPORTED_ACTION_IDS = set(ACTION_CATALOG.keys()) | set(ACTION_ALIASES.keys())
