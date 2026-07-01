from typing import Callable, List, Optional

from models import (
    AnalyzeSelectionResponse,
    ActionStep,
    SuggestedAction,
    DetectedIssue,
    ActionTarget,
    ExecutionPolicy,
)
from reasoning.action_catalog import ACTION_CATALOG, resolve_action


# ---------------------------------------------------------------------------
# Tipo del validador de params inyectable (para evitar import circular con
# services.action_registry). Se inyecta desde AnalysisService en runtime;
# en tests se puede omitir (None) para usar solo el catálogo estático.
# ---------------------------------------------------------------------------
ParamValidator = Optional[Callable[[str, dict], bool]]

ALLOWED_SEVERITIES = {"info", "low", "medium", "high", "critical"}
ALLOWED_SCOPES     = {"selected_object", "scene", "asset", "multi_object"}
ALLOWED_SAFETY     = {"safe", "review", "dangerous"}
ALLOWED_SOURCES    = {"rules", "llm", "hybrid", "agent"}

MAX_PLAN_STEPS = 20
MAX_ISSUES     = 20


# ══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def normalize_response(
    response: AnalyzeSelectionResponse,
    param_validator: ParamValidator = None,
) -> AnalyzeSelectionResponse:
    """
    Normaliza y valida una respuesta cruda del motor de análisis.

    param_validator se inyecta desde AnalysisService cuando el ActionRegistry
    dinámico (cargado desde Unity) está disponible. Si es None se usa el
    catálogo estático ACTION_CATALOG como fallback.
    """
    summary          = (response.summary or "").strip()
    issues           = normalize_issues(response.issues)
    plan             = normalize_plan(response.plan, param_validator)
    execution_policy = normalize_execution_policy(response.execution_policy)
    metadata         = response.metadata if isinstance(response.metadata, dict) else {}

    if not summary:
        if response.message and response.message.strip():
            summary = response.message.strip()
        elif issues:
            summary = "Analysis completed with detected issues."
        else:
            summary = "No issues detected."

    legacy_suggestions = build_legacy_suggestions(plan)
    legacy_message     = summary

    return AnalyzeSelectionResponse(
        api_version="4.0",
        mode=(response.mode or "rules").strip() or "rules",
        summary=summary,
        issues=issues,
        plan=plan,
        execution_policy=execution_policy,
        metadata=metadata,
        message=legacy_message,
        suggestions=legacy_suggestions,
    )


# ══════════════════════════════════════════════════════════════════════════════
# ISSUES
# ══════════════════════════════════════════════════════════════════════════════

def normalize_issues(issues: List[DetectedIssue]) -> List[DetectedIssue]:
    normalized: List[DetectedIssue] = []

    for issue in issues[:MAX_ISSUES]:
        issue_id = (issue.issue_id or "").strip()
        title    = (issue.title    or "").strip()
        message  = (issue.message  or "").strip()
        category = (issue.category or "").strip() or "general"
        severity = issue.severity if issue.severity in ALLOWED_SEVERITIES else "low"
        source   = issue.source   if issue.source   in ALLOWED_SOURCES    else "rules"

        confidence = issue.confidence
        if not isinstance(confidence, (int, float)):
            confidence = 1.0
        confidence = max(0.0, min(float(confidence), 1.0))

        if not issue_id or not message:
            continue

        normalized.append(
            DetectedIssue(
                issue_id=issue_id,
                title=title,
                message=message,
                severity=severity,
                category=category,
                confidence=confidence,
                source=source,
            )
        )

    return dedupe_issues(normalized)


# ══════════════════════════════════════════════════════════════════════════════
# PLAN
# ══════════════════════════════════════════════════════════════════════════════

def normalize_plan(
    plan: List[ActionStep],
    param_validator: ParamValidator = None,
) -> List[ActionStep]:
    normalized: List[ActionStep] = []

    for index, step in enumerate(plan[:MAX_PLAN_STEPS], start=1):
        validated = validate_action_step(
            step,
            default_step_id=f"step_{index:03d}",
            param_validator=param_validator,
        )
        if validated is not None:
            normalized.append(validated)

    return dedupe_plan(normalized)


