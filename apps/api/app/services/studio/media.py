import base64
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.db import SessionLocal
from app.models import Artifact, Notebook
from app.services.modalities import (
    image_ready,
    normalize_openrouter_tts,
    require_tts,
    resolve_media,
    tts_language_code,
)
from app.services.load import heavy_job
from app.services.piper_tts import synthesize_wav
from app.services.pdf import AI_MARK

PAUSE_SEC = 0.35
END_PAD_SEC = 0.35
CLIP_PAD_SEC = 0.2
FRAME_SIZE = (1280, 720)
STYLES = {
    "classic": {
        "bg": (255, 255, 255),
        "fg": (31, 31, 31),
        "muted": (115, 115, 115),
        "accent": (15, 76, 129),
    },
    "whiteboard": {
        "bg": (247, 243, 232),
        "fg": (42, 42, 42),
        "muted": (110, 100, 80),
        "accent": (166, 124, 0),
    },
    "kawaii": {
        "bg": (255, 240, 246),
        "fg": (91, 33, 182),
        "muted": (157, 23, 77),
        "accent": (219, 39, 119),
    },
    "auto": {
        "bg": (255, 255, 255),
        "fg": (31, 31, 31),
        "muted": (115, 115, 115),
        "accent": (15, 76, 129),
    },
}


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise ValueError("ffmpeg fehlt. Installiere ffmpeg für Video.")


def artifact_dir(notebook_id: uuid.UUID) -> Path:
    path = Path(settings.file_store) / str(notebook_id) / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def media_file(notebook_id: uuid.UUID, artifact_id: uuid.UUID, ext: str) -> Path:
    return artifact_dir(notebook_id) / f"{artifact_id}.{ext}"


def remove_artifact_files(notebook_id: uuid.UUID, artifact_id: uuid.UUID) -> None:
    folder = Path(settings.file_store) / str(notebook_id) / "artifacts"
    if not folder.is_dir():
        return
    prefix = str(artifact_id)
    for path in folder.iterdir():
        if path.name != prefix and not path.name.startswith(f"{prefix}.") and not path.name.startswith(f"{prefix}-"):
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError("ffmpeg konnte die Datei nicht schreiben.")


def media_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return 0.0
    return float(result.stdout.strip())


def _duration(path: Path) -> float:
    seconds = media_duration(path)
    if seconds <= 0:
        return 4.0
    return max(1.5, seconds)


GERMAN_SPEECH_STYLE = "Sprich klar und natürlich auf Deutsch. Kein Englisch."
ENGLISH_SPEECH_STYLE = "Speak clearly and naturally in English."
OPENAI_TTS_VOICES = frozenset(
    {
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "fable",
        "nova",
        "onyx",
        "shimmer",
        "verse",
        "marin",
        "cedar",
    }
)
OPENAI_TO_PIPER = {
    "alloy": "de_DE-thorsten-medium",
    "echo": "de_DE-thorsten-medium",
    "onyx": "de_DE-thorsten-medium",
    "nova": "de_DE-kerstin-low",
    "shimmer": "de_DE-kerstin-low",
    "coral": "de_DE-kerstin-low",
}
GEMINI_TTS_VOICES = frozenset(
    {
        "Achernar",
        "Achird",
        "Algenib",
        "Algieba",
        "Alnilam",
        "Aoede",
        "Autonoe",
        "Callirrhoe",
        "Charon",
        "Despina",
        "Enceladus",
        "Erinome",
        "Fenrir",
        "Gacrux",
        "Iapetus",
        "Kore",
        "Laomedeia",
        "Leda",
        "Orus",
        "Pulcherrima",
        "Puck",
        "Rasalgethi",
        "Sadachbia",
        "Sadaltager",
        "Schedar",
        "Sulafat",
        "Umbriel",
        "Vindemiatrix",
        "Zephyr",
        "Zubenelgenubi",
    }
)
OPENAI_TO_GEMINI = {
    "alloy": "Orus",
    "ash": "Puck",
    "echo": "Orus",
    "onyx": "Charon",
    "nova": "Zephyr",
    "shimmer": "Kore",
    "coral": "Sulafat",
    "fable": "Puck",
    "verse": "Iapetus",
    "marin": "Aoede",
    "cedar": "Charon",
}


