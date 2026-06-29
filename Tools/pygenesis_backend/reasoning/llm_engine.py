import json
import logging
import time

from models import AnalyzeSelectionRequest, AnalyzeSelectionResponse
from providers.llm_http_errors import user_notice_for_provider_error
from reasoning.engine import ReasoningEngine
from reasoning.llm_output_models import LLMAnalysisOutput
from reasoning.prompts import (
    build_analysis_prompt,
    build_refinement_prompt,
    build_scene_second_pass_prompt,
    scene_two_pass_enabled,
)

logger = logging.getLogger("pygenesis")

_ACTION_SOURCES_FROZEN = frozenset({"rules", "llm", "hybrid", "agent"})
_ACTION_SCOPES_FROZEN = frozenset({"selected_object", "scene", "asset", "multi_object"})


def _normalize_action_source(value) -> str:
    """Alinea valores que devuelve el LLM (p. ej. 'PyGenesis') con ActionSource."""
    if value is None:
        return "llm"
    v = str(value).strip().lower()
    if v in _ACTION_SOURCES_FROZEN:
        return v
    # El system prompt identifica al modelo como Pygenesis AI; a vecho emite 'PyGenesis'.
    if v in ("pygenesis", "pygenesis ai"):
        return "llm"
    return "llm"


def _normalize_action_scope(value) -> str:
    """Alinea sinónimos del LLM con ActionScope."""
    if value is None:
        return "selected_object"
    v = str(value).strip().lower()
    if v in _ACTION_SCOPES_FROZEN:
        return v
    aliases = {
        "selection": "selected_object",
        "selected": "selected_object",
        "current": "selected_object",
        "current_object": "selected_object",
        "gameobject": "selected_object",
    }
    return aliases.get(v, "selected_object")


def _scene_snapshot_dict(request: AnalyzeSelectionRequest):
    if request.scene_snapshot is None:
        return None
    return request.scene_snapshot.model_dump(mode="json", exclude_none=True)


SYSTEM_PROMPT = (
    "You are Pygenesis AI, the reasoning core of the PyGenesis Unity editor assistant. "
    "You help developers understand and safely modify the current Unity scene or selection. "
    "When the user message describes scene_snapshot / scene_identity, that is the only active scene — "
    "use hierarchy_path strings to refer to GameObjects. "
    "Ignore any default-model persona about language or free-form answers for this API call. "
    "You must reply with a single valid JSON object only (no markdown fences, no prose outside JSON) "
    "that matches the schema requested in the user message. "
    "Do not wrap that JSON in <think> tags."
)


