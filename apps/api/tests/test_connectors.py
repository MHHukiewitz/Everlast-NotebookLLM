import pytest

from app.config import Settings
from app.services.connectors import ModelRouter, _csv, _hetzner_label, _is_ollama_chat_model, _openrouter_label


def test_hetzner_label() -> None:
    assert _hetzner_label("Qwen/Qwen3.6-35B-A3B-FP8") == "Qwen3.6 35B"
    assert _hetzner_label("Qwen3.8-27B") == "Qwen3.8 27B"


def test_list_providers_includes_hetzner(monkeypatch) -> None:
    from app.services import connectors

    monkeypatch.setattr(connectors.settings, "hetzner_api_key", "test-key")
    monkeypatch.setattr(connectors.settings, "hetzner_models", "Qwen/Qwen3.6-35B-A3B-FP8,Qwen3.8-27B")
    lanes = ModelRouter().list_providers()
    hetzner = next(lane for lane in lanes if lane.id == "hetzner")
    assert hetzner.available is True
    assert "DSGVO" in hetzner.notice
    assert [model.id for model in hetzner.models] == ["Qwen/Qwen3.6-35B-A3B-FP8", "Qwen3.8-27B"]


def test_list_providers_hetzner_missing_key(monkeypatch) -> None:
    from app.services import connectors

    monkeypatch.setattr(connectors.settings, "hetzner_api_key", "")
    hetzner = next(lane for lane in ModelRouter().list_providers() if lane.id == "hetzner")
    assert hetzner.available is False
    assert "HETZNER_API_KEY" in hetzner.notice


def test_list_providers_openrouter(monkeypatch) -> None:
    from app.services import connectors

    monkeypatch.setattr(connectors.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(
        connectors.settings,
        "openrouter_models",
        "openrouter/anthropic/claude-sonnet-4.6,openrouter/openai/gpt-5.2",
    )
    lane = next(item for item in ModelRouter().list_providers() if item.id == "openrouter")
    assert lane.available is True
    assert "Drittland" in lane.notice
    assert [model.id for model in lane.models] == [
        "openrouter/anthropic/claude-sonnet-4.6",
        "openrouter/openai/gpt-5.2",
    ]


def test_resolve_hetzner(monkeypatch) -> None:
    from app.services import connectors

    monkeypatch.setattr(connectors.settings, "hetzner_api_key", "test-key")
    monkeypatch.setattr(connectors.settings, "hetzner_api_base", "https://inference.hetzner.com/api/v1")
    monkeypatch.setattr(connectors.settings, "hetzner_models", "Qwen/Qwen3.6-35B-A3B-FP8,Qwen3.8-27B")
    route = ModelRouter().resolve("hetzner", "Qwen3.8-27B")
    assert route["model"] == "Qwen3.8-27B"
    assert route["custom_llm_provider"] == "openai"
    assert route["api_base"] == "https://inference.hetzner.com/api/v1"
    assert route["api_key"] == "test-key"
    assert route["extra_body"]["enable_thinking"] is False
    assert route["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False


def test_openrouter_defaults_include_discounted_chat_models() -> None:
    ids = _csv(str(Settings.model_fields["openrouter_models"].default))
    assert ids[:3] == [
        "openrouter/anthropic/claude-sonnet-4.6",
        "openrouter/openai/gpt-5.2",
        "openrouter/google/gemini-2.5-pro",
    ]
    assert "openrouter/openai/gpt-5.6-sol" in ids
    assert "openrouter/google/gemini-3.7-flash" in ids
    assert "openrouter/deepseek/deepseek-v4-pro" in ids
    assert "openrouter/deepseek/deepseek-v4-flash" in ids
    assert "openrouter/qwen/qwen3-235b-a22b-2507" in ids
    assert "openrouter/z-ai/glm-5.2" in ids


def test_openrouter_label() -> None:
    assert _openrouter_label("openrouter/openai/gpt-5.6-sol") == "GPT-5.6 Sol"
    assert _openrouter_label("openrouter/google/gemini-3.7-flash") == "Gemini 3.7 Flash"


def test_ollama_skips_embedding_models() -> None:
    assert _is_ollama_chat_model("qwen2.5:7b") is True
    assert _is_ollama_chat_model("nomic-embed-text:latest") is False


def test_list_providers_ollama_uses_tags(monkeypatch) -> None:
    from app.services import connectors

    monkeypatch.setattr(connectors, "_ollama_model_ids", lambda: ["qwen2.5:7b", "llama3.2"])
    lane = next(item for item in ModelRouter().list_providers() if item.id == "ollama")
    assert [model.id for model in lane.models] == ["qwen2.5:7b", "llama3.2"]


def test_resolve_openrouter_allowlist(monkeypatch) -> None:
    from app.services import connectors

    monkeypatch.setattr(connectors.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(
        connectors.settings,
        "openrouter_models",
        "openrouter/openai/gpt-5.6-sol,openrouter/google/gemini-3.7-flash",
    )
    route = ModelRouter().resolve("openrouter", "openrouter/openai/gpt-5.6-sol")
    assert route["model"] == "openrouter/openai/gpt-5.6-sol"
    with pytest.raises(ValueError, match="OpenRouter-Allowlist"):
        ModelRouter().resolve("openrouter", "openrouter/openai/unknown-model")
