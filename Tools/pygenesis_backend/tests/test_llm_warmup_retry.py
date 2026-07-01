"""Tests de reintento de warmup LLM."""

import os

from services.llm_warmup_retry import (
    DEFAULT_RETRY_SECONDS,
    warmup_retry_enabled,
    warmup_retry_interval_seconds,
)


def test_warmup_retry_interval_default(monkeypatch):
    monkeypatch.delenv("PYGENESIS_LLM_WARMUP_RETRY_SECONDS", raising=False)
    assert warmup_retry_interval_seconds() == float(DEFAULT_RETRY_SECONDS)


def test_warmup_retry_interval_custom(monkeypatch):
    monkeypatch.setenv("PYGENESIS_LLM_WARMUP_RETRY_SECONDS", "30")
    assert warmup_retry_interval_seconds() == 30.0


def test_warmup_retry_interval_minimum(monkeypatch):
    monkeypatch.setenv("PYGENESIS_LLM_WARMUP_RETRY_SECONDS", "1")
    assert warmup_retry_interval_seconds() == 5.0


def test_warmup_retry_enabled_on_by_default(monkeypatch):
    monkeypatch.delenv("PYGENESIS_LLM_WARMUP_RETRY", raising=False)
    assert warmup_retry_enabled() is True


def test_warmup_retry_can_disable(monkeypatch):
    monkeypatch.setenv("PYGENESIS_LLM_WARMUP_RETRY", "off")
    assert warmup_retry_enabled() is False
