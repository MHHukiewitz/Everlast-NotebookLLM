from types import SimpleNamespace

import pytest

from app.services.modalities import require_tts, tts_language_code
from app.services.studio.audio import SYSTEM_BRIEFING, _language_label
from app.services.studio.media import GERMAN_SPEECH_STYLE, OPENAI_TO_PIPER, speech_payload, speech_style, voice_for


def test_tts_language_defaults_to_german() -> None:
    assert tts_language_code(None) == "de"
    assert tts_language_code("") == "de"
    assert tts_language_code("de") == "de"
    assert tts_language_code("de-DE") == "de"
    assert tts_language_code("en") == "en"
    assert tts_language_code("en-US") == "en"


def test_audio_script_prompt_is_german() -> None:
    language = _language_label("de")
    prompt = SYSTEM_BRIEFING.format(language=language)
    assert "Deutsch" in prompt
    assert "vollständig auf Deutsch" in prompt
    assert "Keine englischen Sätze" in prompt


def test_german_voices_map_openai_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.studio.media.settings.tts_voice_a", "alloy")
    monkeypatch.setattr("app.services.studio.media.settings.tts_voice_b", "nova")
    monkeypatch.setattr("app.services.studio.media.settings.tts_voice_a_en", "alloy")
    monkeypatch.setattr("app.services.studio.media.settings.tts_voice_b_en", "nova")
    assert voice_for("A", "de") == "de_DE-thorsten-medium"
    assert voice_for("B", "de") == "de_DE-kerstin-low"
    assert voice_for("A", "en") == "alloy"
    assert voice_for("B", "en") == "nova"
    assert OPENAI_TO_PIPER["alloy"] == "de_DE-thorsten-medium"


def test_german_local_kokoro_routes_to_piper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.modalities.piper_ready", lambda: True)
    notebook = SimpleNamespace(tts_provider="local", tts_model="kokoro")
    route = require_tts(notebook, "de")  # type: ignore[arg-type]
    assert route["provider"] == "local"
    assert route["model"] == "piper"
    assert route["api_base"] == "piper"


def test_english_local_kokoro_stays_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.modalities.host_open", lambda _url: True)
    notebook = SimpleNamespace(tts_provider="local", tts_model="kokoro")
    route = require_tts(notebook, "en")  # type: ignore[arg-type]
    assert route["provider"] == "local"
    assert route["model"] == "kokoro"


def test_german_local_kokoro_without_piper_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.modalities.piper_ready", lambda: False)
    notebook = SimpleNamespace(tts_provider="local", tts_model="kokoro")
    with pytest.raises(ValueError, match="Piper-Stimmen fehlen"):
        require_tts(notebook, "de")  # type: ignore[arg-type]


def test_openrouter_german_payload_sets_style() -> None:
    route = {"provider": "openrouter", "model": "openai/gpt-4o-mini-tts"}
    payload = speech_payload(route, "Guten Tag. Dies ist eine kurze Prüfung.", "alloy", "de")
    assert payload["model"] == "openai/gpt-4o-mini-tts"
    assert payload["voice"] == "alloy"
    assert payload["input"] == "Guten Tag. Dies ist eine kurze Prüfung."
    assert payload["instructions"] == GERMAN_SPEECH_STYLE
    assert "Deutsch" in speech_style("de")


def test_local_allowlist_always_includes_piper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.modalities.settings.tts_local_models", "kokoro")
    from app.services.modalities import _local_tts_models

    assert _local_tts_models() == ["piper", "kokoro"]


def test_piper_payload_omits_openrouter_style() -> None:
    route = {"provider": "local", "model": "piper"}
    payload = speech_payload(route, "Guten Tag.", "de_DE-thorsten-medium", "de")
    assert "instructions" not in payload
    assert payload["voice"] == "de_DE-thorsten-medium"
