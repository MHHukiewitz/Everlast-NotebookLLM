import shutil
import subprocess
from pathlib import Path

import pytest

from PIL import Image

from app.services.studio.media import (
    CLIP_PAD_SEC,
    END_PAD_SEC,
    FRAME_SIZE,
    concat_mp3,
    hold_durations,
    join_video,
    media_duration,
    render_style_frame,
    wav_to_mp3,
    write_frame,
)

ffmpeg_missing = shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None
pytestmark = pytest.mark.skipif(ffmpeg_missing, reason="ffmpeg fehlt")


def _tone_wav(path: Path, seconds: float, freq: int) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={freq}:sample_rate=22050:duration={seconds}",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def _tone_mp3(path: Path, seconds: float, freq: int) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={freq}:sample_rate=22050:duration={seconds}",
            "-q:a",
            "9",
            "-acodec",
            "libmp3lame",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def test_wav_to_mp3_keeps_source_duration_plus_clip_pad(tmp_path: Path) -> None:
    wav = tmp_path / "speech.wav"
    _tone_wav(wav, 2.0, 440)
    dest = tmp_path / "speech.mp3"
    dest.write_bytes(wav_to_mp3(wav))
    assert media_duration(dest) + 0.05 >= 2.0 + CLIP_PAD_SEC


def test_concat_mp3_keeps_last_clip_and_end_pad(tmp_path: Path) -> None:
    clips = []
    lengths = (1.0, 1.0, 3.0)
    for index, seconds in enumerate(lengths):
        clip = tmp_path / f"{index:03d}.mp3"
        _tone_mp3(clip, seconds, 440 + index * 110)
        clips.append(clip)
    dest = tmp_path / "out.mp3"
    concat_mp3(clips, dest)
    listing = dest.parent / f"{dest.stem}-parts" / "concat.txt"
    assert listing.is_file()
    text = listing.read_text(encoding="utf-8")
    assert str(clips[-1].resolve()) in text
    speech = sum(lengths)
    duration = media_duration(dest)
    assert duration + 0.08 >= speech + END_PAD_SEC
    dropped_last = sum(lengths[:-1]) + END_PAD_SEC + 0.5
    assert duration > dropped_last


def test_concat_mp3_single_clip_adds_end_pad(tmp_path: Path) -> None:
    clip = tmp_path / "only.mp3"
    _tone_mp3(clip, 2.0, 330)
    dest = tmp_path / "only-out.mp3"
    concat_mp3([clip], dest)
    assert media_duration(dest) + 0.08 >= 2.0 + END_PAD_SEC


def test_join_video_duration_covers_concatenated_speech(tmp_path: Path) -> None:
    clips = []
    frames = []
    lengths = (1.2, 1.2, 1.8)
    for index, seconds in enumerate(lengths):
        clip = tmp_path / f"{index:03d}.mp3"
        _tone_mp3(clip, seconds, 520 + index * 80)
        clips.append(clip)
        frame = tmp_path / f"{index:03d}.png"
        render_style_frame(f"Szene {index}", ["Punkt"], "classic", frame)
        frames.append((frame, seconds))
    audio = tmp_path / "narration.mp3"
    concat_mp3(clips, audio)
    video = tmp_path / "out.mp4"
    join_video(frames, audio, video)
    audio_dur = media_duration(audio)
    video_dur = media_duration(video)
    assert audio_dur + 0.08 >= sum(lengths) + END_PAD_SEC
    assert video_dur + 0.08 >= audio_dur
    assert hold_durations(clips)[-1] + 0.05 >= media_duration(clips[-1])


def test_write_frame_draws_slide_text_not_a_textless_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called = []
    monkeypatch.setattr("app.services.studio.media.generate_image", lambda *_args, **_kwargs: called.append(True) or b"fake")
    dest = tmp_path / "slide.png"
    write_frame(object(), "Titel der Folie", ["Erster Punkt", "Zweiter Punkt", "Dritter Punkt"], "classic", dest)
    assert dest.is_file()
    assert called == []
    image = Image.open(dest).convert("RGB")
    assert image.size == FRAME_SIZE
    pixels = image.load()
    dark = 0
    for y in range(image.size[1]):
        for x in range(image.size[0]):
            red, green, blue = pixels[x, y]
            if red < 80 and green < 80 and blue < 80:
                dark += 1
    assert dark > 200