def validate_action_step(
    step: ActionStep,
    default_step_id: str,
    param_validator: ParamValidator = None,
) -> Optional[ActionStep]:
    # Resuelve alias legacy (p. ej. add_box_collider → add_component) a la acción
    # canónica que Unity sabe ejecutar, fusionando/renombrando params.
    raw_params = step.params if isinstance(step.params, dict) else {}
    action_id, params = resolve_action(step.action, raw_params)

    definition = ACTION_CATALOG.get(action_id)
    if definition is None:
        return None

    label       = (step.label       or "").strip() or definition.label
    description = (step.description or "").strip() or definition.description
    rule_id     = (step.rule_id     or "").strip()
    step_id     = (step.step_id     or "").strip() or default_step_id

    safety = step.safety if step.safety in ALLOWED_SAFETY  else definition.safety
    source = step.source if step.source in ALLOWED_SOURCES else "rules"

    confidence = step.confidence
    if not isinstance(confidence, (int, float)):
        confidence = 1.0
    confidence = max(0.0, min(float(confidence), 1.0))

    target_scope = (
        step.target.scope
        if step.target and step.target.scope in ALLOWED_SCOPES
        else definition.target
    )
    object_ref = step.target.object_ref if step.target else None

    for required in definition.required_params:
        if required not in params:
            return None

    allowed_param_names = set(definition.required_params + definition.optional_params)
    filtered_params = {k: v for k, v in params.items() if k in allowed_param_names}

    if not validate_param_types(action_id, filtered_params, param_validator):
        return None

    depends_on    = [d for d in step.depends_on if isinstance(d, str) and d.strip()]
    can_auto_apply = bool(step.can_auto_apply and definition.supports_auto_apply)

    return ActionStep(
        step_id=step_id,
        action=definition.action_id,
        label=label,
        description=description,
        target=ActionTarget(scope=target_scope, object_ref=object_ref),
        params=filtered_params,
        safety=safety,
        confidence=confidence,
        source=source,
        depends_on=depends_on,
        can_auto_apply=can_auto_apply,
        rule_id=rule_id,
    )


# ══════════════════════════════════════════════════════════════════════════════
# VALIDACIÓN DE TIPOS DE PARAMS
# ══════════════════════════════════════════════════════════════════════════════

def validate_param_types(
    action_id: str,
    params: dict,
    external_validator: ParamValidator = None,
) -> bool:
    """
    Valida los tipos de los params de una acción contra el catálogo canónico.

    Orden de prioridad:
      1. external_validator inyectado (ActionRegistry dinámico desde Unity).
      2. Catálogo canónico ACTION_CATALOG (resolviendo alias legacy):
         - todos los required_params deben estar presentes,
         - los params presentes deben tener el tipo declarado,
         - caso especial: rename_object exige un nombre no vacío.
      3. Acción desconocida → False.

    El external_validator NO propaga excepciones: cualquier error interno se
    captura y se cae al catálogo canónico.
    """
    # 1. Validator dinámico (inyectado desde AnalysisService, sin import circular)
    if external_validator is not None:
        try:
            return external_validator(action_id, params)
        except Exception:
            pass  # fallo inesperado → caer al catálogo canónico

    # 2. Catálogo canónico (resolviendo alias legacy → canónico)
    canonical, resolved = resolve_action(action_id, params)
    definition = ACTION_CATALOG.get(canonical)
    if definition is None:
        return False

    param_types = definition.param_types
    for spec_name, expected_type in param_types.items():
        if spec_name not in resolved:
            continue
        value = resolved[spec_name]
        if value is not None and not isinstance(value, expected_type):
            return False

    for req in definition.required_params:
        if req not in resolved:
            return False

    # Caso especial: rename_object requiere nombre no vacío
    if canonical == "rename_object":
        name = resolved.get("name")
        if not isinstance(name, str) or not name.strip():
            return False

    return True


# ══════════════════════════════════════════════════════════════════════════════
# EXECUTION POLICY
# ══════════════════════════════════════════════════════════════════════════════

def normalize_execution_policy(policy: ExecutionPolicy) -> ExecutionPolicy:
    if not isinstance(policy, ExecutionPolicy):
        return ExecutionPolicy()

    max_auto_apply_steps = policy.max_auto_apply_steps
    if not isinstance(max_auto_apply_steps, int):
        max_auto_apply_steps = 1
    max_auto_apply_steps = max(0, min(max_auto_apply_steps, 20))

    return ExecutionPolicy(
        requires_user_confirmation=bool(policy.requires_user_confirmation),
        max_auto_apply_steps=max_auto_apply_steps,
        allow_partial_execution=bool(policy.allow_partial_execution),
    )


# ══════════════════════════════════════════════════════════════════════════════
# LEGACY SUGGESTIONS
# ══════════════════════════════════════════════════════════════════════════════

def build_legacy_suggestions(plan: List[ActionStep]) -> List[SuggestedAction]:
    suggestions: List[SuggestedAction] = []

    for step in plan:
        suggestions.append(
            SuggestedAction(
                action=step.action,
                label=step.label,
                description=step.description,
                rule_id=step.rule_id,
                confidence=step.confidence,
                safety=step.safety,
                target=step.target.scope,
                params=step.params,
            )
        )

    return suggestions


# ══════════════════════════════════════════════════════════════════════════════
# DEDUPLICACIÓN
# ══════════════════════════════════════════════════════════════════════════════

def dedupe_issues(issues: List[DetectedIssue]) -> List[DetectedIssue]:
    result: List[DetectedIssue] = []
    seen: set = set()

    for issue in issues:
        key = (issue.issue_id, issue.message)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)

    return result


def dedupe_plan(plan: List[ActionStep]) -> List[ActionStep]:
    result: List[ActionStep] = []
    seen: set = set()

    for step in plan:
        key = (step.action, tuple(sorted((step.params or {}).items())))
        if key in seen:
            continue
        seen.add(key)
        result.append(step)

    return result