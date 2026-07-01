"""Tests del puente de inferencia PyGenesis."""

from pathlib import Path

import pytest

from providers.bridge.config import bridge_inject_system_prompt, bridge_minimal_api_body, load_bridge_config


@pytest.fixture
def config_path() -> Path:
    tools_root = Path(__file__).resolve().parents[2]
    return tools_root / "pygenesis_inference" / "model_config.yaml"


def test_load_bridge_config(config_path: Path):
    assert config_path.is_file(), f"Falta {config_path}"
    cfg = load_bridge_config(config_path)
    assert cfg.model_id == "pygenesis-unity"
    assert "Pygenesis AI" in cfg.system_prompt
    assert cfg.sampling.temperature == 0.55
    assert cfg.sampling.num_predict == 2048
    assert len(cfg.stop) >= 2
    assert cfg.ui.title == "Pygenesis Unity"
    assert cfg.ui.subtitle == "Haz una pregunta"


def test_bridge_defaults_browser_parity(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PYGENESIS_BRIDGE_INJECT_SYSTEM", raising=False)
    monkeypatch.delenv("PYGENESIS_BRIDGE_MINIMAL_API", raising=False)
    assert bridge_inject_system_prompt() is True
    assert bridge_minimal_api_body() is True


def test_build_messages_includes_system_by_default(config_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PYGENESIS_BRIDGE_INJECT_SYSTEM", raising=False)
    cfg = load_bridge_config(config_path)
    msgs = cfg.build_messages("¿Rigidbody o CharacterController?")
    assert msgs[0]["role"] == "system"
    assert "Pygenesis AI" in msgs[0]["content"]
    assert msgs[1] == {"role": "user", "content": "¿Rigidbody o CharacterController?"}


def test_build_messages_user_only_when_inject_off(config_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PYGENESIS_BRIDGE_INJECT_SYSTEM", "off")
    cfg = load_bridge_config(config_path)
    msgs = cfg.build_messages("¿Rigidbody o CharacterController?")
    assert msgs == [{"role": "user", "content": "¿Rigidbody o CharacterController?"}]


def test_build_messages_inject_system_on(config_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PYGENESIS_BRIDGE_INJECT_SYSTEM", "on")
    cfg = load_bridge_config(config_path)
    msgs = cfg.build_messages("¿Rigidbody o CharacterController?")
    assert msgs[0]["role"] == "system"
    assert "Pygenesis AI" in msgs[0]["content"]
    assert msgs[1] == {"role": "user", "content": "¿Rigidbody o CharacterController?"}


def test_build_messages_system_override(config_path: Path):
    cfg = load_bridge_config(config_path)
    msgs = cfg.build_messages("haz script", system_override="contrato custom")
    assert msgs[0]["content"] == "contrato custom"


def test_passthrough_messages_user_only(config_path: Path, monkeypatch: pytest.MonkeyPatch):
    from config.models import LLMSettings
    from providers.bridge.llama_cpp_bridge import LlamaCppBridgeProvider

    monkeypatch.setenv("PYGENESIS_BRIDGE_INJECT_SYSTEM", "off")
    cfg = load_bridge_config(config_path)
    provider = LlamaCppBridgeProvider(LLMSettings(provider="pygenesis_bridge"), config=cfg)
    api = provider._passthrough_messages(
        [
            {"role": "system", "content": "system del chat_service que debe ignorarse"},
            {"role": "user", "content": "vieja"},
            {"role": "assistant", "content": "respuesta vieja"},
            {"role": "user", "content": "pregunta actual"},
        ]
    )
    assert api == [{"role": "user", "content": "pregunta actual"}]


def test_passthrough_messages_with_inject_system(config_path: Path, monkeypatch: pytest.MonkeyPatch):
    from config.models import LLMSettings
    from providers.bridge.llama_cpp_bridge import LlamaCppBridgeProvider

    monkeypatch.delenv("PYGENESIS_BRIDGE_INJECT_SYSTEM", raising=False)
    cfg = load_bridge_config(config_path)
    provider = LlamaCppBridgeProvider(LLMSettings(provider="pygenesis_bridge"), config=cfg)
    api = provider._passthrough_messages(
        [
            {"role": "user", "content": "pregunta actual"},
        ]
    )
    assert api[0]["role"] == "system"
    assert "Pygenesis AI" in api[0]["content"]
    assert api[-1]["content"] == "pregunta actual"


def test_build_body_minimal_api(config_path: Path, monkeypatch: pytest.MonkeyPatch):
    from config.models import LLMSettings
    from providers.bridge.llama_cpp_bridge import LlamaCppBridgeProvider

    monkeypatch.delenv("PYGENESIS_BRIDGE_MINIMAL_API", raising=False)
    monkeypatch.setenv("PYGENESIS_BRIDGE_INJECT_SYSTEM", "off")
    cfg = load_bridge_config(config_path)
    provider = LlamaCppBridgeProvider(LLMSettings(provider="pygenesis_bridge"), config=cfg)
    body = provider._build_body(
        [{"role": "user", "content": "hola"}],
        temperature=0.2,
        max_tokens=512,
        stream=True,
    )
    assert body == {
        "model": "pygenesis-unity",
        "messages": [{"role": "user", "content": "hola"}],
        "stream": True,
    }


def test_factory_builds_bridge_provider():
    from config.models import LLMSettings
    from providers.factory import build_provider

    p = build_provider(LLMSettings(provider="pygenesis_bridge"))
    assert p.__class__.__name__ == "LlamaCppBridgeProvider"


def test_resolve_gguf_falls_back_to_user_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from providers.bridge.config import BridgeConfig, ModelConfig, ServerConfig, _resolve_gguf_path

    inference = tmp_path / "repo_inference"
    inference.mkdir()
    user_root = tmp_path / "user" / ".pygenesis" / "pygenesis_inference"
    (user_root / "models").mkdir(parents=True)
    gguf = user_root / "models" / "pygenesis-unity-q4km.gguf"
    gguf.write_bytes(b"fake")

    monkeypatch.setattr(
        "providers.bridge.config.user_inference_data_root",
        lambda: user_root,
    )

    resolved = _resolve_gguf_path(inference, Path("models/pygenesis-unity-q4km.gguf"))
    assert resolved == gguf.resolve()
