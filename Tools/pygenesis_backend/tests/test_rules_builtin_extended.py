# tests/test_rules_builtin_extended.py
"""
Tests para las reglas añadidas en esta sesión:
- Escala no uniforme con Collider
- Objeto estático con Rigidbody
- Reglas de escena (cámara, luces, jerarquía, nombres)
"""
import pytest
from conftest import make_selection, make_scene_snapshot
from rules.builtin import build_rule_response, build_scene_rule_response


# ══════════════════════════════════════════════════════════════════
# REGLAS DE SELECCIÓN — nuevas
# ══════════════════════════════════════════════════════════════════

class TestNonUniformScaleWithCollider:
    def test_fires_when_non_uniform_and_has_collider(self):
        sel = make_selection(has_collider=True, scale=[1, 2, 1])
        r = build_rule_response(sel)
        ids = {i.issue_id for i in r.issues}
        assert "non_uniform_scale_collider" in ids

    def test_does_not_fire_when_uniform(self):
        sel = make_selection(has_collider=True, scale=[2, 2, 2])
        r = build_rule_response(sel)
        ids = {i.issue_id for i in r.issues}
        assert "non_uniform_scale_collider" not in ids

    def test_does_not_fire_without_collider(self):
        sel = make_selection(has_collider=False, scale=[1, 2, 3])
        r = build_rule_response(sel)
        ids = {i.issue_id for i in r.issues}
        assert "non_uniform_scale_collider" not in ids

    def test_severity_is_medium(self):
        sel = make_selection(has_collider=True, scale=[1, 3, 1])
        r = build_rule_response(sel)
        issue = next(i for i in r.issues if i.issue_id == "non_uniform_scale_collider")
        assert issue.severity == "medium"


class TestStaticWithRigidbody:
    def test_fires_when_static_and_has_rigidbody(self):
        sel = make_selection(is_static=True, has_rigidbody=True)
        r = build_rule_response(sel)
        ids = {i.issue_id for i in r.issues}
        assert "static_with_rigidbody" in ids

    def test_plan_suggests_remove_rigidbody(self):
        sel = make_selection(is_static=True, has_rigidbody=True)
        r = build_rule_response(sel)
        actions = {s.action for s in r.plan}
        assert "remove_component" in actions

    def test_does_not_fire_when_not_static(self):
        sel = make_selection(is_static=False, has_rigidbody=True)
        r = build_rule_response(sel)
        ids = {i.issue_id for i in r.issues}
        assert "static_with_rigidbody" not in ids

    def test_severity_is_high(self):
        sel = make_selection(is_static=True, has_rigidbody=True)
        r = build_rule_response(sel)
        issue = next(i for i in r.issues if i.issue_id == "static_with_rigidbody")
        assert issue.severity == "high"


class TestPhysicsRulesAddComponent:
    """Las reglas de física ahora usan add_component en lugar de add_box_collider."""
    def test_missing_collider_uses_add_component(self):
        sel = make_selection(has_collider=False)
        r = build_rule_response(sel)
        collider_steps = [s for s in r.plan if s.action == "add_component"
                          and s.params.get("component") == "BoxCollider"]
        assert len(collider_steps) == 1

    def test_missing_rigidbody_uses_add_component(self):
        sel = make_selection(has_collider=True, has_renderer=True, has_rigidbody=False)
        r = build_rule_response(sel)
        rb_steps = [s for s in r.plan if s.action == "add_component"
                    and s.params.get("component") == "Rigidbody"]
        assert len(rb_steps) == 1


class TestCleanObject:
    def test_no_issues_for_clean_object(self):
        sel = make_selection(
            name="Player",
            has_collider=True, has_renderer=True,
            has_rigidbody=True, is_static=False,
            scale=[1, 1, 1],
        )
        r = build_rule_response(sel)
        assert r.issues == []
        assert "looks correct" in r.summary.lower()


# ══════════════════════════════════════════════════════════════════
# REGLAS DE ESCENA
# ══════════════════════════════════════════════════════════════════

