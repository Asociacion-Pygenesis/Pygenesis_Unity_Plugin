"""
Tests para output_validator:
  - validate_param_types con catálogo estático (sin ActionRegistry)
  - validate_param_types con external_validator inyectado
  - normalize_response: severidades, deduplicación, summary, api_version,
    legacy suggestions, acciones desconocidas, confidence clamping.
"""
import pytest

from reasoning.output_validator import (
    validate_param_types,
    normalize_response,
    normalize_issues,
    normalize_plan,
)
from models import (
    AnalyzeSelectionResponse,
    ActionStep,
    ActionTarget,
    DetectedIssue,
    ExecutionPolicy,
)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE TEST
# ══════════════════════════════════════════════════════════════════════════════

def _step(action="set_scale", params=None, step_id="step_001",
          rule_id="", confidence=1.0, safety="safe",
          can_auto_apply=True) -> ActionStep:
    return ActionStep(
        step_id=step_id,
        action=action,
        label="Test step",
        description="Test description",
        rule_id=rule_id,
        target=ActionTarget(scope="selected_object"),
        params=params if params is not None else {"x": 1.0, "y": 1.0, "z": 1.0},
        safety=safety,
        confidence=confidence,
        source="rules",
        depends_on=[],
        can_auto_apply=can_auto_apply,
    )


def _issue(issue_id="issue_001", message="Test issue",
           severity="low", confidence=1.0, title="Test") -> DetectedIssue:
    return DetectedIssue(
        issue_id=issue_id,
        title=title,
        message=message,
        severity=severity,
        category="general",
        confidence=confidence,
        source="rules",
    )


def _response(summary="Test summary", issues=None, plan=None,
              mode="rules", metadata=None) -> AnalyzeSelectionResponse:
    return AnalyzeSelectionResponse(
        summary=summary,
        issues=issues or [],
        plan=plan or [],
        mode=mode,
        metadata=metadata or {},
    )


# ══════════════════════════════════════════════════════════════════════════════
# validate_param_types — catálogo estático (sin external_validator)
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateParamTypesStatic:

    # set_scale
    def test_set_scale_valid(self):
        assert validate_param_types("set_scale", {"x": 1.0, "y": 1.0, "z": 1.0})

    def test_set_scale_int_values_valid(self):
        assert validate_param_types("set_scale", {"x": 1, "y": 2, "z": 3})

    def test_set_scale_invalid_type(self):
        assert not validate_param_types("set_scale", {"x": "one", "y": 1.0, "z": 1.0})

    def test_set_scale_missing_param(self):
        assert not validate_param_types("set_scale", {"x": 1.0, "y": 1.0})

    # rename_object
    def test_rename_object_valid(self):
        assert validate_param_types("rename_object", {"name": "Player"})

    def test_rename_object_empty_string_invalid(self):
        assert not validate_param_types("rename_object", {"name": "   "})

    def test_rename_object_missing_name_invalid(self):
        assert not validate_param_types("rename_object", {})

    # add_component / remove_component
    def test_add_component_valid(self):
        assert validate_param_types("add_component", {"component": "Rigidbody"})

    def test_add_component_missing_param_invalid(self):
        assert not validate_param_types("add_component", {})

    def test_remove_component_valid(self):
        assert validate_param_types("remove_component", {"component": "Animator"})

    # set_tag / set_layer
    def test_set_tag_valid(self):
        assert validate_param_types("set_tag", {"tag": "Player"})

    def test_set_layer_valid(self):
        assert validate_param_types("set_layer", {"layer": "Default"})

    # set_material_color
    def test_set_material_color_valid(self):
        assert validate_param_types(
            "set_material_color", {"r": 1.0, "g": 0.5, "b": 0.0, "a": 1.0}
        )

    def test_set_material_color_invalid_type(self):
        assert not validate_param_types(
            "set_material_color", {"r": "red", "g": 0.5, "b": 0.0, "a": 1.0}
        )

    # acciones sin params (legacy y nuevas)
    def test_unpack_prefab_valid(self):
        assert validate_param_types("unpack_prefab", {})

    def test_legacy_add_box_collider_valid(self):
        assert validate_param_types("add_box_collider", {})

    def test_legacy_add_rigidbody_valid(self):
        assert validate_param_types("add_rigidbody", {})

    # acción desconocida
    def test_unknown_action_returns_false(self):
        assert not validate_param_types("invented_action_xyz", {})


