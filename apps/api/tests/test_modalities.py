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


def test_require_tts_uses_notebook(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.modalities.host_open", lambda _url: True)
    notebook = SimpleNamespace(tts_provider="local", tts_model="kokoro")
    route = require_tts(notebook)  # type: ignore[arg-type]
    assert route["model"] == "kokoro"
