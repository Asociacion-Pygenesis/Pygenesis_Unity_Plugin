"""Análisis de escena (command analyze_scene + scene_snapshot)."""

from models import (
    AnalyzeSelectionRequest,
    AnalyzeSelectionResponse,
    SceneObjectSummary,
    SceneSnapshotData,
)
from services.analysis_service import AnalysisService
from services.scene_validation import is_empty_scene_snapshot


def test_empty_scene_snapshot():
    assert is_empty_scene_snapshot(None) is True
    assert is_empty_scene_snapshot(SceneSnapshotData()) is True


def test_scene_snapshot_with_roots_not_empty():
    snap = SceneSnapshotData(root_count=1, roots=[SceneObjectSummary(name="Main Camera")])
    assert is_empty_scene_snapshot(snap) is False


def test_scene_snapshot_flat_sample_only_not_empty():
    from models import SceneFlatObjectInfo

    snap = SceneSnapshotData(
        root_count=0,
        total_estimated=0,
        flat_sample=[SceneFlatObjectInfo(name="X", hierarchy_path="X")],
    )
    assert is_empty_scene_snapshot(snap) is False


def test_analysis_service_analyze_scene_empty_snapshot_skips_engine():
    class NoCallEngine:
        def analyze(self, request):
            raise AssertionError("should not run")

    svc = AnalysisService(NoCallEngine())
    out = svc.analyze_selection(
        AnalyzeSelectionRequest(command="analyze_scene", scene_name="Test", scene_snapshot=None)
    )
    assert "missing" in (out.message or out.summary).lower() or "empty" in (out.message or out.summary).lower()


def test_analysis_service_analyze_scene_calls_engine():
    class CountEngine:
        def __init__(self):
            self.calls = 0

        def analyze(self, request):
            self.calls += 1
            return AnalyzeSelectionResponse(summary="ok", issues=[])

    eng = CountEngine()
    svc = AnalysisService(eng)
    snap = SceneSnapshotData(
        root_count=1,
        total_estimated=5,
        roots=[SceneObjectSummary(name="A")],
    )
    svc.analyze_selection(
        AnalyzeSelectionRequest(command="analyze_scene", scene_name="S", scene_snapshot=snap)
    )
    assert eng.calls == 1
