import json
import os

from reasoning.action_catalog import ACTION_CATALOG

# Evita que modelos con system en español (p. ej. Modelfile Ollama) echen un preámbulo en lugar del JSON.
_JSON_ANTI_ECHO_TAIL = (
    "\n\nIMPORTANT: Your entire reply must be exactly one JSON object (starts with {, ends with }). "
    "Do not repeat persona, language, or format instructions from any prior context. "
    "Do not wrap the JSON in <think> tags."
)


def _use_compact_llm_prompt() -> bool:
    v = os.getenv("PYGENESIS_COMPACT_LLM_PROMPT")
    if v is None:
        return True
    return v.strip().lower() in ("1", "true", "yes", "on")


def scene_two_pass_enabled() -> bool:
    """Segunda llamada al LLM tras analyze_scene (pasada 1 = snapshot, pasada 2 = síntesis).

    Por defecto está desactivado: en hardware local dos pasadas duplica latencia y suele
    provocar timeouts / 502 en el cliente. Activar explícitamente: PYGENESIS_SCENE_TWO_PASS=1.
    """
    v = os.getenv("PYGENESIS_SCENE_TWO_PASS")
    if v is None:
        return False
    s = v.strip().lower()
    if s in ("0", "false", "no", "off"):
        return False
    return s in ("1", "true", "yes", "on")


def build_allowed_actions_text() -> str:
    lines = []

    for action_id, definition in ACTION_CATALOG.items():
        required = ", ".join(definition.required_params) if definition.required_params else "none"
        optional = ", ".join(definition.optional_params) if definition.optional_params else "none"

        lines.append(
            f"- {action_id}: target={definition.target}, safety={definition.safety}, "
            f"required_params={required}, optional_params={optional}"
        )

    return "\n".join(lines)


def build_allowed_actions_one_line() -> str:
    """Una sola línea de ids y parámetros — menos tokens que el listado largo."""
    parts = []
    for action_id, definition in ACTION_CATALOG.items():
        req = ",".join(definition.required_params) if definition.required_params else ""
        extra = f"({req})" if req else "()"
        parts.append(f"{action_id}{extra}")
    return "; ".join(parts)


def _unity_context_block(
    selection_payload: dict,
    scene_name: str,
    command: str,
    scene_snapshot: dict | None = None,
) -> str:
    cmd = (command or "").strip().lower()
    if cmd == "analyze_scene":
        path = ""
        if isinstance(scene_snapshot, dict):
            path = (scene_snapshot.get("scene_asset_path") or "").strip()
        identity = {
            "instruction": (
                "Unity Editor: there is exactly ONE active scene for this request. "
                "All roots, flat_sample, and hierarchy_path values refer ONLY to this scene. "
                "selection is empty — there is no single selected GameObject."
            ),
            "display_name": (scene_name or "").strip() or "(unnamed scene)",
            "scene_asset_path": path or "(unsaved or unknown — Unity sent an empty path)",
        }
        data: dict = {
            "scene_identity": identity,
            "scene_name": scene_name,
            "command": command,
            "selection": selection_payload,
        }
        if scene_snapshot is not None:
            data["scene_snapshot"] = scene_snapshot
        return json.dumps(data, ensure_ascii=False, indent=2)

    data: dict = {
        "scene_name": scene_name,
        "command": command,
        "selection": selection_payload,
    }
    if scene_snapshot is not None:
        data["scene_snapshot"] = scene_snapshot
    return json.dumps(data, ensure_ascii=False, indent=2)


def _scene_identity_plaintext(scene_name: str, scene_snapshot: dict | None) -> str:
    """Líneas visibles al inicio del user prompt para modelos que pierden contexto en JSON largo."""
    if not isinstance(scene_snapshot, dict):
        return ""
    path = (scene_snapshot.get("scene_asset_path") or "").strip()
    name = (scene_name or "").strip() or "(unnamed scene)"
    path_disp = path if path else "(unsaved or path unknown)"
    return (
        "=== ACTIVE UNITY SCENE (analyze ONLY this one) ===\n"
        f"display_name: {name}\n"
        f"scene_asset_path: {path_disp}\n"
        "Object IDs in data: use hierarchy_path strings from scene_snapshot (e.g. \"Player/Arm/Camera\").\n"
        "=== END ===\n\n"
    )


