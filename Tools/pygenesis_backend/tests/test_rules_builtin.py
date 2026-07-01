"""Tests de reglas deterministas (build_rule_response)."""

import pytest

from models import SelectionData, TransformData
from rules.builtin import build_rule_response


def _selection(
    *,
    name: str = "MyObject",
    scale=None,
    has_collider: bool = True,
    has_renderer: bool = False,
    has_animator: bool = False,
    has_rigidbody: bool = False,
):
    if scale is None:
        scale = [1.0, 1.0, 1.0]
    return SelectionData(
        name=name,
        type="GameObject",
        has_collider=has_collider,
        has_renderer=has_renderer,
        has_animator=has_animator,
        has_rigidbody=has_rigidbody,
        transform=TransformData(
            position=[0, 0, 0],
            rotation=[0, 0, 0],
            scale=scale,
        ),
    )


def test_build_rule_response_incomplete_transform():
    sel = SelectionData(name="X", transform=None)
    out = build_rule_response(sel)
    assert "incomplete" in out.summary.lower()


def test_build_rule_response_oversized_scale_adds_issue_and_plan():
    sel = _selection(scale=[20.0, 1.0, 1.0], has_collider=True)
    out = build_rule_response(sel)
    ids = [i.issue_id for i in out.issues]
    assert "oversized_scale" in ids
    actions = [p.action for p in out.plan]
    assert "set_scale" in actions


def test_build_rule_response_generic_name_suggests_rename():
    sel = _selection(name="Cube", has_collider=True)
    out = build_rule_response(sel)
    assert any(p.action == "rename_object" for p in out.plan)


def test_build_rule_response_all_good_minimal_messages():
    sel = _selection(
        name="Hero",
        has_collider=True,
        has_renderer=True,
        has_animator=True,
        has_rigidbody=True,
    )
    out = build_rule_response(sel)
    assert len(out.plan) == 0
    assert "correct" in out.summary.lower() or len(out.summary) > 0
