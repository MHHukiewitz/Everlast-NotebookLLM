from types import SimpleNamespace

import pytest

from app.services.modalities import require_tts, resolve_media


def test_resolve_tts_local_when_host_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.modalities.host_open", lambda _url: True)
    route = resolve_media("tts", "local", "kokoro")
    assert route["model"] == "kokoro"
    assert route["api_base"].endswith("/v1")


def test_resolve_tts_local_down_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.modalities.host_open", lambda _url: False)
    with pytest.raises(ValueError, match="Sprachmodell"):
        resolve_media("tts", "local", "kokoro")


def test_resolve_image_local_down_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.modalities.host_open", lambda _url: False)
    with pytest.raises(ValueError, match="Bildmodell"):
        resolve_media("image", "local", "flux")


def test_resolve_eu_missing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.modalities.settings.eu_llm_base_url", "")
    monkeypatch.setattr("app.services.modalities.settings.eu_llm_api_key", "")
    with pytest.raises(ValueError, match="EU-Gateway"):
        resolve_media("tts", "eu", "tts-1")


def test_resolve_openrouter_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.modalities.settings.openrouter_api_key", "")
    with pytest.raises(ValueError, match="OpenRouter"):
        resolve_media("image", "openrouter", "google/gemini-2.5-flash-image")


def test_notebook_defaults_use_hetzner_and_openrouter_image(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.tenancy import notebook_defaults

    monkeypatch.setattr("app.services.tenancy.settings.default_provider", "hetzner")
    monkeypatch.setattr("app.services.tenancy.settings.default_model", "Qwen/Qwen3.6-35B-A3B-FP8")
    monkeypatch.setattr("app.services.tenancy.settings.default_image_provider", "openrouter")
    monkeypatch.setattr(
        "app.services.tenancy.settings.default_image_model", "google/gemini-2.5-flash-image"
    )
    monkeypatch.setattr("app.services.tenancy.settings.default_tts_provider", "local")
    monkeypatch.setattr("app.services.tenancy.settings.default_tts_model", "piper")
    defaults = notebook_defaults()
    assert defaults["provider"] == "hetzner"
    assert defaults["model_id"] == "Qwen/Qwen3.6-35B-A3B-FP8"
    assert defaults["tts_provider"] == "local"
    assert defaults["tts_model"] == "piper"
    assert defaults["image_provider"] == "openrouter"
    assert defaults["image_model"] == "google/gemini-2.5-flash-image"
    assert defaults["openrouter_notice_accepted"] is True


def test_image_request_openrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.modalities.settings.openrouter_api_key", "test-key")
    from app.services.studio.media import image_request

    url, payload, headers = image_request(
        "openrouter", "google/gemini-2.5-flash-image", "rotes Quadrat"
    )
    assert url == "https://openrouter.ai/api/v1/images"
    assert payload["model"] == "google/gemini-2.5-flash-image"
    assert payload["aspect_ratio"] == "16:9"
    assert "Authorization" in headers


def test_require_tts_uses_notebook(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.modalities.host_open", lambda _url: True)
    notebook = SimpleNamespace(tts_provider="local", tts_model="kokoro")
    route = require_tts(notebook, "en")  # type: ignore[arg-type]
    assert route["model"] == "kokoro"
    assert route["provider"] == "local"
