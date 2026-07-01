# services/analysis_service.py
from models import AnalyzeSelectionRequest, AnalyzeSelectionResponse
from reasoning.engine import ReasoningEngine
from reasoning.output_validator import normalize_response, ParamValidator
from services.scene_validation import is_empty_scene_snapshot
from services.selection_validation import is_empty_selection


class AnalysisService:
    """
    Orquesta validación de entrada, motor de razonamiento y validación de salida.

    param_validator se inyecta desde main.py (o desde tests) en el constructor.
    AnalysisService no importa action_registry — esa responsabilidad pertenece
    a quien instancia este servicio.
    """

    def __init__(
        self,
        reasoning_engine: ReasoningEngine,
        param_validator: ParamValidator = None,
    ):
        self._engine = reasoning_engine
        self._param_validator = param_validator

    def analyze_selection(self, payload: AnalyzeSelectionRequest) -> AnalyzeSelectionResponse:
        cmd = (payload.command or "").strip().lower()

        if cmd == "analyze_scene":
            if is_empty_scene_snapshot(payload.scene_snapshot):
                return normalize_response(
                    AnalyzeSelectionResponse(
                        message="Scene snapshot is missing or empty (no roots or invalid scene).",
                        issues=[],
                        suggestions=[],
                    ),
                    self._param_validator,
                )
            raw = self._engine.analyze(payload)
            return normalize_response(raw, self._param_validator)

        if is_empty_selection(payload.selection):
            return normalize_response(
                AnalyzeSelectionResponse(
                    message="No object is currently selected.",
                    issues=[],
                    suggestions=[],
                ),
                self._param_validator,
            )

        raw = self._engine.analyze(payload)
        return normalize_response(raw, self._param_validator)