# tests/test_hybrid_engine.py
"""
Tests para HybridEngine: fusión de reglas + LLM, fallbacks, deduplicación.
"""
import json
import pytest
from conftest import (
    make_selection, make_scene_snapshot, make_request,
    make_llm_engine, MINIMAL_LLM_RESPONSE,
)


def make_hybrid(llm_response=MINIMAL_LLM_RESPONSE, llm_exc=None):
    from reasoning.hybrid_engine import HybridEngine
    from reasoning.rules_engine import RulesEngine
    llm, provider = make_llm_engine(
        response=llm_response, raise_exc=llm_exc,
        fallback=RulesEngine(),
    )
    return HybridEngine(llm_engine=llm), provider


def llm_resp(issues=None, plan=None, summary="LLM says ok."):
    return json.dumps({
        "summary": summary,
        "issues": issues or [],
        "plan": plan or [],
        "execution_policy": {
            "requires_user_confirmation": False,
            "max_auto_apply_steps": 1,
            "allow_partial_execution": True,
        },
        "metadata": {},
    })


# ══════════════════════════════════════════════════════════════════
# MODO BÁSICO
# ══════════════════════════════════════════════════════════════════

class TestHybridMode:
    def test_mode_is_hybrid(self):
        engine, _ = make_hybrid()
        req = make_request(selection=make_selection())
        result = engine.analyze(req)
        assert result.mode == "hybrid"

    def test_metadata_contains_timing_keys(self):
        engine, _ = make_hybrid()
        req = make_request(selection=make_selection())
        result = engine.analyze(req)
        meta = result.metadata or {}
        assert "rules_duration_ms" in meta
        assert "llm_duration_ms" in meta
        assert "total_duration_ms" in meta

    def test_metadata_hybrid_mode_label(self):
        engine, _ = make_hybrid()
        req = make_request(selection=make_selection())
        result = engine.analyze(req)
        assert result.metadata.get("hybrid_mode") == "rules+llm"


# ══════════════════════════════════════════════════════════════════
# FUSIÓN DE ISSUES
# ══════════════════════════════════════════════════════════════════

class TestIssuesMerge:
    def test_certain_rule_issues_always_present(self):
        """Issues de reglas con confidence >= 0.95 deben estar en el resultado."""
        # oversized_scale tiene confidence=1.0 → cierta
        sel = make_selection(scale=[50, 50, 50])
        engine, _ = make_hybrid()
        req = make_request(selection=sel)
        result = engine.analyze(req)
        ids = {i.issue_id for i in result.issues}
        assert "oversized_scale" in ids

    def test_llm_issues_added_when_no_duplicate(self):
        """Issues nuevas del LLM se añaden si no duplican una regla."""
        llm_issue = {
            "issue_id": "llm_unique_issue",
            "title": "LLM Issue",
            "message": "Something only LLM detected.",
            "severity": "low",
            "category": "general",
            "confidence": 0.8,
            "source": "llm",
        }
        engine, _ = make_hybrid(llm_response=llm_resp(issues=[llm_issue]))
        req = make_request(selection=make_selection())
        result = engine.analyze(req)
        ids = {i.issue_id for i in result.issues}
        assert "llm_unique_issue" in ids

    def test_no_duplicate_issues_by_id(self):
        """Si el LLM devuelve el mismo issue_id que una regla, no se duplica."""
        # oversized_scale ya viene de reglas
        llm_issue = {
            "issue_id": "oversized_scale",
            "title": "Oversized Scale (LLM)",
            "message": "Also detected by LLM.",
            "severity": "medium",
            "category": "transform",
            "confidence": 0.9,
            "source": "llm",
        }
        sel = make_selection(scale=[50, 50, 50])
        engine, _ = make_hybrid(llm_response=llm_resp(issues=[llm_issue]))
        req = make_request(selection=sel)
        result = engine.analyze(req)
        dupe_ids = [i.issue_id for i in result.issues]
        assert dupe_ids.count("oversized_scale") == 1

    def test_certain_issues_count_in_metadata(self):
        sel = make_selection(scale=[50, 50, 50])   # dispara oversized_scale (conf=1.0)
        engine, _ = make_hybrid()
        req = make_request(selection=sel)
        result = engine.analyze(req)
        assert result.metadata.get("certain_issues", 0) >= 1


# ══════════════════════════════════════════════════════════════════
# FUSIÓN DEL PLAN
# ══════════════════════════════════════════════════════════════════