def _scene_analysis_hint(command: str) -> str:
    if (command or "").strip().lower() != "analyze_scene":
        return ""
    return (
        "\nSCENE-WIDE analysis only (no selected object). Follow this workflow:\n"
        "1) Identity: Start your \"summary\" with the scene display_name and scene_asset_path from scene_identity "
        "(one clear sentence, e.g. \"Scene 'X' at Assets/...\").\n"
        "2) Per-object pass: Walk scene_snapshot.roots and flat_sample. For each notable GameObject "
        "(use hierarchy_path as stable id), form a brief observation (role, components/flags, layer/tag if relevant). "
        "Put these in metadata.object_insights as an array of objects "
        '{ "hierarchy_path": "...", "observation": "..." } — cap at 28 entries; skip duplicates; '
        "group trivial siblings in one observation if needed.\n"
        "3) Ensemble pass: In summary (after the opening identity line), issues, and plan, synthesize the whole scene: "
        "hierarchy organization, possible clutter, static vs dynamic mix, cameras/lights presence, performance risks. "
        "When citing a specific object, use its hierarchy_path.\n"
        "Data: roots (first_level_children per root), flat_sample (BFS; direct_children_detail on early items), "
        "lights_index (light_type/shadows/intensity/color_rgb), cameras_index (orthographic/FOV/near/far/depth/clear_flags/culling), "
        "light_inspector / camera_inspector on nodes with has_light / has_camera, "
        "total_estimated, note. Use plan target.scope \"scene\" when the step applies to the whole scene.\n"
    )


def build_analysis_prompt(
    selection_payload: dict,
    scene_name: str,
    command: str,
    scene_snapshot: dict | None = None,
) -> str:
    selection_json = _unity_context_block(selection_payload, scene_name, command, scene_snapshot)
    hint = _scene_analysis_hint(command)
    scene_banner = ""
    if (command or "").strip().lower() == "analyze_scene" and scene_snapshot is not None:
        scene_banner = _scene_identity_plaintext(scene_name, scene_snapshot)

    if _use_compact_llm_prompt():
        catalog_line = build_allowed_actions_one_line()
        meta_hint = ""
        if (command or "").strip().lower() == "analyze_scene":
            meta_hint = (
                " For analyze_scene, metadata SHOULD include object_insights (array) as described in the workflow."
            )
        return f"""You are Pygenesis AI (PyGenesis Unity assistant). Reply with ONE JSON object only (no markdown).

Allowed plan actions (use these action ids only): {catalog_line}

Output JSON keys: summary (string), issues (array of {{issue_id,title,message,severity,category,confidence,source}}), plan (array of steps with step_id,action,label,description,rule_id,params,safety,confidence,source,depends_on,can_auto_apply,target={{scope,object_ref}}), execution_policy, metadata (object, may include object_insights). severity: info|low|medium|high|critical. Each issue/plan step: source MUST be one of rules|llm|hybrid|agent (use llm for model output). target.scope MUST be one of selected_object|scene|asset|multi_object (never use synonyms like selection or PyGenesis as source).{meta_hint}
{hint}
{scene_banner}Context:
{selection_json}
{_JSON_ANTI_ECHO_TAIL}
""".strip()

    allowed_actions_text = build_allowed_actions_text()
    return f"""
You are Pygenesis AI — the analysis engine for the PyGenesis Unity editor assistant.

Analyze the provided Unity context and return valid JSON only (no markdown, no commentary).
{hint}
For analyze_scene, include metadata.object_insights as specified in the workflow above.

Rules:
- Use only actions from the allowed catalog for "plan" steps.
- Do not invent action names.
- severity on issues must be one of: info, low, medium, high, critical
- issue.source and plan step source must be one of: rules, llm, hybrid, agent (use llm for findings you produce)
- plan step target.scope must be one of: selected_object, scene, asset, multi_object (use selected_object for the current selection)
- Keep output strictly compatible with the schema below.

Allowed actions:
{allowed_actions_text}

Required JSON shape:
{{
  "summary": "string",
  "issues": [
    {{
      "issue_id": "string",
      "title": "string",
      "message": "string",
      "severity": "info",
      "category": "string",
      "confidence": 1.0,
      "source": "llm"
    }}
  ],
  "plan": [
    {{
      "step_id": "string",
      "action": "string",
      "label": "string",
      "description": "string",
      "rule_id": "string",
      "params": {{}},
      "safety": "safe",
      "confidence": 1.0,
      "source": "llm",
      "depends_on": [],
      "can_auto_apply": true,
      "target": {{ "scope": "selected_object", "object_ref": null }}
    }}
  ],
  "execution_policy": {{
    "requires_user_confirmation": false,
    "max_auto_apply_steps": 1,
    "allow_partial_execution": true
  }},
  "metadata": {{}}
}}

{scene_banner}Unity context:
{selection_json}
{_JSON_ANTI_ECHO_TAIL}
""".strip()