def media_progress(kind: str, index: int, total: int, step: str) -> str:
    if index <= 0:
        return step
    label = "Szene" if kind == "video" else "Absatz"
    return f"{label} {index}/{total}: {step}"


async def save_media_payload(session: AsyncSession, artifact: Artifact, **updates: Any) -> None:
    payload = dict(artifact.payload or {})
    payload.update(updates)
    artifact.payload = payload
    flag_modified(artifact, "payload")
    await session.commit()


def speech_style(language: str | None) -> str:
    if tts_language_code(language) == "en":
        return ENGLISH_SPEECH_STYLE
    return GERMAN_SPEECH_STYLE


def openai_tts_voice(voice: str) -> str:
    if voice in OPENAI_TTS_VOICES:
        return voice
    if "kerstin" in voice:
        return settings.tts_voice_b_en if settings.tts_voice_b_en in OPENAI_TTS_VOICES else "nova"
    return settings.tts_voice_a_en if settings.tts_voice_a_en in OPENAI_TTS_VOICES else "alloy"


def gemini_tts_voice(voice: str) -> str:
    if voice in GEMINI_TTS_VOICES:
        return voice
    mapped = OPENAI_TO_GEMINI.get(voice)
    if mapped:
        return mapped
    if "kerstin" in voice:
        return "Zephyr"
    return "Orus"


def uses_gemini_tts(model: str) -> bool:
    return "gemini" in (model or "") or (model or "").startswith("google/")


def speech_payload(route: dict[str, Any], text: str, voice: str, language: str | None = "de") -> dict[str, Any]:
    model = route["model"]
    if route.get("provider") == "openrouter":
        model = normalize_openrouter_tts(model)
    payload = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": "mp3",
    }
    if route.get("provider") != "openrouter":
        return payload
    if uses_gemini_tts(model):
        payload["voice"] = gemini_tts_voice(voice)
        payload["response_format"] = "pcm"
        return payload
    payload["voice"] = openai_tts_voice(voice)
    payload["provider"] = {"options": {"openai": {"instructions": speech_style(language)}}}
    return payload


def speech_request(
    route: dict[str, Any], text: str, voice: str, language: str | None = "de"
) -> tuple[str, dict[str, str], dict[str, Any]]:
    return (
        f"{route['api_base']}/audio/speech",
        dict(route.get("headers") or {}),
        speech_payload(route, text, voice, language),
    )


def pcm_params(content_type: str) -> tuple[int, int]:
    rate = 24000
    channels = 1
    for part in (content_type or "").split(";"):
        item = part.strip().lower()
        if item.startswith("rate=") and item[5:].isdigit():
            rate = int(item[5:])
        if item.startswith("channels=") and item[9:].isdigit():
            channels = int(item[9:])
    return rate, channels


def pcm_to_mp3(pcm: bytes, rate: int = 24000, channels: int = 1) -> bytes:
    if not pcm:
        raise ValueError("Das Sprachmodell lieferte keine Audiodatei.")
    work = Path(tempfile.mkdtemp(prefix="tts-pcm-"))
    raw = work / "speech.pcm"
    dest = work / "speech.mp3"
    raw.write_bytes(pcm)
    _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "s16le",
            "-ar",
            str(rate),
            "-ac",
            str(channels),
            "-i",
            str(raw),
            "-af",
            f"apad=pad_dur={CLIP_PAD_SEC}",
            "-q:a",
            "9",
            "-acodec",
            "libmp3lame",
            str(dest),
        ]
    )
    if not dest.exists() or dest.stat().st_size == 0:
        raise ValueError("ffmpeg konnte die Sprachdatei nicht schreiben.")
    return dest.read_bytes()


def wav_to_mp3(wav: Path) -> bytes:
    dest = wav.with_suffix(".mp3")
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(wav),
            "-af",
            f"apad=pad_dur={CLIP_PAD_SEC}",
            "-q:a",
            "9",
            "-acodec",
            "libmp3lame",
            str(dest),
        ]
    )
    if not dest.exists() or dest.stat().st_size == 0:
        raise ValueError("ffmpeg konnte die Sprachdatei nicht schreiben.")
    return dest.read_bytes()