# ══════════════════════════════════════════════════════════════════════════════
# validate_param_types — external_validator inyectado
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateParamTypesExternal:

    def test_external_validator_used_when_provided(self):
        called = []

        def my_validator(action_id, params):
            called.append(action_id)
            return True

        result = validate_param_types("set_scale", {"x": 1.0, "y": 1.0, "z": 1.0},
                                      external_validator=my_validator)
        assert result is True
        assert "set_scale" in called

    def test_external_validator_can_reject(self):
        def strict_validator(action_id, params):
            return False

        result = validate_param_types("set_scale", {"x": 1.0, "y": 1.0, "z": 1.0},
                                      external_validator=strict_validator)
        assert result is False

    def test_external_validator_exception_falls_back_to_static(self):
        def broken_validator(action_id, params):
            raise RuntimeError("registry unavailable")

        # set_scale con params válidos → static fallback devuelve True
        result = validate_param_types("set_scale", {"x": 1.0, "y": 1.0, "z": 1.0},
                                      external_validator=broken_validator)
        assert result is True

    def test_external_validator_exception_static_rejects_bad_params(self):
        def broken_validator(action_id, params):
            raise RuntimeError("registry unavailable")

        # set_scale con tipo inválido → static fallback devuelve False
        result = validate_param_types("set_scale", {"x": "bad", "y": 1.0, "z": 1.0},
                                      external_validator=broken_validator)
        assert result is False

    def test_none_external_validator_uses_static(self):
        result = validate_param_types("set_scale", {"x": 1.0, "y": 1.0, "z": 1.0},
                                      external_validator=None)
        assert result is True