def build_refinement_prompt(
    selection_payload: dict,
    scene_name: str,
    command: str,
    draft: dict,
    scene_snapshot: dict | None = None,
) -> str:
    selection_json = _unity_context_block(selection_payload, scene_name, command, scene_snapshot)
    draft_json = json.dumps(draft, ensure_ascii=False, indent=2)
    hint = _scene_analysis_hint(command)
    scene_banner = ""
    if (command or "").strip().lower() == "analyze_scene" and scene_snapshot is not None:
        scene_banner = _scene_identity_plaintext(scene_name, scene_snapshot)

    if _use_compact_llm_prompt():
        catalog_line = build_allowed_actions_one_line()
        return f"""You are Pygenesis AI. Refine the rule-based draft; return ONE JSON object only (no markdown).

Allowed plan actions: {catalog_line}

Same JSON shape as analysis (summary, issues, plan, execution_policy, metadata). For analyze_scene, add or keep metadata.object_insights if missing.
{hint}
{scene_banner}Context:
{selection_json}

Draft:
{draft_json}
{_JSON_ANTI_ECHO_TAIL}
""".strip()

    allowed_actions_text = build_allowed_actions_text()
    return f"""
You are Pygenesis AI. You refine analysis for the PyGenesis Unity editor assistant. Return valid JSON only (no markdown).

You receive a rule-based draft. Improve summary, issues, and plan if needed; you may keep, drop, or replace steps.
Use only actions from the catalog.
{hint}

Allowed actions:
{allowed_actions_text}

Required JSON shape (same as analysis): summary, issues, plan, optional execution_policy and metadata.

{scene_banner}Unity context:
{selection_json}

Rule-based draft to refine:
{draft_json}
{_JSON_ANTI_ECHO_TAIL}
""".strip()


