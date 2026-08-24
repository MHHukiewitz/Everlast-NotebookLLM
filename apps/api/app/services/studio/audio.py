from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Artifact, Notebook
from app.services.modalities import require_tts, tts_language_code
from app.services.studio.generate import EVAL_MODE, STUDIO_USER, generate_json, save_artifact, source_ids_from_args, topic_from_args
from app.services.studio.media import artifact_dir, concat_mp3, media_file, media_progress, save_media_payload, speak, voice_for

FILLER = "unser ziel ist es"

SYSTEM_BRIEFING = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Erzeuge ein Audio-Skript nur aus den gelieferten Quellen.
Ein Sprecher. Ein Monolog. Kein Dialog. Keine Sprecher A und B. Kein Interview.
Kurzes Briefing.
Sechs bis zehn Absätze.
Jeder Absatz nennt einen Fakt aus dem Quellenkontext.
Keine Begrüßung ohne Fakt.
Erfinde keine Fakten.
Der gesamte Text ist vollständig auf {language}.
Keine englischen Sätze, außer ein Quellen-Zitat ist auf Englisch.
Klare Sätze für Sprachausgabe.
Sprich keine Quellennummern und keine Klammermarken wie [1].
Antworte nur mit einem JSON-Objekt.
Schema: {{"title": "string", "turns": [{{"text": "string"}}]}}
Sprache: {language}.
"""

SYSTEM_EXPLAINER = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Erzeuge ein Audio-Skript nur aus den gelieferten Quellen.
Ein Sprecher. Ein Monolog. Kein Dialog. Keine Sprecher A und B. Kein Interview.
Längerer erklärender Monolog.
Zwölf bis achtzehn Absätze.
Jeder Absatz nennt einen Fakt aus dem Quellenkontext.
Keine Begrüßung ohne Fakt.
Erfinde keine Fakten.
Der gesamte Text ist vollständig auf {language}.
Keine englischen Sätze, außer ein Quellen-Zitat ist auf Englisch.
Klare Sätze für Sprachausgabe.
Sprich keine Quellennummern und keine Klammermarken wie [1].
Antworte nur mit einem JSON-Objekt.
Schema: {{"title": "string", "turns": [{{"text": "string"}}]}}
Sprache: {language}.
"""

def _language_label(code: str) -> str:
    return "Englisch" if tts_language_code(code) == "en" else "Deutsch"


def _dialog_speakers(turns: list[Any]) -> bool:
    speakers = {
        str(turn.get("speaker") or "").strip().upper()
        for turn in turns
        if isinstance(turn, dict) and str(turn.get("speaker") or "").strip()
    }
    return bool(speakers & {"A", "1"}) and bool(speakers & {"B", "2"})


def prepare_audio(payload: dict[str, Any], min_turns: int = 6) -> tuple[bool, str]:
    turns = payload.get("turns")
    if not isinstance(turns, list) or len(turns) < min_turns:
        return False, "zu wenige Absätze"
    if _dialog_speakers(turns):
        return False, "Dialog statt Monolog"
    for turn in turns:
        if not isinstance(turn, dict):
            return False, "Absatz fehlt"
        if not str(turn.get("text") or "").strip():
            return False, "Absatz ohne Text"
        if EVAL_MODE.get() and FILLER in str(turn.get("text") or "").casefold():
            return False, "leere Floskel"
    return True, ""


async def create_audio(
    session: AsyncSession, notebook: Notebook, args: dict[str, Any]
) -> dict[str, Any]:
    language_code = tts_language_code(str(args.get("language") or "de"))
    if not EVAL_MODE.get():
        require_tts(notebook, language_code)
    topic = topic_from_args(args)
    fmt = str(args.get("format") or "briefing")
    language = _language_label(language_code)
    system = (SYSTEM_EXPLAINER if fmt == "explainer" else SYSTEM_BRIEFING).format(language=language)
    min_turns = 12 if fmt == "explainer" else 6
    payload = await generate_json(
        session,
        notebook,
        topic,
        system,
        STUDIO_USER,
        source_ids_from_args(args),
        check=lambda data: prepare_audio(data, min_turns),
    )
    title = str(payload.get("title") or "Audio-Zusammenfassung")
    payload["format"] = fmt
    payload["language"] = language_code
    payload["status"] = "ready" if EVAL_MODE.get() else "pending"
    if payload["status"] == "pending":
        payload["progress"] = "Skript fertig. Sprache startet…"
    return await save_artifact(session, notebook, "studio.audio", "audio", title, payload)


async def synthesize_audio(session: AsyncSession, notebook: Notebook, artifact: Artifact) -> None:
    language = tts_language_code(str((artifact.payload or {}).get("language") or "de"))
    route = require_tts(notebook, language)
    turns = artifact.payload.get("turns") or []
    work = artifact_dir(notebook.id) / f"{artifact.id}-clips"
    work.mkdir(parents=True, exist_ok=True)
    clips = []
    voice = voice_for("A", language, provider=route.get("provider"))
    spoken = [turn for turn in turns if str((turn or {}).get("text") or "").strip()]
    total = len(spoken)
    for index, turn in enumerate(spoken, start=1):
        text = str(turn.get("text") or "").strip()
        await save_media_payload(
            session, artifact, status="pending", progress=media_progress("audio", index, total, "Sprache wird erzeugt")
        )
        clip = work / f"{index - 1:03d}.mp3"
        clip.write_bytes(speak(notebook, text, voice, language))
        clips.append(clip)
    if not clips:
        raise ValueError("Das Audio-Skript hat keinen Text.")
    dest = media_file(notebook.id, artifact.id, "mp3")
    await save_media_payload(session, artifact, status="pending", progress="Audio wird verbunden")
    concat_mp3(clips, dest)
    if not dest.exists() or dest.stat().st_size == 0:
        raise ValueError("Die Audiodatei ist unvollständig.")
    await save_media_payload(session, artifact, status="ready", progress="", audio_path=str(dest))
