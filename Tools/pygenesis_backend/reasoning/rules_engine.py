from models import AnalyzeSelectionRequest, AnalyzeSelectionResponse
from reasoning.engine import ReasoningEngine
from rules.builtin import build_rule_response, build_scene_rule_response


class RulesEngine(ReasoningEngine):
    def analyze(self, request: AnalyzeSelectionRequest) -> AnalyzeSelectionResponse:
        cmd = (request.command or "").strip().lower()
        if cmd == "analyze_scene":
            snap = (
                request.scene_snapshot.model_dump(mode="json", exclude_none=True)
                if request.scene_snapshot else {}
            )
            return build_scene_rule_response(snap, request.scene_name or "")
        return build_rule_response(request.selection)