def _coerce_llm_dict(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("LLM output must be a JSON object")

    if "actions" in data and "plan" not in data:
        data = {**data, "plan": data.pop("actions")}

    plan_in = data.get("plan") or []
    plan_out = []
    for i, item in enumerate(plan_in):
        if not isinstance(item, dict):
            continue
        step = dict(item)
        step.setdefault("step_id", f"llm_step_{i + 1:03d}")
        step.setdefault("label", step.get("action", "action"))
        step.setdefault("description", step.get("description", ""))
        step.setdefault("rule_id", step.get("rule_id", ""))
        step.setdefault("safety", step.get("safety", "safe"))
        step.setdefault("confidence", step.get("confidence", 1.0))
        step.setdefault("source", step.get("source", "llm"))
        step["source"] = _normalize_action_source(step.get("source"))
        step.setdefault("depends_on", step.get("depends_on") or [])
        step.setdefault("can_auto_apply", step.get("can_auto_apply", True))
        tgt = step.get("target")
        if isinstance(tgt, str):
            step["target"] = {
                "scope": _normalize_action_scope(tgt),
                "object_ref": None,
            }
        elif tgt is None:
            step["target"] = {"scope": "selected_object", "object_ref": None}
        elif isinstance(tgt, dict):
            if "scope" not in tgt:
                step["target"] = {
                    "scope": "selected_object",
                    "object_ref": tgt.get("object_ref"),
                }
            else:
                step["target"] = {
                    "scope": _normalize_action_scope(tgt.get("scope")),
                    "object_ref": tgt.get("object_ref"),
                }
        else:
            step["target"] = {"scope": "selected_object", "object_ref": None}
        step.setdefault("params", step.get("params") or {})
        plan_out.append(step)
    data["plan"] = plan_out

    issues_in = data.get("issues") or []
    issues_out = []
    for i, item in enumerate(issues_in):
        if not isinstance(item, dict):
            continue
        iss = dict(item)
        iss.setdefault("issue_id", f"issue_{i + 1:03d}")
        iss.setdefault("title", iss.get("title", "" ) or "")
        msg = (iss.get("message") or "").strip()
        if not msg:
            continue
        iss["message"] = msg
        iss.setdefault("severity", iss.get("severity", "low"))
        iss.setdefault("category", iss.get("category", "general"))
        iss.setdefault("confidence", iss.get("confidence", 1.0))
        iss.setdefault("source", iss.get("source", "llm"))
        iss["source"] = _normalize_action_source(iss.get("source"))
        issues_out.append(iss)
    data["issues"] = issues_out

    return data


def _normalize_llm_json_text(raw: str) -> str:
    """Quita cercas ```json de modelos locales (p. ej. Ollama) que no devuelven JSON puro."""
    s = raw.strip()
    if not s.startswith("```"):
        return s
    lines = s.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    s = "\n".join(lines).strip()
    if s.lower().startswith("json"):
        s = s[4:].lstrip()
    return s


def _parse_llm_json(raw: str) -> LLMAnalysisOutput:
    normalized = _normalize_llm_json_text(raw)
    parsed = json.loads(normalized)
    coerced = _coerce_llm_dict(parsed)
    return LLMAnalysisOutput.model_validate(coerced)


class LLMEngine:
    def __init__(
        self,
        provider,
        *,
        fallback: ReasoningEngine | None = None,
    ):
        self._provider = provider
        self._fallback = fallback

    def _run_llm(self, user_prompt: str) -> LLMAnalysisOutput:
        raw = self._provider.generate_json(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        return _parse_llm_json(raw)

    def analyze(self, request: AnalyzeSelectionRequest) -> AnalyzeSelectionResponse:
        cmd = (request.command or "").strip().lower()
        snap = _scene_snapshot_dict(request)
        prompt = build_analysis_prompt(
            selection_payload=request.selection.model_dump(mode="json") if request.selection else {},
            scene_name=request.scene_name,
            command=request.command,
            scene_snapshot=snap,
        )

        t0 = time.monotonic()
        try:
            output1 = self._run_llm(prompt)
        except Exception as ex:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.warning(
                "LLM analyze failed after %d ms, using fallback if configured: %s",
                elapsed_ms,
                ex,
            )
            if self._fallback is not None:
                fb = self._fallback.analyze(request)
                logger.info(
                    "Analyze completed: mode=rules (fallback tras fallo del LLM; ver warning anterior)",
                )
                meta = dict(fb.metadata or {})
                meta["fallback_reason"] = str(ex)
                meta["llm_attempt_duration_ms"] = elapsed_ms
                notice = user_notice_for_provider_error(ex)
                if notice:
                    meta["user_notice"] = notice
                    base = (fb.summary or "").strip()
                    new_summary = f"{notice}\n\n{base}" if base else notice
                    return fb.model_copy(
                        update={"metadata": meta, "summary": new_summary},
                    )
                return fb.model_copy(update={"metadata": meta})

            return AnalyzeSelectionResponse(
                mode="llm",
                summary=f"LLM analysis failed: {ex}",
                issues=[],
                plan=[],
                metadata={"error": str(ex)},
            )

        pass1_ms = int((time.monotonic() - t0) * 1000)

        if cmd == "analyze_scene" and scene_two_pass_enabled():
            t2_start = time.monotonic()
            try:
                prompt2 = build_scene_second_pass_prompt(
                    request.scene_name,
                    snap,
                    output1.model_dump(mode="json"),
                )
                output2 = self._run_llm(prompt2)
                pass2_ms = int((time.monotonic() - t2_start) * 1000)
                meta1 = output1.metadata if isinstance(output1.metadata, dict) else {}
                insights = meta1.get("object_insights")
                if not isinstance(insights, list):
                    insights = []
                meta2 = dict(output2.metadata) if isinstance(output2.metadata, dict) else {}
                meta2["object_insights"] = insights
                meta2["two_pass_scene"] = True
                meta2["llm_pass1_duration_ms"] = pass1_ms
                meta2["llm_pass2_duration_ms"] = pass2_ms
                meta2["llm_duration_ms"] = pass1_ms + pass2_ms
                logger.info(
                    "Analyze completed: mode=llm two_pass_scene in %dms+%dms; issues=%d plan_steps=%d",
                    pass1_ms,
                    pass2_ms,
                    len(output2.issues or []),
                    len(output2.plan or []),
                )
                return AnalyzeSelectionResponse(
                    mode="llm",
                    summary=output2.summary or output1.summary or "Analysis completed.",
                    issues=output2.issues,
                    plan=output2.plan,
                    execution_policy=output2.execution_policy,
                    metadata=meta2,
                )
            except Exception as ex2:
                pass2_ms = int((time.monotonic() - t2_start) * 1000)
                logger.warning(
                    "Scene pass-2 LLM failed after %d ms (pass-1 ok): %s",
                    pass2_ms,
                    ex2,
                )
                meta = dict(output1.metadata) if isinstance(output1.metadata, dict) else {}
                meta["two_pass_scene"] = False
                meta["two_pass_scene_error"] = str(ex2)
                meta["llm_pass2_attempt_duration_ms"] = pass2_ms
                meta["llm_duration_ms"] = pass1_ms
                return AnalyzeSelectionResponse(
                    mode="llm",
                    summary=output1.summary or "Analysis completed.",
                    issues=output1.issues,
                    plan=output1.plan,
                    execution_policy=output1.execution_policy,
                    metadata=meta,
                )

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        n_issues = len(output1.issues or [])
        n_plan = len(output1.plan or [])
        logger.info(
            "Analyze completed: mode=llm (respuesta del modelo) in %d ms; issues=%d plan_steps=%d",
            elapsed_ms,
            n_issues,
            n_plan,
        )
        meta = {**(output1.metadata or {}), "llm_duration_ms": elapsed_ms}
        if cmd == "analyze_scene":
            meta["two_pass_scene"] = False
        return AnalyzeSelectionResponse(
            mode="llm",
            summary=output1.summary or "Analysis completed.",
            issues=output1.issues,
            plan=output1.plan,
            execution_policy=output1.execution_policy,
            metadata=meta,
        )

    def refine(
        self,
        request: AnalyzeSelectionRequest,
        draft: AnalyzeSelectionResponse,
    ) -> AnalyzeSelectionResponse:
        draft_dict = draft.model_dump(mode="json")
        prompt = build_refinement_prompt(
            selection_payload=request.selection.model_dump(mode="json") if request.selection else {},
            scene_name=request.scene_name,
            command=request.command,
            draft=draft_dict,
            scene_snapshot=_scene_snapshot_dict(request),
        )

        output = self._run_llm(prompt)
        return AnalyzeSelectionResponse(
            mode="hybrid",
            summary=output.summary or draft.summary or "Analysis completed.",
            issues=output.issues if output.issues else draft.issues,
            plan=output.plan if output.plan else draft.plan,
            execution_policy=output.execution_policy,
            metadata={
                **(draft.metadata or {}),
                **(output.metadata or {}),
                "refined_from_rules": True,
            },
        )
