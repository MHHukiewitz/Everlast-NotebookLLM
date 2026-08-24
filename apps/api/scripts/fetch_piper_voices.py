"""Download German Piper voices into TTS_PIPER_VOICE_DIR."""

from pathlib import Path

from piper.download_voices import download_voice

from app.config import settings

VOICES = ("de_DE-thorsten-medium", "de_DE-kerstin-low")


def main() -> None:
    dest = Path(settings.tts_piper_voice_dir)
    dest.mkdir(parents=True, exist_ok=True)
    for voice in VOICES:
        download_voice(voice, dest)


if __name__ == "__main__":
    main()
