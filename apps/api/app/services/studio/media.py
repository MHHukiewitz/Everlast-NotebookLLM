import base64
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.models import Artifact, Notebook
from app.services.modalities import image_ready, require_tts, resolve_media
from app.services.pdf import AI_MARK

PAUSE_SEC = 0.35
FRAME_SIZE = (1280, 720)
STYLES = {
    "classic": {"bg": (255, 255, 255), "fg": (31, 31, 31), "muted": (115, 115, 115)},
    "whiteboard": {"bg": (247, 243, 232), "fg": (42, 42, 42), "muted": (110, 100, 80)},
    "kawaii": {"bg": (255, 240, 246), "fg": (91, 33, 182), "muted": (157, 23, 77)},
    "auto": {"bg": (255, 255, 255), "fg": (31, 31, 31), "muted": (115, 115, 115)},
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


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError("ffmpeg konnte die Datei nicht schreiben.")


def _duration(path: Path) -> float:
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
        return 4.0
    return max(1.5, float(result.stdout.strip()))


def speak(notebook: Notebook, text: str, voice: str) -> bytes:
    route = require_tts(notebook)
    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{route['api_base']}/audio/speech",
            headers=route["headers"],
            json={
                "model": route["model"],
                "input": text,
                "voice": voice,
                "response_format": "mp3",
            },
        )
    if response.status_code >= 400:
        raise ValueError(f"Sprachmodell antwortete mit {response.status_code}.")
    if not response.content:
        raise ValueError("Das Sprachmodell lieferte keine Audiodatei.")
    return response.content


def voice_for(speaker: str) -> str:
    if str(speaker).strip().upper() in {"B", "2"}:
        return settings.tts_voice_b
    return settings.tts_voice_a


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


def concat_mp3(clips: list[Path], dest: Path) -> None:
    if len(clips) == 1:
        dest.write_bytes(clips[0].read_bytes())
        return
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
            "-c",
            "copy",
            str(dest),
        ]
    )


def generate_image(notebook: Notebook, prompt: str) -> bytes | None:
    if not image_ready(notebook):
        return None
    route = resolve_media("image", notebook.image_provider, notebook.image_model)
    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{route['api_base']}/images/generations",
            headers=route["headers"],
            json={
                "model": route["model"],
                "prompt": prompt,
                "size": "1280x720",
                "n": 1,
                "response_format": "b64_json",
            },
        )
    if response.status_code >= 400:
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
    max_width = FRAME_SIZE[0] - 160
    y = 80
    for line in _wrap(draw, heading, title_font, max_width):
        draw.text((80, y), line, font=title_font, fill=theme["fg"])
        y += 52
    y += 16
    for bullet in bullets:
        for index, line in enumerate(_wrap(draw, str(bullet), body_font, max_width - 24)):
            prefix = "• " if index == 0 else "  "
            draw.text((80, y), f"{prefix}{line}", font=body_font, fill=theme["fg"])
            y += 36
        y += 8
    draw.text((80, FRAME_SIZE[1] - 48), AI_MARK, font=mark_font, fill=theme["muted"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="PNG")


def write_frame(notebook: Notebook, heading: str, bullets: list[str], style: str, dest: Path) -> None:
    prompt = f"{style} presentation slide, no text: {heading}. {'; '.join(str(item) for item in bullets[:3])}"
    raw = generate_image(notebook, prompt)
    if raw:
        dest.write_bytes(raw)
        return
    render_style_frame(heading, bullets, style, dest)


def join_video(frames: list[tuple[Path, float]], audio: Path, dest: Path) -> None:
    require_ffmpeg()
    work = dest.parent / f"{dest.stem}-edit"
    work.mkdir(parents=True, exist_ok=True)
    listing = work / "frames.txt"
    lines: list[str] = []
    for frame, seconds in frames:
        lines.append(f"file '{frame.resolve()}'")
        lines.append(f"duration {seconds}")
    if frames:
        lines.append(f"file '{frames[-1][0].resolve()}'")
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
            "-i",
            str(audio),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(dest),
        ]
    )


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


async def synthesize_media_isolated(artifact_id: uuid.UUID) -> None:
    async with SessionLocal() as session:
        await synthesize_media(session, artifact_id)
