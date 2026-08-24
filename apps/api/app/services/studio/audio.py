from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models import Artifact, Notebook
from app.services.modalities import require_tts, tts_language_code
from app.services.studio.generate import EVAL_MODE, STUDIO_USER, generate_json, save_artifact, source_ids_from_args, topic_from_args
from app.services.studio.media import artifact_dir, concat_mp3, media_file, speak, voice_for

FILLER = "unser ziel ist es"

SYSTEM_BRIEFING = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Erzeuge ein Audio-Skript nur aus den gelieferten Quellen.
Zwei Sprecher: A und B. Kurzes Briefing.
Sechs bis zehn Wechsel.
Jeder Wechsel nennt einen Fakt aus dem Quellenkontext.
Keine Begrüßung ohne Fakt.
Erfinde keine Fakten.
Jeder Sprechertext ist vollständig auf {language}.
Keine englischen Sätze, außer ein Quellen-Zitat ist auf Englisch.
Antworte nur mit einem JSON-Objekt.
Schema: {{"title": "string", "turns": [{{"speaker": "A", "text": "string"}}]}}
Sprache: {language}.
"""

SYSTEM_EXPLAINER = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Erzeuge ein Audio-Skript nur aus den gelieferten Quellen.
Zwei Sprecher: A und B. Längeres Erklärgespräch.
Zwölf bis achtzehn Wechsel.
Jeder Wechsel nennt einen Fakt aus dem Quellenkontext.
Keine Begrüßung ohne Fakt.
Erfinde keine Fakten.
Jeder Sprechertext ist vollständig auf {language}.
Keine englischen Sätze, außer ein Quellen-Zitat ist auf Englisch.
Antworte nur mit einem JSON-Objekt.
Schema: {{"title": "string", "turns": [{{"speaker": "A", "text": "string"}}]}}
Sprache: {language}.
"""

def _language_label(code: str) -> str:
    return "Englisch" if tts_language_code(code) == "en" else "Deutsch"


def prepare_audio(payload: dict[str, Any], min_turns: int = 6) -> tuple[bool, str]:
    turns = payload.get("turns")
    if not isinstance(turns, list) or len(turns) < min_turns:
        return False, "zu wenige Sprecherwechsel"
    for turn in turns:
        if not isinstance(turn, dict):
            return False, "Wechsel fehlt"
        if not str(turn.get("text") or "").strip():
            return False, "Wechsel ohne Text"
        if str(turn.get("speaker") or "") not in {"A", "B"}:
            return False, "Sprecher ist nicht A oder B"
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
    return await save_artifact(session, notebook, "studio.audio", "audio", title, payload)


async def synthesize_audio(session: AsyncSession, notebook: Notebook, artifact: Artifact) -> None:
    language = tts_language_code(str((artifact.payload or {}).get("language") or "de"))
    require_tts(notebook, language)
    turns = artifact.payload.get("turns") or []
    work = artifact_dir(notebook.id) / f"{artifact.id}-clips"
    work.mkdir(parents=True, exist_ok=True)
    clips = []
    for index, turn in enumerate(turns):
        text = str(turn.get("text") or "").strip()
        if not text:
            continue
        clip = work / f"{index:03d}.mp3"
        clip.write_bytes(speak(notebook, text, voice_for(str(turn.get("speaker") or "A"), language), language))
        clips.append(clip)
    if not clips:
        raise ValueError("Das Audio-Skript hat keinen Text.")
    dest = media_file(notebook.id, artifact.id, "mp3")
    concat_mp3(clips, dest)
    payload = dict(artifact.payload or {})
    payload["status"] = "ready"
    payload["audio_path"] = str(dest)
    artifact.payload = payload
    flag_modified(artifact, "payload")
    await session.commit()
