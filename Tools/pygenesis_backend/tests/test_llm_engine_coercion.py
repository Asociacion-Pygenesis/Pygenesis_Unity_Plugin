"""Coerción de JSON del LLM hacia LLMAnalysisOutput (fuentes y scopes tolerantes)."""

import json

from reasoning.llm_engine import _coerce_llm_dict, _parse_llm_json
from reasoning.llm_output_models import LLMAnalysisOutput


def test_coerce_pygenesis_source_and_selection_scope():
    raw = {
        "summary": "test",
        "issues": [
            {
                "issue_id": "a",
                "title": "T",
                "message": "m",
                "source": "PyGenesis",
            }
        ],
        "plan": [
            {
                "step_id": "s1",
                "action": "add_component",
                "label": "L",
                "source": "PyGenesis",
                "target": {"scope": "selection", "object_ref": None},
            }
        ],
    }
    coerced = _coerce_llm_dict(raw)
    out = LLMAnalysisOutput.model_validate(coerced)
    assert out.issues[0].source == "llm"
    assert out.plan[0].source == "llm"
    assert out.plan[0].target.scope == "selected_object"


def test_parse_llm_json_roundtrip():
    payload = json.dumps(
        {
            "summary": "ok",
            "issues": [
                {
                    "issue_id": "i1",
                    "title": "x",
                    "message": "msg",
                    "source": "PyGenesis",
                }
            ],
            "plan": [],
        }
    )
    parsed = _parse_llm_json(payload)
    assert parsed.issues[0].source == "llm"
