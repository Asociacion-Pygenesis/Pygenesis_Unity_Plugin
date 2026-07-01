from __future__ import annotations
from dataclasses import dataclass, field
from models import AnalyzeSelectionResponse, ActionStep, ActionTarget, DetectedIssue


# ══════════════════════════════════════════════════════════════════
# TIPOS INTERNOS
# ══════════════════════════════════════════════════════════════════

@dataclass
class RuleResult:
    """Resultado de evaluar un conjunto de reglas. Acumulable."""
    issues: list[DetectedIssue] = field(default_factory=list)
    plan:   list[ActionStep]    = field(default_factory=list)
    notes:  list[str]           = field(default_factory=list)   # para el summary

    def merge(self, other: "RuleResult") -> None:
        self.issues.extend(other.issues)
        self.plan.extend(other.plan)
        self.notes.extend(other.notes)


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def _issue(issue_id, title, message, severity, category, confidence=1.0) -> DetectedIssue:
    return DetectedIssue(
        issue_id=issue_id, title=title, message=message,
        severity=severity, category=category,
        confidence=confidence, source="rules",
    )

def _step(step_id, action, label, description, params,
          rule_id, safety="safe", confidence=1.0,
          scope="selected_object", can_auto_apply=True) -> ActionStep:
    return ActionStep(
        step_id=step_id, action=action, label=label,
        description=description, rule_id=rule_id,
        target=ActionTarget(scope=scope),
        params=params, safety=safety,
        confidence=confidence, source="rules",
        depends_on=[], can_auto_apply=can_auto_apply,
    )


# ══════════════════════════════════════════════════════════════════
# REGLAS DE SELECCIÓN
# ══════════════════════════════════════════════════════════════════

_GENERIC_NAMES = {
    "GameObject", "Cube", "Sphere", "Capsule",
    "Cylinder", "Plane", "Quad", "Empty",
}

def _rules_transform(sel) -> RuleResult:
    r = RuleResult()
    if sel.transform is None or len(sel.transform.scale) < 3:
        return r
    sx, sy, sz = sel.transform.scale

    if sx > 10 or sy > 10 or sz > 10:
        r.issues.append(_issue(
            "oversized_scale", "Oversized Scale",
            f"Scale ({sx:.1f}, {sy:.1f}, {sz:.1f}) is very large.",
            "medium", "transform",
        ))
        r.plan.append(_step(
            "step_fix_scale", "set_scale", "Normalize scale to (1,1,1)",
            "Reset local scale to (1, 1, 1).",
            {"x": 1.0, "y": 1.0, "z": 1.0}, "oversized_scale",
        ))
        r.notes.append("Object is oversized.")

    # Escala no uniforme en objetos con collider: puede causar problemas de física
    if sel.has_collider and len({round(sx, 2), round(sy, 2), round(sz, 2)}) > 1:
        r.issues.append(_issue(
            "non_uniform_scale_collider",
            "Non-uniform Scale with Collider",
            f"Scale ({sx:.2f}, {sy:.2f}, {sz:.2f}) is non-uniform on an object with a Collider. "
            "This can cause physics artifacts.",
            "medium", "physics", confidence=0.9,
        ))
        r.notes.append("Non-uniform scale with Collider detected.")

    return r


def _rules_physics(sel) -> RuleResult:
    r = RuleResult()

    if not sel.has_collider:
        r.issues.append(_issue(
            "missing_collider", "Missing Collider",
            "Object has no Collider component.",
            "medium", "physics",
        ))
        r.plan.append(_step(
            "step_add_box_collider", "add_component",
            "Add BoxCollider",
            "Add a BoxCollider to enable collision detection.",
            {"component": "BoxCollider"}, "missing_collider",
        ))
        r.notes.append("Missing Collider.")

    if sel.has_renderer and sel.has_collider and not sel.has_rigidbody:
        r.issues.append(_issue(
            "missing_rigidbody", "Missing Rigidbody",
            "Object has Renderer and Collider but no Rigidbody.",
            "medium", "physics",
        ))
        r.plan.append(_step(
            "step_add_rigidbody", "add_component",
            "Add Rigidbody",
            "Add a Rigidbody to enable physics simulation.",
            {"component": "Rigidbody"}, "missing_rigidbody",
        ))
        r.notes.append("Missing Rigidbody.")

    return r