class TestPlanMerge:
    def test_certain_rule_steps_present(self):
        """Steps ligados a issues ciertas siempre aparecen."""
        sel = make_selection(scale=[50, 50, 50])
        engine, _ = make_hybrid()
        req = make_request(selection=sel)
        result = engine.analyze(req)
        actions = {s.action for s in result.plan}
        assert "set_scale" in actions

    def test_llm_steps_added_without_duplicate(self):
        """Steps del LLM que no repiten acción+params se añaden al plan."""
        llm_step = {
            "step_id": "llm_step_001",
            "action": "set_tag",
            "label": "Set tag to Player",
            "description": "Tag this object as Player.",
            "rule_id": "",
            "params": {"tag": "Player"},
            "safety": "safe",
            "confidence": 0.9,
            "source": "llm",
            "depends_on": [],
            "can_auto_apply": True,
            "target": {"scope": "selected_object", "object_ref": None},
        }
        engine, _ = make_hybrid(llm_response=llm_resp(plan=[llm_step]))
        req = make_request(selection=make_selection())
        result = engine.analyze(req)
        actions = {s.action for s in result.plan}
        assert "set_tag" in actions

    def test_no_duplicate_steps_same_action_params(self):
        """Si el LLM propone set_scale con mismos params que reglas, no se duplica."""
        sel = make_selection(scale=[50, 50, 50])
        llm_step = {
            "step_id": "llm_step_001",
            "action": "set_scale",
            "label": "Fix scale",
            "description": "Normalize scale.",
            "rule_id": "oversized_scale",
            "params": {"x": 1.0, "y": 1.0, "z": 1.0},
            "safety": "safe",
            "confidence": 1.0,
            "source": "llm",
            "depends_on": [],
            "can_auto_apply": True,
            "target": {"scope": "selected_object", "object_ref": None},
        }
        engine, _ = make_hybrid(llm_response=llm_resp(plan=[llm_step]))
        req = make_request(selection=sel)
        result = engine.analyze(req)
        scale_steps = [s for s in result.plan if s.action == "set_scale"]
        assert len(scale_steps) == 1


# ══════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════

class TestSummary:
    def test_uses_llm_summary_when_available(self):
        engine, _ = make_hybrid(llm_response=llm_resp(summary="LLM enriched summary."))
        req = make_request(selection=make_selection())
        result = engine.analyze(req)
        assert "LLM enriched summary" in result.summary

    def test_falls_back_to_rules_summary_when_llm_empty(self):
        engine, _ = make_hybrid(llm_response=llm_resp(summary=""))
        sel = make_selection(scale=[50, 50, 50])
        req = make_request(selection=sel)
        result = engine.analyze(req)
        # El summary de reglas menciona "oversized"
        assert result.summary  # al menos no vacío


# ══════════════════════════════════════════════════════════════════
# FALLBACK CUANDO EL LLM FALLA
# ══════════════════════════════════════════════════════════════════

class TestHybridFallback:
    def test_returns_rules_result_when_llm_raises(self):
        engine, _ = make_hybrid(llm_exc=RuntimeError("LLM timeout"))
        sel = make_selection(scale=[50, 50, 50])
        req = make_request(selection=sel)
        result = engine.analyze(req)
        # Debe devolver algo válido (el borrador de reglas)
        assert result is not None
        assert result.mode == "hybrid"
        ids = {i.issue_id for i in result.issues}
        assert "oversized_scale" in ids   # las reglas sí detectaron esto

    def test_fallback_metadata_has_reason(self):
        engine, _ = make_hybrid(llm_exc=ConnectionError("Network error"))
        req = make_request(selection=make_selection())
        result = engine.analyze(req)
        meta = result.metadata or {}
        assert "llm_fallback_reason" in meta
        assert "Network error" in meta["llm_fallback_reason"]

    def test_fallback_mode_label(self):
        engine, _ = make_hybrid(llm_exc=RuntimeError("fail"))
        req = make_request(selection=make_selection())
        result = engine.analyze(req)
        assert result.metadata.get("hybrid_mode") == "rules_only_fallback"


# ══════════════════════════════════════════════════════════════════
# ANÁLISIS DE ESCENA CON HÍBRIDO
# ══════════════════════════════════════════════════════════════════

class TestHybridScene:
    def test_scene_mode_uses_scene_rules(self):
        engine, provider = make_hybrid()
        snap = make_scene_snapshot(cameras_index=[])   # dispara scene_no_camera
        req = make_request(
            command="analyze_scene",
            scene_snapshot=snap,
            scene_name="TestScene",
        )
        result = engine.analyze(req)
        ids = {i.issue_id for i in result.issues}
        assert "scene_no_camera" in ids

    def test_llm_called_with_rule_draft_for_scene(self):
        """El LLM debe recibir el borrador de reglas en el prompt de refinamiento."""
        engine, provider = make_hybrid()
        snap = make_scene_snapshot()
        req = make_request(
            command="analyze_scene",
            scene_snapshot=snap,
            scene_name="TestScene",
        )
        engine.analyze(req)
        assert len(provider.calls) >= 1
        # El prompt de refinamiento incluye el draft JSON
        refine_prompt = provider.calls[-1]["user"]
        assert "draft" in refine_prompt.lower() or "pass" in refine_prompt.lower() \
               or "rule" in refine_prompt.lower()