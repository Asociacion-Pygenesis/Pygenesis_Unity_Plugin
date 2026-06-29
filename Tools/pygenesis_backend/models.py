from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal


Severity = Literal["info", "low", "medium", "high", "critical"]
ActionSafety = Literal["safe", "review", "dangerous"]
ActionScope = Literal["selected_object", "scene", "asset", "multi_object"]
ActionSource = Literal["rules", "llm", "hybrid", "agent"]


class TransformData(BaseModel):
    position: List[float] = Field(default_factory=list)
    rotation: List[float] = Field(default_factory=list)
    scale: List[float] = Field(default_factory=list)


class SelectionData(BaseModel):
    name: str = ""
    type: str = ""
    has_collider: bool = False
    has_renderer: bool = False
    has_animator: bool = False
    has_rigidbody: bool = False
    transform: Optional[TransformData] = None


class CameraInspectorSummary(BaseModel):
    """Propiedades típicas del componente Camera (inspector)."""

    orthographic: bool = False
    orthographic_size: float = 0.0
    field_of_view: float = 0.0
    near_clip_plane: float = 0.0
    far_clip_plane: float = 0.0
    depth: float = 0.0
    clear_flags: str = ""
    culling_mask_summary: str = ""
    enabled: bool = True
    target_display: int = 0


class LightInspectorSummary(BaseModel):
    """Propiedades típicas del componente Light (inspector)."""

    light_type: str = ""
    color_rgb: List[float] = Field(default_factory=list)
    intensity: float = 0.0
    shadow_type: str = ""
    range: float = 0.0
    spot_angle: float = 0.0
    inner_spot_angle: float = 0.0
    enabled: bool = True
    bake_type: str = ""
    culling_mask_summary: str = ""


class SceneChildBrief(BaseModel):
    """Hijo directo con mismas señales que un objeto plano (segundo nivel de jerarquía)."""

    name: str = ""
    hierarchy_path: str = ""
    active: bool = True
    tag: str = ""
    layer_name: str = ""
    child_count: int = 0
    has_collider: bool = False
    has_renderer: bool = False
    has_animator: bool = False
    has_rigidbody: bool = False
    has_camera: bool = False
    has_light: bool = False
    is_static: bool = False
    light_inspector: Optional[LightInspectorSummary] = None
    camera_inspector: Optional[CameraInspectorSummary] = None


class SceneObjectSummary(BaseModel):
    """Raíz de escena con señales de componentes y vista rápida de hijos."""

    name: str = ""
    hierarchy_path: str = ""
    active: bool = True
    tag: str = ""
    layer_name: str = ""
    child_count: int = 0
    has_collider: bool = False
    has_renderer: bool = False
    has_animator: bool = False
    has_rigidbody: bool = False
    has_camera: bool = False
    has_light: bool = False
    is_static: bool = False
    direct_children_preview: str = ""
    first_level_children: List[SceneChildBrief] = Field(default_factory=list)
    light_inspector: Optional[LightInspectorSummary] = None
    camera_inspector: Optional[CameraInspectorSummary] = None


class SceneFlatObjectInfo(BaseModel):
    """Muestra BFS de objetos en la escena (ruta + componentes típicos)."""

    hierarchy_path: str = ""
    name: str = ""
    active: bool = True
    tag: str = ""
    layer_name: str = ""
    has_collider: bool = False
    has_renderer: bool = False
    has_animator: bool = False
    has_rigidbody: bool = False
    has_camera: bool = False
    has_light: bool = False
    is_static: bool = False
    direct_children_detail: List[SceneChildBrief] = Field(default_factory=list)
    light_inspector: Optional[LightInspectorSummary] = None
    camera_inspector: Optional[CameraInspectorSummary] = None


class SceneLightEntry(BaseModel):
    """Entrada en el índice de luces de la escena (BFS hasta límite)."""

    hierarchy_path: str = ""
    name: str = ""
    object_active: bool = True
    light: LightInspectorSummary = Field(default_factory=LightInspectorSummary)


class SceneCameraEntry(BaseModel):
    """Entrada en el índice de cámaras de la escena (BFS hasta límite)."""

    hierarchy_path: str = ""
    name: str = ""
    object_active: bool = True
    camera: CameraInspectorSummary = Field(default_factory=CameraInspectorSummary)


class SceneSnapshotData(BaseModel):
    """Instantánea de la escena activa enviada desde Unity (editor)."""

    root_count: int = 0
    total_estimated: int = 0
    roots: List[SceneObjectSummary] = Field(default_factory=list)
    flat_sample: List[SceneFlatObjectInfo] = Field(default_factory=list)
    lights_index: List[SceneLightEntry] = Field(default_factory=list)
    cameras_index: List[SceneCameraEntry] = Field(default_factory=list)
    scene_asset_path: str = ""
    # Unity puede enviar null; el backend lo acepta.
    note: Optional[str] = None


class AnalyzeSelectionRequest(BaseModel):
    command: str = ""
    scene_name: str = ""
    selection: Optional[SelectionData] = None
    scene_snapshot: Optional[SceneSnapshotData] = None


ChatRole = Literal["user", "assistant", "system"]


class ChatMessage(BaseModel):
    role: ChatRole
    content: str


class ChatRequest(BaseModel):
    """Mensajes del turno actual y historial reciente (solo user/assistant se conservan al truncar)."""

    messages: List[ChatMessage] = Field(min_length=1)
    scene_name: str = ""
    # Misma instantánea que Analyze Scene: jerarquía, muestra BFS, luces (inspector), etc.
    scene_snapshot: Optional[SceneSnapshotData] = None


class ChatResponse(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DetectedIssue(BaseModel):
    issue_id: str
    title: str = ""
    message: str
    severity: Severity = "low"
    category: str = "general"
    confidence: float = 1.0
    source: ActionSource = "rules"


class ActionTarget(BaseModel):
    scope: ActionScope = "selected_object"
    object_ref: Optional[str] = None


class ActionStep(BaseModel):
    step_id: str
    action: str
    label: str
    description: str = ""
    target: ActionTarget = Field(default_factory=ActionTarget)
    params: Dict[str, Any] = Field(default_factory=dict)
    safety: ActionSafety = "safe"
    confidence: float = 1.0
    source: ActionSource = "rules"
    depends_on: List[str] = Field(default_factory=list)
    can_auto_apply: bool = True
    rule_id: str = ""


class SuggestedAction(BaseModel):
    action: str
    label: str
    description: str = ""
    rule_id: str = ""
    confidence: float = 1.0
    safety: ActionSafety = "safe"
    target: ActionScope = "selected_object"
    params: Dict[str, Any] = Field(default_factory=dict)

    
class ExecutionPolicy(BaseModel):
    requires_user_confirmation: bool = False
    max_auto_apply_steps: int = 1
    allow_partial_execution: bool = True


class AnalyzeSelectionResponse(BaseModel):
    api_version: str = "4.0"
    mode: str = "rules"
    summary: str = ""
    issues: List[DetectedIssue] = Field(default_factory=list)
    plan: List[ActionStep] = Field(default_factory=list)
    execution_policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    message: str = ""
    suggestions: List[SuggestedAction] = Field(default_factory=list)