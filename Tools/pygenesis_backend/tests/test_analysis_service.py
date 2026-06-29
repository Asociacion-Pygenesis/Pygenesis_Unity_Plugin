"""Tests de AnalysisService con motor simulado."""

import pytest

from models import AnalyzeSelectionRequest, AnalyzeSelectionResponse, SelectionData, TransformData
from services.analysis_service import AnalysisService


class MockEngine:
    """Motor mínimo que devuelve una respuesta fija."""

    def __init__(self, response: AnalyzeSelectionResponse):
        self._response = response
        self.calls = 0

    def analyze(self, request: AnalyzeSelectionRequest) -> AnalyzeSelectionResponse:
        self.calls += 1
        return self._response


def test_analysis_service_empty_selection_skips_engine():
    engine = MockEngine(
        AnalyzeSelectionResponse(summary="should not run", issues=[], plan=[])
    )
    svc = AnalysisService(engine)
    payload = AnalyzeSelectionRequest(selection=None)
    out = svc.analyze_selection(payload)
    assert engine.calls == 0
    assert "no object" in out.message.lower() or "no object" in out.summary.lower()


def test_analysis_service_delegates_to_engine_and_normalizes():
    engine = MockEngine(
        AnalyzeSelectionResponse(
            mode="rules",
            summary="",
            message="raw",
            issues=[],
            plan=[],
        )
    )
    svc = AnalysisService(engine)
    sel = SelectionData(
        name="X",
        transform=TransformData(position=[0, 0, 0], rotation=[0, 0, 0], scale=[1, 1, 1]),
    )
    payload = AnalyzeSelectionRequest(selection=sel)
    out = svc.analyze_selection(payload)
    assert engine.calls == 1
    assert out.summary == "raw" or out.message
    assert out.api_version == "4.0"