def speak_piper(text: str, voice: str) -> bytes:
    work = Path(tempfile.mkdtemp(prefix="piper-"))
    wav = work / "speech.wav"
    synthesize_wav(text, voice, wav)
    return wav_to_mp3(wav)


def speak(notebook: Notebook, text: str, voice: str, language: str | None = "de") -> bytes:
    route = require_tts(notebook, language)
    if route.get("model") == "piper":
        return speak_piper(text, voice)
    url, headers, payload = speech_request(route, text, voice, language)
    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, headers=headers, json=payload)
    if response.status_code >= 400:
        detail = (response.text or "").strip().replace("\n", " ")[:180]
        suffix = f" {detail}" if detail else ""
        raise ValueError(f"Sprachmodell antwortete mit {response.status_code}.{suffix}")
    if not response.content:
        raise ValueError("Das Sprachmodell lieferte keine Audiodatei.")
    content_type = (response.headers.get("content-type") or "").lower()
    if payload.get("response_format") == "pcm" or content_type.startswith("audio/pcm"):
        rate, channels = pcm_params(content_type)
        return pcm_to_mp3(response.content, rate, channels)
    return response.content


def voice_for(speaker: str, language: str | None = "de", provider: str | None = None) -> str:
    secondary = str(speaker).strip().upper() in {"B", "2"}
    if provider in {"openrouter", "eu"} or tts_language_code(language) == "en":
        return settings.tts_voice_b_en if secondary else settings.tts_voice_a_en
    raw = settings.tts_voice_b if secondary else settings.tts_voice_a
    return OPENAI_TO_PIPER.get(raw, raw)


def write_silence(path: Path, seconds: float = PAUSE_SEC) -> None:
    require_ffmpeg()
    _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=24000:cl=mono",
            "-t",
            str(seconds),
            "-q:a",
            "9",
            "-acodec",
            "libmp3lame",
            str(path),
        ]
    )


def hold_durations(clips: list[Path]) -> list[float]:
    durations = [_duration(clip) for clip in clips]
    if not durations:
        return []
    for index in range(len(durations) - 1):
        durations[index] += PAUSE_SEC
    durations[-1] += END_PAD_SEC
    return durations


def concat_mp3(clips: list[Path], dest: Path) -> None:
    if shutil.which("ffmpeg") is None:
        dest.write_bytes(b"".join(clip.read_bytes() for clip in clips))
        return
    work = dest.parent / f"{dest.stem}-parts"
    work.mkdir(parents=True, exist_ok=True)
    silence = work / "silence.mp3"
    write_silence(silence)
    listing = work / "concat.txt"
    lines: list[str] = []
    for index, clip in enumerate(clips):
        lines.append(f"file '{clip.resolve()}'")
        if index < len(clips) - 1:
            lines.append(f"file '{silence.resolve()}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-af",
            f"apad=pad_dur={END_PAD_SEC}",
            "-q:a",
            "9",
            "-acodec",
            "libmp3lame",
            str(dest),
        ]
    )


def image_request(provider: str, model_id: str, prompt: str) -> tuple[str, dict[str, Any], dict[str, str]]:
    route = resolve_media("image", provider, model_id)
    if provider == "openrouter":
        return (
            f"{route['api_base']}/images",
            {"model": route["model"], "prompt": prompt, "aspect_ratio": "16:9", "n": 1},
            route["headers"],
        )
    return (
        f"{route['api_base']}/images/generations",
        {
            "model": route["model"],
            "prompt": prompt,
            "size": "1280x720",
            "n": 1,
            "response_format": "b64_json",
        },
        route["headers"],
    )


