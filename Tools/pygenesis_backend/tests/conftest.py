# tests/conftest.py
import os
import pytest

# Desactivar warmup y RAG en todos los tests
os.environ.setdefault("PYGENESIS_LLM_WARMUP", "false")
# Evitar llamada real al LLM si algún test importa `main:app` (lifespan bloqueante).
os.environ.setdefault("PYGENESIS_LLM_SKIP_STARTUP_LOAD", "true")
os.environ.setdefault("PYGENESIS_RAG_ENABLED", "false")
os.environ.setdefault("PYGENESIS_SCENE_TWO_PASS", "false")


# ── Builders de selección ─────────────────────────────────────────

def make_selection(**kwargs):
    """Selección mínima válida con overrides opcionales."""
    from models import SelectionData, TransformData
    defaults = dict(
        name="TestObject",
        has_collider=False,
        has_renderer=False,
        has_animator=False,
        has_rigidbody=False,
        has_camera=False,
        has_light=False,
        is_static=False,
        transform=TransformData(
            position=[0, 0, 0],
            rotation=[0, 0, 0],
            scale=kwargs.pop("scale", [1, 1, 1]),
        ),
    )
    defaults.update(kwargs)
    return SelectionData(**defaults)


def make_scene_snapshot(**kwargs):
    """Snapshot de escena mínimo con overrides opcionales."""
    defaults = dict(
        root_count=kwargs.pop("root_count", 2),
        total_estimated=kwargs.pop("total_estimated", 5),
        roots=kwargs.pop("roots", [
            {"name": "Main Camera", "has_camera": True,
             "camera_inspector": {"depth": 0}, "hierarchy_path": "Main Camera"},
            {"name": "Directional Light", "has_light": True,
             "light_inspector": {"bake_type": "realtime", "light_type": "Directional"},
             "hierarchy_path": "Directional Light"},
        ]),
        flat_sample=kwargs.pop("flat_sample", []),
        lights_index=kwargs.pop("lights_index", [
            {"name": "Directional Light", "hierarchy_path": "Directional Light",
             "light_inspector": {"bake_type": "realtime", "light_type": "Directional",
                                 "intensity": 1.0}},
        ]),
        cameras_index=kwargs.pop("cameras_index", [
            {"name": "Main Camera", "hierarchy_path": "Main Camera",
             "camera_inspector": {"depth": 0, "orthographic": False}},
        ]),
        scene_asset_path="Assets/Scenes/Test.unity",
        note="",
    )
    defaults.update(kwargs)
    from models import SceneSnapshotData
    return SceneSnapshotData(**defaults)


def make_request(command="", selection=None, scene_snapshot=None, scene_name="TestScene"):
    from models import AnalyzeSelectionRequest
    return AnalyzeSelectionRequest(
        command=command,
        scene_name=scene_name,
        selection=selection,
        scene_snapshot=scene_snapshot,
    )


# ── Mock provider ─────────────────────────────────────────────────

class MockLLMProvider:
    """Provider que devuelve respuestas prefabricadas sin llamar a ninguna API."""

    def __init__(self, response: str | None = None, raise_exc: Exception | None = None):
        self._response = response
        self._raise = raise_exc
        self.calls: list[dict] = []   # historial de llamadas para asserts

    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system": system_prompt, "user": user_prompt})
        if self._raise is not None:
            raise self._raise
        return self._response or "{}"


MINIMAL_LLM_RESPONSE = """{
  "summary": "LLM analysis complete.",
  "issues": [],
  "plan": [],
  "execution_policy": {"requires_user_confirmation": false,
                        "max_auto_apply_steps": 1,
                        "allow_partial_execution": true},
  "metadata": {}
}"""


def make_llm_engine(response=MINIMAL_LLM_RESPONSE, raise_exc=None, fallback=None):
    from reasoning.llm_engine import LLMEngine
    provider = MockLLMProvider(response=response, raise_exc=raise_exc)
    return LLMEngine(provider, fallback=fallback), provider


@pytest.fixture
def minimal_selection():
    return make_selection()

@pytest.fixture
def minimal_scene(make_scene_snapshot=make_scene_snapshot):
    return make_scene_snapshot()

@pytest.fixture
def minimal_request():
    return make_request(selection=make_selection())