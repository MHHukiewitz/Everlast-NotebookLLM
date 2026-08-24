import wave
from functools import lru_cache
from pathlib import Path

from piper import PiperVoice

from app.config import settings

DEFAULT_VOICES = ("de_DE-thorsten-medium", "de_DE-kerstin-low")


def voice_dir() -> Path:
    return Path(settings.tts_piper_voice_dir)


def voice_file(voice: str) -> Path:
    name = voice if voice.endswith(".onnx") else f"{voice}.onnx"
    return voice_dir() / name


def piper_ready(voices: tuple[str, ...] = DEFAULT_VOICES) -> bool:
    return all(voice_file(voice).exists() and voice_file(voice).stat().st_size > 0 for voice in voices)


@lru_cache(maxsize=4)
def load_voice(voice: str) -> PiperVoice:
    path = voice_file(voice)
    if not path.exists() or path.stat().st_size == 0:
        raise ValueError(
            f"Piper-Stimme fehlt: {path.name}. Lege die Datei in {voice_dir()} ab."
        )
    return PiperVoice.load(str(path))


def synthesize_wav(text: str, voice: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    model = load_voice(voice)
    with wave.open(str(dest), "wb") as handle:
        model.synthesize_wav(text, handle)
