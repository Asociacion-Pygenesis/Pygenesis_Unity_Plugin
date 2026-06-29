"""Tests de normalize_response y piezas relacionadas."""

import pytest

from models import AnalyzeSelectionResponse, DetectedIssue, ActionStep, ActionTarget, ExecutionPolicy
from reasoning.output_validator import normalize_response, normalize_issues


def test_normalize_response_fills_summary_from_message_when_summary_empty():
    raw = AnalyzeSelectionResponse(
        summary="",
        message="Hello from legacy field",
        issues=[],
        plan=[],
    )
    out = normalize_response(raw)
    assert out.summary == "Hello from legacy field"
    assert out.message == out.summary


def test_normalize_response_default_summary_when_both_empty_no_issues():
    raw = AnalyzeSelectionResponse(summary="", message="", issues=[], plan=[])
    out = normalize_response(raw)
    assert out.summary == "No issues detected."


def test_normalize_response_uses_issue_fallback_summary():
    raw = AnalyzeSelectionResponse(
        summary="",
        message="",
        issues=[
            DetectedIssue(
                issue_id="x",
                message="Something wrong",
                severity="low",
            )
        ],
        plan=[],
    )
    out = normalize_response(raw)
    assert out.summary == "Analysis completed with detected issues."


def test_normalize_issues_clamps_confidence():
    raw_issues = [
        DetectedIssue(
            issue_id="a",
            message="ok",
            severity="low",
            confidence=99.0,
        )
    ]
    out = normalize_issues(raw_issues)
    assert len(out) == 1
    assert out[0].confidence == 1.0


def test_normalize_response_preserves_mode_and_api_version():
    raw = AnalyzeSelectionResponse(
        mode="llm",
        summary="S",
        issues=[],
        plan=[],
    )
    out = normalize_response(raw)
    assert out.mode == "llm"
    assert out.api_version == "4.0"
