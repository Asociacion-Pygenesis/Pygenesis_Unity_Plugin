from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from models import (
    AnalyzeSelectionRequest,
    AnalyzeSelectionResponse,
    DetectedIssue,
    ActionStep,
)
from providers.llm_http_errors import user_notice_for_provider_error
from reasoning.engine import ReasoningEngine
from reasoning.output_validator import normalize_response
from rules.builtin import build_rule_response, build_scene_rule_response

if TYPE_CHECKING:
    from reasoning.llm_engine import LLMEngine

logger = logging.getLogger("pygenesis")

# Issues de reglas con confidence >= este umbral no se envían al LLM para revisión
_HIGH_CONFIDENCE_THRESHOLD = 0.95

# Si las reglas encuentran >= este número de issues de alta gravedad, el LLM
# recibe el borrador completo para que lo enriquezca (modo enriquecimiento)
# Si hay menos, el LLM solo refina (modo refinamiento ligero)
_ENRICH_ISSUE_COUNT = 2


class HybridEngine(ReasoningEngine):
    """
    Motor híbrido: reglas como prefiltro + LLM como refinador.

    Flujo:
      1. Ejecutar reglas → borrador determinista (rápido, sin LLM)
      2. Clasificar issues por confianza:
         - Alta confianza (≥0.95): se mantienen como están
         - Baja confianza (<0.95): se envían al LLM para revisión
      3. Llamar al LLM con el borrador y el contexto para que:
         - Confirme/descarte issues de baja confianza
         - Añada issues que las reglas no detectan
         - Enriquezca las descripciones
         - Reordene el plan con lógica de dependencias
      4. Fusionar resultado: issues de reglas (alta conf.) + issues del LLM (deduplicados)
    """

    def __init__(self, llm_engine: "LLMEngine"):
        self._llm = llm_engine

    def analyze(self, request: AnalyzeSelectionRequest) -> AnalyzeSelectionResponse:
        cmd = (request.command or "").strip().lower()
        t0 = time.monotonic()

        # ── Paso 1: reglas ────────────────────────────────────────
        if cmd == "analyze_scene":
            snap = (
                request.scene_snapshot.model_dump(mode="json", exclude_none=True)
                if request.scene_snapshot else {}
            )
            rule_draft = build_scene_rule_response(snap, request.scene_name or "")
        else:
            rule_draft = build_rule_response(request.selection)

        rules_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Hybrid pass-1 (rules) done in %d ms: %d issues, %d steps",
            rules_ms, len(rule_draft.issues or []), len(rule_draft.plan or []),
        )

        # ── Paso 2: clasificar issues por confianza ───────────────
        certain_issues, uncertain_issues = _split_by_confidence(
            rule_draft.issues or [], _HIGH_CONFIDENCE_THRESHOLD
        )
        certain_steps = _steps_for_issues(rule_draft.plan or [], certain_issues)

        # ── Paso 3: LLM refina el borrador ────────────────────────
        t1 = time.monotonic()
        try:
            llm_result = self._llm.refine(request, rule_draft)
            llm_ms = int((time.monotonic() - t1) * 1000)
            logger.info(
                "Hybrid pass-2 (LLM refine) done in %d ms: %d issues, %d steps",
                llm_ms, len(llm_result.issues or []), len(llm_result.plan or []),
            )
        except Exception as ex:
            llm_ms = int((time.monotonic() - t1) * 1000)
            logger.warning(
                "Hybrid LLM refine failed after %d ms, returning rule draft: %s",
                llm_ms, ex,
            )
            # Fallback: devolver el borrador de reglas directamente
            meta = dict(rule_draft.metadata or {})
            meta.update({
                "hybrid_mode": "rules_only_fallback",
                "llm_fallback_reason": str(ex),
                "rules_duration_ms": rules_ms,
                "llm_attempt_duration_ms": llm_ms,
            })
            notice = user_notice_for_provider_error(ex)
            if notice:
                meta["user_notice"] = notice
                base = (rule_draft.summary or "").strip()
                new_summary = f"{notice}\n\n{base}" if base else notice
                return rule_draft.model_copy(
                    update={"mode": "hybrid", "metadata": meta, "summary": new_summary},
                )
            return rule_draft.model_copy(update={"mode": "hybrid", "metadata": meta})

        # ── Paso 4: fusionar resultados ───────────────────────────
        merged = _merge_results(
            certain_issues=certain_issues,
            certain_steps=certain_steps,
            llm_result=llm_result,
            rule_draft=rule_draft,
        )

        total_ms = int((time.monotonic() - t0) * 1000)
        merged.metadata = {
            **(merged.metadata or {}),
            "hybrid_mode": "rules+llm",
            "rules_duration_ms": rules_ms,
            "llm_duration_ms": llm_ms,
            "total_duration_ms": total_ms,
            "certain_issues": len(certain_issues),
            "uncertain_issues": len(uncertain_issues),
        }
        merged.mode = "hybrid"
        logger.info(
            "Hybrid complete in %d ms: %d issues total (%d certain + %d from LLM)",
            total_ms,
            len(merged.issues or []),
            len(certain_issues),
            len(merged.issues or []) - len(certain_issues),
        )
        return merged


