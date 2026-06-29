"""Chat con scene_snapshot en el system prompt."""

from models import (
    CameraInspectorSummary,
    ChatMessage,
    ChatRequest,
    LightInspectorSummary,
    SceneCameraEntry,
    SceneLightEntry,
    SceneSnapshotData,
)
from reasoning.chat_prompts import build_chat_system_prompt


def test_build_chat_system_prompt_includes_scene_json():
    snap = SceneSnapshotData(
        scene_asset_path="Assets/X.unity",
        root_count=1,
        total_estimated=5,
        lights_index=[
            SceneLightEntry(
                hierarchy_path="Directional Light",
                name="Directional Light",
                object_active=True,
                light=LightInspectorSummary(
                    light_type="Directional",
                    intensity=1.2,
                    shadow_type="Soft",
                ),
            )
        ],
        cameras_index=[
            SceneCameraEntry(
                hierarchy_path="Main Camera",
                name="Main Camera",
                object_active=True,
                camera=CameraInspectorSummary(
                    orthographic=False,
                    field_of_view=60.0,
                    clear_flags="Skybox",
                ),
            )
        ],
    )
    s = build_chat_system_prompt(
        scene_name="X",
        last_user_message="¿Qué luces hay en mi escena?",
        scene_snapshot=snap,
    )
    assert "ESTADO ACTUAL DE LA ESCENA UNITY" in s
    assert "lights_index" in s
    assert "cameras_index" in s
    assert "Directional" in s
    assert "Main Camera" in s
    assert "Assets/X.unity" in s


def test_build_chat_system_prompt_omits_scene_for_generic_question():
    """Pregunta general (sin relación con la escena): no se inyecta el JSON de escena (menos latencia)."""
    snap = SceneSnapshotData(
        scene_asset_path="Assets/X.unity",
        root_count=1,
        total_estimated=5,
        cameras_index=[
            SceneCameraEntry(
                hierarchy_path="Main Camera",
                name="Main Camera",
                object_active=True,
                camera=CameraInspectorSummary(orthographic=False, field_of_view=60.0),
            )
        ],
    )
    s = build_chat_system_prompt(
        scene_name="X",
        last_user_message="¿Cómo puedo usar un Rigidbody?",
        scene_snapshot=snap,
    )
    assert "Fin estado escena" not in s
    assert "Assets/X.unity" not in s
    assert "Main Camera" not in s


def test_build_chat_system_prompt_scene_context_always(monkeypatch):
    """PYGENESIS_CHAT_SCENE_CONTEXT=always fuerza incluir la escena aunque la pregunta sea genérica."""
    monkeypatch.setenv("PYGENESIS_CHAT_SCENE_CONTEXT", "always")
    snap = SceneSnapshotData(scene_asset_path="Assets/X.unity", root_count=1, total_estimated=1)
    s = build_chat_system_prompt(
        scene_name="X",
        last_user_message="¿Cómo puedo usar un Rigidbody?",
        scene_snapshot=snap,
    )
    assert "Fin estado escena" in s
    assert "Assets/X.unity" in s


def test_chat_request_accepts_scene_snapshot():
    snap = SceneSnapshotData(root_count=0, note="empty")
    req = ChatRequest(
        messages=[ChatMessage(role="user", content="hola")],
        scene_name="E",
        scene_snapshot=snap,
    )
    assert req.scene_snapshot is not None
    assert req.scene_snapshot.note == "empty"