def _rules_animation(sel) -> RuleResult:
    r = RuleResult()

    if sel.has_renderer and not sel.has_animator:
        r.issues.append(_issue(
            "missing_animator", "Missing Animator",
            "Object has a Renderer but no Animator component.",
            "low", "animation", confidence=0.8,
        ))
        r.plan.append(_step(
            "step_add_animator", "add_component",
            "Add Animator",
            "Add an Animator component for animation support.",
            {"component": "Animator"}, "missing_animator",
            safety="review", confidence=0.8,
        ))
        r.notes.append("Renderer without Animator.")

    return r


def _rules_naming(sel) -> RuleResult:
    r = RuleResult()
    name = getattr(sel, "name", "") or ""

    if name in _GENERIC_NAMES:
        suggested = f"{name}_Object"
        r.issues.append(_issue(
            "generic_name", "Generic Name",
            f"'{name}' is a generic Unity default name.",
            "low", "naming", confidence=0.95,
        ))
        r.plan.append(_step(
            "step_rename_selected", "rename_object",
            f"Rename to {suggested}",
            "Give the object a descriptive name.",
            {"name": suggested}, "generic_name",
        ))
        r.notes.append("Generic name detected.")

    return r


def _rules_static(sel) -> RuleResult:
    """Objetos marcados como estáticos pero con Rigidbody (conflicto Unity)."""
    r = RuleResult()
    is_static = getattr(sel, "is_static", False)

    if is_static and sel.has_rigidbody:
        r.issues.append(_issue(
            "static_with_rigidbody", "Static Object with Rigidbody",
            "Object is marked Static but has a Rigidbody. "
            "Unity ignores physics on static objects; this wastes memory.",
            "high", "physics", confidence=0.95,
        ))
        r.plan.append(_step(
            "step_remove_rigidbody", "remove_component",
            "Remove Rigidbody from static object",
            "Static objects should not have a Rigidbody.",
            {"component": "Rigidbody"}, "static_with_rigidbody",
            safety="review",
        ))
        r.notes.append("Static object with Rigidbody (conflict).")

    return r


def build_rule_response(selection) -> AnalyzeSelectionResponse:
    """Punto de entrada para análisis de selección por reglas."""
    if selection is None or selection.transform is None:
        return AnalyzeSelectionResponse(
            mode="rules",
            summary="Selected object data is incomplete.",
            issues=[], plan=[],
            metadata={"engine": "rule_based"},
        )

    result = RuleResult()
    for rule_fn in [
        _rules_transform,
        _rules_physics,
        _rules_animation,
        _rules_naming,
        _rules_static,
    ]:
        result.merge(rule_fn(selection))

    summary = " ".join(result.notes) if result.notes else "The selected object looks correct."

    return AnalyzeSelectionResponse(
        mode="rules",
        summary=summary,
        issues=result.issues,
        plan=result.plan,
        metadata={"engine": "rule_based", "rules_fired": len(result.issues)},
    )


# ══════════════════════════════════════════════════════════════════
# REGLAS DE ESCENA
# ══════════════════════════════════════════════════════════════════