def generate_image(notebook: Notebook, prompt: str) -> bytes | None:
    if not image_ready(notebook):
        return None
    url, payload, headers = image_request(notebook.image_provider, notebook.image_model, prompt)
    with httpx.Client(timeout=180.0) as client:
        response = client.post(url, headers=headers, json=payload)
    if response.status_code >= 400:
        if notebook.image_provider == "openrouter":
            raise ValueError(f"OpenRouter Bildmodell antwortete mit {response.status_code}.")
        return None
    body = response.json()
    items = body.get("data") or []
    if not items:
        return None
    raw = items[0].get("b64_json")
    if raw:
        return base64.b64decode(raw)
    url = items[0].get("url")
    if not url:
        return None
    with httpx.Client(timeout=60.0) as client:
        image = client.get(url)
    if image.status_code >= 400 or not image.content:
        return None
    return image.content


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def render_style_frame(heading: str, bullets: list[str], style: str, dest: Path) -> None:
    theme = STYLES.get(style) or STYLES["classic"]
    image = Image.new("RGB", FRAME_SIZE, theme["bg"])
    draw = ImageDraw.Draw(image)
    title_font = _font(42)
    body_font = _font(26)
    mark_font = _font(14)
    left = 80
    max_width = FRAME_SIZE[0] - 160
    footer_y = FRAME_SIZE[1] - 56
    draw.rectangle((0, 0, 16, FRAME_SIZE[1]), fill=theme["accent"])
    draw.rectangle((0, 0, FRAME_SIZE[0], 8), fill=theme["accent"])
    y = 64
    title_lines = _wrap(draw, heading, title_font, max_width)
    for line in title_lines:
        draw.text((left, y), line, font=title_font, fill=theme["fg"])
        y += 52
    draw.rectangle((left, y + 4, left + 160, y + 8), fill=theme["accent"])
    y += 28
    for bullet in bullets:
        wrapped = _wrap(draw, str(bullet), body_font, max_width - 36)
        needed = 36 * len(wrapped) + 8
        if y + needed > footer_y:
            break
        for index, line in enumerate(wrapped):
            prefix = "• " if index == 0 else "   "
            draw.text((left, y), f"{prefix}{line}", font=body_font, fill=theme["fg"])
            y += 36
        y += 8
    draw.text((left, footer_y), AI_MARK, font=mark_font, fill=theme["muted"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="PNG")


def write_frame(notebook: Notebook, heading: str, bullets: list[str], style: str, dest: Path) -> None:
    del notebook
    render_style_frame(heading, bullets, style, dest)


def join_video(frames: list[tuple[Path, float]], audio: Path, dest: Path) -> None:
    require_ffmpeg()
    work = dest.parent / f"{dest.stem}-edit"
    work.mkdir(parents=True, exist_ok=True)
    holds = list(frames)
    audio_dur = media_duration(audio)
    visual_dur = sum(seconds for _, seconds in holds)
    if holds and audio_dur > visual_dur:
        last, seconds = holds[-1]
        holds[-1] = (last, seconds + audio_dur - visual_dur)
    listing = work / "frames.txt"
    lines: list[str] = []
    for frame, seconds in holds:
        lines.append(f"file '{frame.resolve()}'")
        lines.append(f"duration {seconds}")
    if holds:
        lines.append(f"file '{holds[-1][0].resolve()}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(listing),
        "-i",
        str(audio),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
    ]
    if audio_dur > 0:
        cmd.extend(["-t", f"{audio_dur:.3f}"])
    cmd.append(str(dest))
    _run(cmd)


def clip_duration(path: Path) -> float:
    return _duration(path)


async def synthesize_media(session: AsyncSession, artifact_id: uuid.UUID) -> None:
    from app.services.studio.audio import synthesize_audio
    from app.services.studio.video import synthesize_video

    artifact = await session.get(Artifact, artifact_id)
    if artifact is None:
        return
    notebook = await session.get(Notebook, artifact.notebook_id)
    if notebook is None:
        return
    if artifact.type == "audio":
        await synthesize_audio(session, notebook, artifact)
        return
    if artifact.type == "video":
        await synthesize_video(session, notebook, artifact)


async def mark_media_error(artifact_id: uuid.UUID, message: str) -> None:
    async with SessionLocal() as session:
        artifact = await session.get(Artifact, artifact_id)
        if artifact is None:
            return
        await save_media_payload(session, artifact, status="error", progress=message)


async def synthesize_media_isolated(artifact_id: uuid.UUID) -> None:
    async with heavy_job():
        async with SessionLocal() as session:
            try:
                await synthesize_media(session, artifact_id)
                return
            except Exception as exc:
                message = str(exc)
        await mark_media_error(artifact_id, message)
