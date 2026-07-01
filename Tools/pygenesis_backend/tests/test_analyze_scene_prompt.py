"""Prompts para analyze_scene: identidad de escena y workflow."""

from reasoning.prompts import build_analysis_prompt, build_refinement_prompt


def test_analysis_prompt_scene_identity_and_banner():
    snap = {
        "scene_asset_path": "Assets/Scenes/Demo.unity",
        "root_count": 1,
        "roots": [],
        "flat_sample": [],
        "note": "",
    }
    p = build_analysis_prompt({}, "Demo", "analyze_scene", snap)
    assert "scene_identity" in p
    assert "ACTIVE UNITY SCENE" in p
    assert "Demo" in p
    assert "Assets/Scenes/Demo.unity" in p
    assert "object_insights" in p


def test_refinement_prompt_includes_scene_banner():
    snap = {"scene_asset_path": "", "roots": [], "flat_sample": [], "note": ""}
    p = build_refinement_prompt({}, "X", "analyze_scene", {"summary": "s"}, snap)
    assert "ACTIVE UNITY SCENE" in p