def _scene_rules_lighting(snap: dict) -> RuleResult:
    r = RuleResult()
    lights = snap.get("lights_index") or []

    if not lights:
        r.issues.append(_issue(
            "scene_no_lights", "No Lights in Scene",
            "The scene has no Light components. Objects may render flat or black.",
            "high", "lighting",
        ))
        r.notes.append("No lights found.")
        return r

    # Detectar realtime lights excesivas (coste GPU)
    realtime = [
        l for l in lights
        if isinstance(l, dict)
        and (l.get("light_inspector") or {}).get("bake_type", "").lower() == "realtime"
    ]
    if len(realtime) > 4:
        r.issues.append(_issue(
            "too_many_realtime_lights", "Too Many Realtime Lights",
            f"{len(realtime)} realtime lights found. "
            "Consider baking some to reduce GPU cost.",
            "medium", "performance", confidence=0.85,
        ))
        r.notes.append(f"{len(realtime)} realtime lights (possible perf issue).")

    return r


def _scene_rules_cameras(snap: dict) -> RuleResult:
    r = RuleResult()
    cameras = snap.get("cameras_index") or []

    if not cameras:
        r.issues.append(_issue(
            "scene_no_camera", "No Camera in Scene",
            "The scene has no Camera. Nothing will render at runtime.",
            "critical", "camera",
        ))
        r.notes.append("No camera found.")
        return r

    # Múltiples cámaras activas sin depth ordering explícito
    if len(cameras) > 1:
        depths = [
            c.get("camera_inspector", {}).get("depth")
            for c in cameras
            if isinstance(c, dict)
        ]
        unique_depths = {d for d in depths if d is not None}
        if len(unique_depths) < len(cameras):
            r.issues.append(_issue(
                "cameras_same_depth", "Cameras with Duplicate Depth",
                f"{len(cameras)} cameras found with non-unique depths. "
                "This causes undefined render order.",
                "medium", "camera", confidence=0.9,
            ))

    return r


def _scene_rules_hierarchy(snap: dict) -> RuleResult:
    r = RuleResult()
    roots = snap.get("roots") or []
    total = snap.get("total_estimated") or 0

    # Escena muy plana (todo en la raíz)
    if len(roots) > 30 and total > 0:
        flat_ratio = len(roots) / total
        if flat_ratio > 0.7:
            r.issues.append(_issue(
                "flat_hierarchy", "Flat Hierarchy",
                f"{len(roots)} root objects out of ~{total} total. "
                "Consider grouping objects into logical parents.",
                "low", "organization", confidence=0.8,
            ))
            r.notes.append("Scene hierarchy is very flat.")

    # Escena muy grande
    if total > 500:
        r.issues.append(_issue(
            "large_scene", "Large Scene",
            f"~{total} GameObjects estimated. Large scenes can slow down the editor.",
            "low", "performance", confidence=0.75,
        ))

    return r


def _scene_rules_naming(snap: dict) -> RuleResult:
    """Detecta raíces con nombres genéricos."""
    r = RuleResult()
    roots = snap.get("roots") or []
    generic = [
        obj.get("name", "") for obj in roots
        if isinstance(obj, dict) and obj.get("name", "") in _GENERIC_NAMES
    ]
    if generic:
        names_str = ", ".join(f"'{n}'" for n in generic[:5])
        r.issues.append(_issue(
            "scene_generic_names", "Generic Root Names",
            f"Root objects with generic names: {names_str}.",
            "low", "naming", confidence=0.9,
        ))
    return r


def build_scene_rule_response(scene_snapshot: dict, scene_name: str) -> AnalyzeSelectionResponse:
    """Punto de entrada para análisis de escena por reglas."""
    result = RuleResult()
    for rule_fn in [
        _scene_rules_lighting,
        _scene_rules_cameras,
        _scene_rules_hierarchy,
        _scene_rules_naming,
    ]:
        result.merge(rule_fn(scene_snapshot))

    summary = (
        f"Scene '{scene_name}': " + " ".join(result.notes)
        if result.notes
        else f"Scene '{scene_name}' looks correct at a glance."
    )

    return AnalyzeSelectionResponse(
        mode="rules",
        summary=summary,
        issues=result.issues,
        plan=result.plan,
        metadata={
            "engine": "rule_based",
            "rules_fired": len(result.issues),
            "scene_name": scene_name,
        },
    )