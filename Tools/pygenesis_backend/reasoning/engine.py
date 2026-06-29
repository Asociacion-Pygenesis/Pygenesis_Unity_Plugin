from typing import Protocol

from models import AnalyzeSelectionRequest, AnalyzeSelectionResponse
from rules.builtin import build_rule_response


class ReasoningEngine(Protocol):
    def analyze(self, request: AnalyzeSelectionRequest) -> AnalyzeSelectionResponse: ...


class RuleBasedEngine:
    def analyze(self, request: AnalyzeSelectionRequest) -> AnalyzeSelectionResponse:
        cmd = (request.command or "").strip().lower()
        if cmd == "analyze_scene" and request.scene_snapshot is not None:
            snap = request.scene_snapshot
            scene = (request.scene_name or "").strip() or "(unnamed)"
            summary = (
                f"Scene '{scene}': {snap.root_count} root object(s), "
                f"~{snap.total_estimated} GameObjects counted (editor snapshot)."
            )
            if (snap.note or "").strip():
                summary += " " + snap.note.strip()
            return AnalyzeSelectionResponse(
                mode="rules",
                message=summary,
                summary=summary,
                issues=[],
                suggestions=[],
            )

        if request.selection is None:
            return AnalyzeSelectionResponse(
                message="No object is currently selected.",
                issues=[],
                suggestions=[],
            )

        selection = request.selection

        if selection.transform is None:
            return AnalyzeSelectionResponse(
                message="The selected object data is incomplete.",
                issues=[],
                suggestions=[],
            )

        if len(selection.transform.scale) < 3:
            return AnalyzeSelectionResponse(
                message="The selected object scale data is incomplete.",
                issues=[],
                suggestions=[],
            )

        return build_rule_response(selection)