# ══════════════════════════════════════════════════════════════════════════════
# normalize_response — comportamiento completo
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizeResponse:

    def test_api_version_always_40(self):
        result = normalize_response(_response())
        assert result.api_version == "4.0"

    def test_mode_preserved(self):
        result = normalize_response(_response(mode="hybrid"))
        assert result.mode == "hybrid"

    def test_mode_defaults_to_rules_when_empty(self):
        resp = _response()
        resp.mode = ""
        result = normalize_response(resp)
        assert result.mode == "rules"

    def test_summary_preserved(self):
        result = normalize_response(_response(summary="All good."))
        assert result.summary == "All good."

    def test_empty_summary_gets_default_no_issues(self):
        result = normalize_response(_response(summary=""))
        assert result.summary == "No issues detected."

    def test_empty_summary_gets_default_with_issues(self):
        result = normalize_response(_response(summary="", issues=[_issue()]))
        assert "issues" in result.summary.lower()

    def test_message_fallback_for_summary(self):
        resp = AnalyzeSelectionResponse(
            summary="",
            message="Fallback message.",
            issues=[],
            plan=[],
            metadata={},
        )
        result = normalize_response(resp)
        assert result.summary == "Fallback message."

    def test_unknown_action_stripped_from_plan(self):
        step = _step(action="invented_action_xyz", params={})
        result = normalize_response(_response(plan=[step]))
        assert all(s.action != "invented_action_xyz" for s in result.plan)

    def test_valid_action_kept_in_plan(self):
        step = _step(action="set_scale", params={"x": 1.0, "y": 1.0, "z": 1.0})
        result = normalize_response(_response(plan=[step]))
        assert any(s.action == "set_scale" for s in result.plan)

    def test_invalid_severity_normalized_to_low(self):
        issue = _issue(severity="extreme")
        result = normalize_response(_response(issues=[issue]))
        assert result.issues[0].severity == "low"

    def test_valid_severity_preserved(self):
        for sev in ("info", "low", "medium", "high", "critical"):
            issue = _issue(severity=sev)
            result = normalize_response(_response(issues=[issue]))
            assert result.issues[0].severity == sev

    def test_issue_without_message_dropped(self):
        issue = _issue(message="")
        result = normalize_response(_response(issues=[issue]))
        assert result.issues == []

    def test_issue_without_issue_id_dropped(self):
        issue = _issue(issue_id="")
        result = normalize_response(_response(issues=[issue]))
        assert result.issues == []

    def test_duplicate_issues_deduped(self):
        i1 = _issue(issue_id="dupe", message="Same issue")
        i2 = _issue(issue_id="dupe", message="Same issue")
        result = normalize_response(_response(issues=[i1, i2]))
        assert len(result.issues) == 1

    def test_duplicate_plan_steps_deduped(self):
        s1 = _step(params={"x": 1.0, "y": 1.0, "z": 1.0})
        s2 = _step(params={"x": 1.0, "y": 1.0, "z": 1.0})
        result = normalize_response(_response(plan=[s1, s2]))
        assert len(result.plan) == 1

    def test_confidence_clamped_above_1(self):
        issue = _issue(confidence=1.5)
        result = normalize_response(_response(issues=[issue]))
        assert result.issues[0].confidence <= 1.0

    def test_confidence_clamped_below_0(self):
        issue = _issue(confidence=-0.5)
        result = normalize_response(_response(issues=[issue]))
        assert result.issues[0].confidence >= 0.0

    def test_non_numeric_confidence_defaults_to_1(self):
        issue = _issue(confidence="high")  # type: ignore
        result = normalize_response(_response(issues=[issue]))
        assert result.issues[0].confidence == 1.0

    def test_legacy_suggestions_built_from_plan(self):
        step = _step(action="set_scale", params={"x": 1.0, "y": 1.0, "z": 1.0})
        result = normalize_response(_response(plan=[step]))
        assert len(result.suggestions) == 1
        assert result.suggestions[0].action == "set_scale"

    def test_max_issues_cap(self):
        issues = [_issue(issue_id=f"issue_{i}", message=f"msg {i}") for i in range(30)]
        result = normalize_response(_response(issues=issues))
        assert len(result.issues) <= 20

    def test_max_plan_steps_cap(self):
        steps = [
            _step(step_id=f"step_{i:03d}", params={"x": float(i), "y": 1.0, "z": 1.0})
            for i in range(25)
        ]
        result = normalize_response(_response(plan=steps))
        assert len(result.plan) <= 20

    def test_metadata_preserved(self):
        meta = {"engine": "hybrid", "llm_duration_ms": 123}
        result = normalize_response(_response(metadata=meta))
        assert result.metadata["engine"] == "hybrid"
        assert result.metadata["llm_duration_ms"] == 123

    def test_non_dict_metadata_replaced_with_empty(self):
        resp = _response()
        resp.metadata = "invalid"  # type: ignore
        result = normalize_response(resp)
        assert isinstance(result.metadata, dict)

    def test_param_validator_injected_and_used(self):
        """external_validator rechaza todo → step válido estáticamente igual se descarta."""
        def reject_all(action_id, params):
            return False

        step = _step(action="set_scale", params={"x": 1.0, "y": 1.0, "z": 1.0})
        result = normalize_response(_response(plan=[step]), param_validator=reject_all)
        assert result.plan == []

    def test_param_validator_none_uses_static(self):
        """Sin external_validator, el catálogo estático acepta set_scale válido."""
        step = _step(action="set_scale", params={"x": 1.0, "y": 1.0, "z": 1.0})
        result = normalize_response(_response(plan=[step]), param_validator=None)
        assert any(s.action == "set_scale" for s in result.plan)


# ══════════════════════════════════════════════════════════════════════════════
# normalize_execution_policy
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizeExecutionPolicy:

    def test_none_policy_returns_default(self):
        resp = _response()
        resp.execution_policy = None  # type: ignore
        result = normalize_response(resp)
        assert result.execution_policy is not None

    def test_max_auto_apply_clamped_to_20(self):
        resp = _response()
        resp.execution_policy = ExecutionPolicy(
            requires_user_confirmation=False,
            max_auto_apply_steps=999,
            allow_partial_execution=True,
        )
        result = normalize_response(resp)
        assert result.execution_policy.max_auto_apply_steps <= 20

    def test_max_auto_apply_clamped_to_0(self):
        resp = _response()
        resp.execution_policy = ExecutionPolicy(
            requires_user_confirmation=False,
            max_auto_apply_steps=-5,
            allow_partial_execution=True,
        )
        result = normalize_response(resp)
        assert result.execution_policy.max_auto_apply_steps >= 0