from app.services.connectors import ModelRouter, _hetzner_label


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
    assert route["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
