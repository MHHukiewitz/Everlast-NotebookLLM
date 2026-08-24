from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Artifact, Notebook
from app.services.modalities import require_tts, tts_language_code
from app.services.studio.generate import EVAL_MODE, STUDIO_USER, generate_json, save_artifact, source_ids_from_args, topic_from_args
from app.services.studio.media import (
    artifact_dir,
    concat_mp3,
    hold_durations,
    join_video,
    media_file,
    media_progress,
    require_ffmpeg,
    save_media_payload,
    speak,
    voice_for,
    write_frame,
)

FILLER = "unser ziel ist es"

SYSTEM_BRIEFING = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Erzeuge eine Video-Gliederung nur aus den gelieferten Quellen.
Vier bis sechs Szenen.
Jede Szene hat eine Überschrift, drei bis fünf Stichpunkte und einen kurzen Sprechertext.
Jede Szene nennt einen Fakt aus dem Quellenkontext.
Keine Begrüßung ohne Fakt.
Erfinde keine Fakten.
Überschrift, Stichpunkte und Sprechertext sind vollständig auf {language}.
Keine englischen Sätze, außer ein Quellen-Zitat ist auf Englisch.
Antworte nur mit einem JSON-Objekt.
Schema: {{"title": "string", "scenes": [{{"heading": "string", "bullets": ["string"], "narration": "string"}}]}}
Sprache: {language}.
"""

SYSTEM_EXPLAINER = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Erzeuge eine Video-Gliederung nur aus den gelieferten Quellen.
Sechs bis acht Szenen.
Jede Szene hat eine Überschrift, drei bis fünf Stichpunkte und einen Sprechertext.
Jede Szene nennt einen Fakt aus dem Quellenkontext.
Keine Begrüßung ohne Fakt.
Erfinde keine Fakten.
Überschrift, Stichpunkte und Sprechertext sind vollständig auf {language}.
Keine englischen Sätze, außer ein Quellen-Zitat ist auf Englisch.
Antworte nur mit einem JSON-Objekt.
Schema: {{"title": "string", "scenes": [{{"heading": "string", "bullets": ["string"], "narration": "string"}}]}}
Sprache: {language}.
"""

def _language_label(code: str) -> str:
    return "Englisch" if tts_language_code(code) == "en" else "Deutsch"


def prepare_video(payload: dict[str, Any], min_scenes: int = 4) -> tuple[bool, str]:
    scenes = payload.get("scenes")
    if not isinstance(scenes, list) or len(scenes) < min_scenes:
        return False, "zu wenige Szenen"
    for scene in scenes:
        if not isinstance(scene, dict):
            return False, "Szene fehlt"
        if not str(scene.get("heading") or "").strip():
            return False, "Szene ohne Überschrift"
        bullets = scene.get("bullets")
        if not isinstance(bullets, list) or len(bullets) < 3:
            return False, "Szene hat zu wenige Stichpunkte"
        if not str(scene.get("narration") or "").strip():
            return False, "Szene ohne Sprechertext"
        blob = " ".join(
            [
                str(scene.get("heading") or ""),
                " ".join(str(item) for item in bullets),
                str(scene.get("narration") or ""),
            ]
        ).casefold()
        if EVAL_MODE.get() and FILLER in blob:
            return False, "leere Floskel"
    return True, ""


async def create_video(
    session: AsyncSession, notebook: Notebook, args: dict[str, Any]
) -> dict[str, Any]:
    language_code = tts_language_code(str(args.get("language") or "de"))
    if not EVAL_MODE.get():
        require_tts(notebook, language_code)
        require_ffmpeg()
    topic = topic_from_args(args)
    fmt = str(args.get("format") or "briefing")
    language = _language_label(language_code)
    style = str(args.get("style") or "auto")
    system = (SYSTEM_EXPLAINER if fmt == "explainer" else SYSTEM_BRIEFING).format(language=language)
    min_scenes = 6 if fmt == "explainer" else 4
    payload = await generate_json(
        session,
        notebook,
        topic,
        system,
        STUDIO_USER,
        source_ids_from_args(args),
        check=lambda data: prepare_video(data, min_scenes),
    )
    title = str(payload.get("title") or "Videoübersicht")
    payload["format"] = fmt
    payload["language"] = language_code
    payload["style"] = style
    payload["status"] = "ready" if EVAL_MODE.get() else "pending"
    if payload["status"] == "pending":
        payload["progress"] = "Skript fertig. Sprache startet…"
    return await save_artifact(session, notebook, "studio.video", "video", title, payload)


async def synthesize_video(session: AsyncSession, notebook: Notebook, artifact: Artifact) -> None:
    language = tts_language_code(str((artifact.payload or {}).get("language") or "de"))
    route = require_tts(notebook, language)
    require_ffmpeg()
    scenes = artifact.payload.get("scenes") or []
    style = str(artifact.payload.get("style") or "auto")
    work = artifact_dir(notebook.id) / f"{artifact.id}-video"
    work.mkdir(parents=True, exist_ok=True)
    clips = []
    stills: list[Any] = []
    total = len(scenes)
    voice = voice_for("A", language, provider=route.get("provider"))
    for index, scene in enumerate(scenes, start=1):
        heading = str(scene.get("heading") or "")
        bullets = [str(item) for item in scene.get("bullets") or []]
        narration = str(scene.get("narration") or "").strip() or heading
        await save_media_payload(
            session, artifact, status="pending", progress=media_progress("video", index, total, "Sprache wird erzeugt")
        )
        clip = work / f"{index - 1:03d}.mp3"
        clip.write_bytes(speak(notebook, narration, voice, language))
        clips.append(clip)
        await save_media_payload(
            session, artifact, status="pending", progress=media_progress("video", index, total, "Bild wird erzeugt")
        )
        frame = work / f"{index - 1:03d}.png"
        write_frame(notebook, heading, bullets, style, frame)
        stills.append(frame)
    if not clips:
        raise ValueError("Die Video-Szenen haben keinen Text.")
    await save_media_payload(session, artifact, status="pending", progress="Audio wird verbunden")
    audio = work / "narration.mp3"
    concat_mp3(clips, audio)
    dest = media_file(notebook.id, artifact.id, "mp4")
    await save_media_payload(session, artifact, status="pending", progress="Video wird geschnitten")
    join_video(list(zip(stills, hold_durations(clips))), audio, dest)
    if not dest.exists() or dest.stat().st_size == 0:
        raise ValueError("Die Videodatei ist unvollständig.")
    await save_media_payload(session, artifact, status="ready", progress="", video_path=str(dest))