def _compact_pass1_for_second_pass(pass1: dict, *, max_insights: int = 36, max_issue_msgs: int = 160) -> dict:
    """Reduce tokens para la pasada 2 sin perder referencias hierarchy_path."""
    meta = pass1.get("metadata") if isinstance(pass1.get("metadata"), dict) else {}
    raw_insights = meta.get("object_insights")
    insights: list = raw_insights if isinstance(raw_insights, list) else []
    trimmed = []
    for item in insights[:max_insights]:
        if not isinstance(item, dict):
            continue
        trimmed.append(
            {
                "hierarchy_path": (item.get("hierarchy_path") or "")[:200],
                "observation": (item.get("observation") or "")[:400],
            }
        )
    issues_out = []
    for iss in (pass1.get("issues") or [])[:12]:
        if not isinstance(iss, dict):
            continue
        msg = (iss.get("message") or "")[:max_issue_msgs]
        issues_out.append(
            {
                "issue_id": iss.get("issue_id", ""),
                "title": (iss.get("title") or "")[:120],
                "message": msg,
                "severity": iss.get("severity", "low"),
            }
        )
    plan_out = []
    for step in (pass1.get("plan") or [])[:15]:
        if not isinstance(step, dict):
            continue
        plan_out.append(
            {
                "step_id": step.get("step_id", ""),
                "action": step.get("action", ""),
                "label": (step.get("label") or "")[:100],
                "description": (step.get("description") or "")[:240],
                "target": step.get("target"),
            }
        )
    return {
        "pass1_summary": (pass1.get("summary") or "")[:2500],
        "pass1_issues": issues_out,
        "pass1_plan_preview": plan_out,
        "object_insights": trimmed,
        "object_insights_truncated": len(insights) > max_insights,
    }


def build_scene_second_pass_prompt(
    scene_name: str,
    scene_snapshot: dict | None,
    pass1: dict,
) -> str:
    """Pasada 2: solo contexto comprimido + salida de pasada 1; pide síntesis final (summary, issues, plan)."""
    scene_banner = ""
    if isinstance(scene_snapshot, dict):
        scene_banner = _scene_identity_plaintext(scene_name, scene_snapshot)

    snap = scene_snapshot if isinstance(scene_snapshot, dict) else {}
    stats = {
        "total_estimated": snap.get("total_estimated"),
        "root_count": snap.get("root_count"),
        "note": (snap.get("note") or "")[:500],
    }
    compact = _compact_pass1_for_second_pass(pass1)
    bundle = {
        "scene_stats": stats,
        "first_pass_output": compact,
    }
    bundle_json = json.dumps(bundle, ensure_ascii=False, indent=2)

    if _use_compact_llm_prompt():
        catalog_line = build_allowed_actions_one_line()
        return f"""You are Pygenesis AI (PyGenesis Unity assistant). This is PASS 2 of 2 for scene analysis.
Pass 1 already walked the hierarchy; you receive its summary, issues, plan preview, and object_insights (per-object notes).
Reply with ONE JSON object only (no markdown).

Allowed plan actions (use these action ids only): {catalog_line}

Output JSON keys: summary, issues, plan, execution_policy, metadata.
Rules for pass 2:
- Start summary with the scene display_name and asset path (from banner below or scene_stats context).
- Write a cohesive scene-level summary (do NOT paste the full object_insights list into summary; at most 1–2 examples with hierarchy_path).
- Refine or replace issues and plan using only facts supported by first_pass_output; use hierarchy_path when naming objects.
- target.scope \"scene\" when the step applies to the whole scene.
- metadata: optional short synthesis_notes only. Do NOT include object_insights (the server keeps pass-1 insights).
severity: info|low|medium|high|critical.

{scene_banner}Compressed first-pass data (JSON):
{bundle_json}
{_JSON_ANTI_ECHO_TAIL}
""".strip()

    allowed_actions_text = build_allowed_actions_text()
    return f"""
You are Pygenesis AI — PASS 2 of 2 for Unity scene-wide analysis.
You receive compressed output from pass 1 (per-object insights, draft issues, draft plan). Produce the final analysis JSON only (no markdown).

Rules:
- summary: start with scene identity, then synthesis (organization, risks, cameras/lights, performance). Do not duplicate the full object_insights list.
- issues / plan: consolidate, dedupe, fix inconsistencies; cite hierarchy_path where useful.
- Use only catalog actions for plan steps.
- metadata: optional synthesis_notes only (no object_insights array).

Allowed actions:
{allowed_actions_text}

Required JSON shape (same as main analysis): summary, issues, plan, execution_policy, metadata.

{scene_banner}Compressed first-pass data:
{bundle_json}
{_JSON_ANTI_ECHO_TAIL}
""".strip()