class TestSceneRulesLighting:
    def test_no_lights_is_high_severity(self):
        snap = make_scene_snapshot(lights_index=[])
        r = build_scene_rule_response(snap.model_dump(mode="json"), "Test")
        ids = {i.issue_id for i in r.issues}
        assert "scene_no_lights" in ids
        issue = next(i for i in r.issues if i.issue_id == "scene_no_lights")
        assert issue.severity == "high"

    def test_too_many_realtime_lights(self):
        lights = [
            {"name": f"Light{i}", "hierarchy_path": f"Light{i}",
             "light_inspector": {"bake_type": "realtime", "light_type": "Point"}}
            for i in range(6)
        ]
        snap = make_scene_snapshot(lights_index=lights)
        r = build_scene_rule_response(snap.model_dump(mode="json"), "Test")
        ids = {i.issue_id for i in r.issues}
        assert "too_many_realtime_lights" in ids

    def test_acceptable_light_count_no_issue(self):
        lights = [
            {"name": f"Light{i}", "hierarchy_path": f"Light{i}",
             "light_inspector": {"bake_type": "realtime", "light_type": "Point"}}
            for i in range(3)
        ]
        snap = make_scene_snapshot(lights_index=lights)
        r = build_scene_rule_response(snap.model_dump(mode="json"), "Test")
        ids = {i.issue_id for i in r.issues}
        assert "too_many_realtime_lights" not in ids


class TestSceneRulesCameras:
    def test_no_camera_is_critical(self):
        snap = make_scene_snapshot(cameras_index=[])
        r = build_scene_rule_response(snap.model_dump(mode="json"), "Test")
        ids = {i.issue_id for i in r.issues}
        assert "scene_no_camera" in ids
        issue = next(i for i in r.issues if i.issue_id == "scene_no_camera")
        assert issue.severity == "critical"

    def test_duplicate_depth_flagged(self):
        cameras = [
            {"name": "Cam1", "hierarchy_path": "Cam1",
             "camera_inspector": {"depth": 0}},
            {"name": "Cam2", "hierarchy_path": "Cam2",
             "camera_inspector": {"depth": 0}},   # mismo depth
        ]
        snap = make_scene_snapshot(cameras_index=cameras)
        r = build_scene_rule_response(snap.model_dump(mode="json"), "Test")
        ids = {i.issue_id for i in r.issues}
        assert "cameras_same_depth" in ids

    def test_unique_depths_no_issue(self):
        cameras = [
            {"name": "Cam1", "hierarchy_path": "Cam1",
             "camera_inspector": {"depth": 0}},
            {"name": "Cam2", "hierarchy_path": "Cam2",
             "camera_inspector": {"depth": 1}},
        ]
        snap = make_scene_snapshot(cameras_index=cameras)
        r = build_scene_rule_response(snap.model_dump(mode="json"), "Test")
        ids = {i.issue_id for i in r.issues}
        assert "cameras_same_depth" not in ids


class TestSceneRulesHierarchy:
    def test_flat_hierarchy_flagged(self):
        # 35 raíces de 40 totales → ratio > 0.7
        roots = [{"name": f"Object{i}", "hierarchy_path": f"Object{i}"}
                 for i in range(35)]
        snap = make_scene_snapshot(
            roots=roots, root_count=35, total_estimated=40,
            lights_index=[{"name": "L", "hierarchy_path": "L",
                           "light_inspector": {"bake_type": "realtime"}}],
        )
        r = build_scene_rule_response(snap.model_dump(mode="json"), "Test")
        ids = {i.issue_id for i in r.issues}
        assert "flat_hierarchy" in ids

    def test_large_scene_flagged(self):
        snap = make_scene_snapshot(total_estimated=600)
        r = build_scene_rule_response(snap.model_dump(mode="json"), "Test")
        ids = {i.issue_id for i in r.issues}
        assert "large_scene" in ids

    def test_small_scene_no_large_issue(self):
        snap = make_scene_snapshot(total_estimated=30)
        r = build_scene_rule_response(snap.model_dump(mode="json"), "Test")
        ids = {i.issue_id for i in r.issues}
        assert "large_scene" not in ids


class TestSceneRulesNaming:
    def test_generic_root_name_flagged(self):
        roots = [
            {"name": "Cube", "hierarchy_path": "Cube"},
            {"name": "Player", "hierarchy_path": "Player"},
        ]
        snap = make_scene_snapshot(roots=roots)
        r = build_scene_rule_response(snap.model_dump(mode="json"), "Test")
        ids = {i.issue_id for i in r.issues}
        assert "scene_generic_names" in ids

    def test_no_generic_names_no_issue(self):
        roots = [
            {"name": "Player", "hierarchy_path": "Player"},
            {"name": "EnemySpawner", "hierarchy_path": "EnemySpawner"},
        ]
        snap = make_scene_snapshot(roots=roots)
        r = build_scene_rule_response(snap.model_dump(mode="json"), "Test")
        ids = {i.issue_id for i in r.issues}
        assert "scene_generic_names" not in ids