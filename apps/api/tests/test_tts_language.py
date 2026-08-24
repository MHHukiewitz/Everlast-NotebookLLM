from types import SimpleNamespace

import pytest

from app.services.modalities import require_tts, tts_language_code
from app.services.studio.audio import SYSTEM_BRIEFING, SYSTEM_EXPLAINER, _language_label
from app.services.studio.media import (
    GERMAN_SPEECH_STYLE,
    OPENAI_TO_PIPER,
    OPENAI_TTS_VOICES,
    media_progress,
    openai_tts_voice,
    speech_payload,
    speech_request,
    speech_style,
    voice_for,
)


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
    assert "Monolog" in prompt
    assert "Kein Dialog" in prompt
    assert "Keine Sprecher A und B" in prompt
    assert "Zwei Sprecher" not in prompt
    assert '"speaker"' not in prompt
    explainer = SYSTEM_EXPLAINER.format(language=language)
    assert "Monolog" in explainer
    assert "Kein Dialog" in explainer
    assert "Zwei Sprecher" not in explainer


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
    assert "instructions" not in payload
    assert payload["provider"]["options"]["openai"]["instructions"] == GERMAN_SPEECH_STYLE
    assert "Deutsch" in speech_style("de")


def test_openrouter_german_speech_request_rejects_piper_voice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.studio.media.settings.tts_voice_a", "alloy")
    monkeypatch.setattr("app.services.studio.media.settings.tts_voice_a_en", "alloy")
    route = {
        "provider": "openrouter",
        "model": "openai/gpt-4o-mini-tts",
        "api_base": "https://openrouter.ai/api/v1",
        "headers": {"Authorization": "Bearer test"},
    }
    voice = voice_for("A", "de")
    assert voice == "de_DE-thorsten-medium"
    url, _headers, body = speech_request(route, "Guten Tag. Dies ist eine kurze Prüfung.", voice, "de")
    assert url == "https://openrouter.ai/api/v1/audio/speech"
    assert body["voice"] == "alloy"
    assert body["voice"] in OPENAI_TTS_VOICES
    assert "de_DE" not in body["voice"]
    assert "instructions" not in body
    assert body["response_format"] == "mp3"
    assert body["provider"]["options"]["openai"]["instructions"] == GERMAN_SPEECH_STYLE
    assert openai_tts_voice("de_DE-thorsten-medium") == "alloy"
    assert voice_for("A", "de", provider="openrouter") == "alloy"


def test_media_progress_names_scene_and_step() -> None:
    assert media_progress("video", 2, 8, "Sprache wird erzeugt") == "Szene 2/8: Sprache wird erzeugt"
    assert media_progress("audio", 1, 6, "Sprache wird erzeugt") == "Absatz 1/6: Sprache wird erzeugt"
    assert media_progress("video", 0, 8, "Skript fertig. Sprache startet…") == "Skript fertig. Sprache startet…"


def test_local_allowlist_always_includes_piper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.modalities.settings.tts_local_models", "kokoro")
    from app.services.modalities import _local_tts_models

    assert _local_tts_models() == ["piper", "kokoro"]


def test_piper_payload_omits_openrouter_style() -> None:
    route = {"provider": "local", "model": "piper"}
    payload = speech_payload(route, "Guten Tag.", "de_DE-thorsten-medium", "de")
    assert "instructions" not in payload
    assert payload["voice"] == "de_DE-thorsten-medium"
