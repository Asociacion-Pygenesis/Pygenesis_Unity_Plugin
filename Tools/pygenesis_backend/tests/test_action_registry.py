# tests/test_action_registry.py
"""
Tests para ActionRegistry: carga, validación, coerción y generación de prompt.
Instancia ActionRegistry() directamente — no usa el singleton global.
"""
import pytest
from services.action_registry import ActionRegistry


def _sample_actions():
    return [
        {
            "id": "set_scale",
            "label": "Set scale",
            "description": "Set local scale",
            "params_def": [
                {"name": "x", "type": "float", "required": True,  "default_value": None},
                {"name": "y", "type": "float", "required": True,  "default_value": None},
                {"name": "z", "type": "float", "required": True,  "default_value": None},
            ],
        },
        {
            "id": "rename_object",
            "label": "Rename",
            "description": "Rename the object",
            "params_def": [
                {"name": "name", "type": "string", "required": True, "default_value": None},
            ],
        },
        {
            "id": "set_active",
            "label": "Set active",
            "description": "Toggle active state",
            "params_def": [
                {"name": "active", "type": "bool", "required": True, "default_value": None},
            ],
        },
        {
            "id": "set_tag",
            "label": "Set tag",
            "description": "Change tag",
            "params_def": [
                {"name": "tag",       "type": "string", "required": True,  "default_value": None},
                {"name": "recursive", "type": "bool",   "required": False, "default_value": "false"},
            ],
        },
    ]


@pytest.fixture
def registry():
    r = ActionRegistry()
    r.load(_sample_actions())
    return r


# ══════════════════════════════════════════════════════════════════════════════
# CARGA
# ══════════════════════════════════════════════════════════════════════════════

class TestRegistryLoad:
    def test_known_ids_after_load(self, registry):
        ids = set(registry.known_ids())
        assert {"set_scale", "rename_object", "set_active", "set_tag"} <= ids

    def test_is_empty_before_load(self):
        r = ActionRegistry()
        assert r.is_empty()

    def test_not_empty_after_load(self, registry):
        assert not registry.is_empty()

    def test_get_returns_action(self, registry):
        defn = registry.get("set_scale")
        assert defn is not None
        assert defn["id"] == "set_scale"

    def test_get_unknown_returns_none(self, registry):
        assert registry.get("invented_action") is None

    def test_reload_replaces_catalog(self, registry):
        registry.load([{"id": "only_action", "label": "X", "params_def": []}])
        assert registry.known_ids() == ["only_action"]


# ══════════════════════════════════════════════════════════════════════════════
# VALIDACIÓN Y COERCIÓN
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateAndCoerce:
    def test_valid_float_params(self, registry):
        result, warnings = registry.validate_and_coerce(
            "set_scale", {"x": "1.5", "y": "2.0", "z": "0.5"}
        )
        assert result["x"] == pytest.approx(1.5)
        assert result["y"] == pytest.approx(2.0)
        assert warnings == []

    def test_float_already_float(self, registry):
        result, _ = registry.validate_and_coerce(
            "set_scale", {"x": 1.0, "y": 1.0, "z": 1.0}
        )
        assert isinstance(result["x"], float)

    def test_bool_coercion_from_string_true(self, registry):
        result, _ = registry.validate_and_coerce("set_active", {"active": "true"})
        assert result["active"] is True

    def test_bool_coercion_false(self, registry):
        result, _ = registry.validate_and_coerce("set_active", {"active": "0"})
        assert result["active"] is False

    def test_bool_passthrough(self, registry):
        result, _ = registry.validate_and_coerce("set_active", {"active": True})
        assert result["active"] is True

    def test_string_coercion(self, registry):
        result, _ = registry.validate_and_coerce("rename_object", {"name": 42})
        assert result["name"] == "42"

    def test_missing_required_raises(self, registry):
        with pytest.raises(ValueError, match="requerido"):
            registry.validate_and_coerce("set_scale", {"x": 1.0, "y": 1.0})  # falta z

    def test_unknown_action_raises(self, registry):
        with pytest.raises(ValueError, match="desconocida"):
            registry.validate_and_coerce("invented_action", {})

    def test_optional_with_default_used(self, registry):
        result, warnings = registry.validate_and_coerce("set_tag", {"tag": "Player"})
        assert result["recursive"] is False
        assert any("recursive" in w for w in warnings)

    def test_optional_provided_overrides_default(self, registry):
        result, _ = registry.validate_and_coerce(
            "set_tag", {"tag": "Player", "recursive": True}
        )
        assert result["recursive"] is True

    def test_invalid_float_raises(self, registry):
        with pytest.raises(ValueError):
            registry.validate_and_coerce(
                "set_scale", {"x": "not_a_number", "y": 1.0, "z": 1.0}
            )


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT BLOCK
# ══════════════════════════════════════════════════════════════════════════════

class TestPromptBlock:
    def test_empty_registry_returns_empty_string(self):
        r = ActionRegistry()
        assert r.to_prompt_block() == ""

    def test_prompt_contains_all_action_ids(self, registry):
        block = registry.to_prompt_block()
        for action_id in registry.known_ids():
            assert action_id in block

    def test_prompt_marks_required_params(self, registry):
        block = registry.to_prompt_block()
        assert "* = requerido" in block

    def test_prompt_ends_with_warning(self, registry):
        block = registry.to_prompt_block()
        assert "Nunca inventes" in block

    def test_prompt_contains_param_names(self, registry):
        block = registry.to_prompt_block()
        assert "name" in block      # param de rename_object
        assert "active" in block    # param de set_active