# ══════════════════════════════════════════════════════════════════
# LÓGICA DE FUSIÓN
# ══════════════════════════════════════════════════════════════════

def _split_by_confidence(
    issues: list[DetectedIssue], threshold: float
) -> tuple[list[DetectedIssue], list[DetectedIssue]]:
    certain, uncertain = [], []
    for issue in issues:
        (certain if (issue.confidence or 0) >= threshold else uncertain).append(issue)
    return certain, uncertain


def _steps_for_issues(
    plan: list[ActionStep], issues: list[DetectedIssue]
) -> list[ActionStep]:
    """Devuelve los steps del plan cuyo rule_id corresponde a un issue cierto."""
    certain_ids = {i.issue_id for i in issues}
    return [s for s in plan if s.rule_id in certain_ids]


def _merge_results(
    certain_issues: list[DetectedIssue],
    certain_steps: list[ActionStep],
    llm_result: AnalyzeSelectionResponse,
    rule_draft: AnalyzeSelectionResponse,
) -> AnalyzeSelectionResponse:
    """
    Fusiona issues y plan con esta prioridad:
    - Issues ciertas (reglas alta conf.) → siempre se incluyen
    - Issues del LLM → se incluyen si no duplican una cierta
    - Steps del plan: primero los de reglas ciertas, luego los del LLM (deduplicados)
    """
    # Issues: ciertas + LLM (sin duplicar por issue_id)
    certain_ids = {i.issue_id for i in certain_issues}
    llm_issues = [
        i for i in (llm_result.issues or [])
        if i.issue_id not in certain_ids
    ]
    merged_issues = certain_issues + llm_issues

    # Plan: steps ciertas primero + steps del LLM (deduplicados por action+params)
    seen_actions: set[tuple] = {
        (s.action, tuple(sorted(s.params.items()))) for s in certain_steps
    }
    llm_steps_new = []
    for step in (llm_result.plan or []):
        key = (step.action, tuple(sorted((step.params or {}).items())))
        if key not in seen_actions:
            seen_actions.add(key)
            llm_steps_new.append(step)

    merged_plan = certain_steps + llm_steps_new

    # Summary: usar el del LLM si existe (más rico), si no el de reglas
    summary = (llm_result.summary or "").strip() or (rule_draft.summary or "")

    # Metadata: fusionar ambas
    meta = {**(rule_draft.metadata or {}), **(llm_result.metadata or {})}

    return AnalyzeSelectionResponse(
        mode="hybrid",
        summary=summary,
        issues=merged_issues,
        plan=merged_plan,
        execution_policy=llm_result.execution_policy or rule_draft.execution_policy,
        metadata=meta,
    )