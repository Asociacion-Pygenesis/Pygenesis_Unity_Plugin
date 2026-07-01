"""Análisis de escena en dos pasadas (LLM)."""

import json

import pytest

from models import AnalyzeSelectionRequest, SceneObjectSummary, SceneSnapshotData
from reasoning.llm_engine import LLMEngine
from reasoning.prompts import build_scene_second_pass_prompt, scene_two_pass_enabled


def test_scene_two_pass_enabled_default_off(monkeypatch):
    monkeypatch.delenv("PYGENESIS_SCENE_TWO_PASS", raising=False)
    assert scene_two_pass_enabled() is False


def test_scene_two_pass_disabled(monkeypatch):
    monkeypatch.setenv("PYGENESIS_SCENE_TWO_PASS", "0")
    assert scene_two_pass_enabled() is False


def test_build_scene_second_pass_prompt_contains_pass2_markers():
    snap = {"scene_asset_path": "Assets/S.unity", "total_estimated": 10, "root_count": 2, "note": "n"}
    pass1 = {
        "summary": "First",
        "issues": [],
        "plan": [],
        "metadata": {"object_insights": [{"hierarchy_path": "Main Camera", "observation": "has camera"}]},
    }
    p = build_scene_second_pass_prompt("MyScene", snap, pass1)
    assert "PASS 2" in p or "pass 2" in p.lower()
    assert "Main Camera" in p
    assert "object_insights" in p or "first_pass_output" in p


class _TwoCallProvider:
    def __init__(self):
        self.calls = 0

    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if self.calls == 1:
            return json.dumps(
                {
                    "summary": "Pass one summary.",
                    "issues": [],
                    "plan": [],
                    "metadata": {
                        "object_insights": [
                            {"hierarchy_path": "R/A", "observation": "test"},
                        ]
                    },
                }
            )
        return json.dumps(
            {
                "summary": "Pass two final summary.",
                "issues": [],
                "plan": [],
                "metadata": {},
            }
        )


def test_llm_engine_analyze_scene_two_pass(monkeypatch):
    monkeypatch.setenv("PYGENESIS_SCENE_TWO_PASS", "1")
    prov = _TwoCallProvider()
    eng = LLMEngine(prov)
    req = AnalyzeSelectionRequest(
        command="analyze_scene",
        scene_name="Demo",
        scene_snapshot=SceneSnapshotData(
            root_count=1,
            total_estimated=3,
            roots=[SceneObjectSummary(name="R")],
        ),
    )
    out = eng.analyze(req)
    assert prov.calls == 2
    assert out.summary == "Pass two final summary."
    assert out.metadata.get("two_pass_scene") is True
    assert len(out.metadata.get("object_insights") or []) == 1
    assert out.metadata.get("llm_pass1_duration_ms") is not None
    assert out.metadata.get("llm_pass2_duration_ms") is not None


def test_llm_engine_analyze_scene_single_when_two_pass_env_unset(monkeypatch):
    monkeypatch.delenv("PYGENESIS_SCENE_TWO_PASS", raising=False)
    prov = _TwoCallProvider()
    eng = LLMEngine(prov)
    req = AnalyzeSelectionRequest(
        command="analyze_scene",
        scene_name="Demo",
        scene_snapshot=SceneSnapshotData(
            root_count=1,
            roots=[SceneObjectSummary(name="R")],
        ),
    )
    out = eng.analyze(req)
    assert prov.calls == 1
    assert out.summary == "Pass one summary."
    assert out.metadata.get("two_pass_scene") is False


def test_llm_engine_analyze_scene_single_when_disabled(monkeypatch):
    monkeypatch.setenv("PYGENESIS_SCENE_TWO_PASS", "0")
    prov = _TwoCallProvider()
    eng = LLMEngine(prov)
    req = AnalyzeSelectionRequest(
        command="analyze_scene",
        scene_name="Demo",
        scene_snapshot=SceneSnapshotData(
            root_count=1,
            roots=[SceneObjectSummary(name="R")],
        ),
    )
    out = eng.analyze(req)
    assert prov.calls == 1
    assert out.summary == "Pass one summary."
    assert out.metadata.get("two_pass_scene") is False


def test_llm_engine_pass2_failure_falls_back_to_pass1(monkeypatch):
    monkeypatch.setenv("PYGENESIS_SCENE_TWO_PASS", "1")

    class _BadSecond:
        def __init__(self):
            self.calls = 0

        def generate_json(self, system_prompt: str, user_prompt: str) -> str:
            self.calls += 1
            if self.calls == 1:
                return json.dumps(
                    {
                        "summary": "Only pass1",
                        "issues": [],
                        "plan": [],
                        "metadata": {"object_insights": []},
                    }
                )
            raise RuntimeError("provider down")

    eng = LLMEngine(_BadSecond())
    req = AnalyzeSelectionRequest(
        command="analyze_scene",
        scene_name="X",
        scene_snapshot=SceneSnapshotData(root_count=1, roots=[SceneObjectSummary(name="R")]),
    )
    out = eng.analyze(req)
    assert out.summary == "Only pass1"
    assert out.metadata.get("two_pass_scene") is False
    assert "two_pass_scene_error" in out.metadata
