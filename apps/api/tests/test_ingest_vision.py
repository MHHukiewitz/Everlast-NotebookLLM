import asyncio
import io
from types import SimpleNamespace

import pytest

from PIL import Image

from app.services.ingest import (
    VISION_SYSTEM,
    describe_image,
    extract_upload_text,
    image_data_url,
    is_image_filename,
    vision_messages,
    vision_route,
)


def _png() -> bytes:
    image = Image.new("RGB", (8, 8), (20, 80, 160))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def test_is_image_filename() -> None:
    assert is_image_filename("scan.PNG") is True
    assert is_image_filename("notes.pdf") is False


def test_vision_route_needs_key(monkeypatch) -> None:
    from app.services import ingest

    monkeypatch.setattr(ingest.settings, "hetzner_api_key", "")
    with pytest.raises(ValueError, match="Hetzner"):
        vision_route(None)


def test_vision_route_uses_notebook_model(monkeypatch) -> None:
    from app.services import ingest

    monkeypatch.setattr(ingest.settings, "hetzner_api_key", "test-key")
    monkeypatch.setattr(ingest.settings, "hetzner_models", "Qwen/Qwen3.6-35B-A3B-FP8,Qwen3.8-27B")
    notebook = SimpleNamespace(provider="hetzner", model_id="Qwen3.8-27B")
    assert vision_route(notebook) == ("hetzner", "Qwen3.8-27B")
    assert vision_route(SimpleNamespace(provider="ollama", model_id="llama3.2")) == (
        "hetzner",
        "Qwen/Qwen3.6-35B-A3B-FP8",
    )


def test_image_data_url_is_jpeg() -> None:
    url = image_data_url(_png())
    assert url.startswith("data:image/jpeg;base64,")
    assert len(url) > 40


def test_vision_messages_include_image() -> None:
    messages = vision_messages("data:image/jpeg;base64,abc")
    assert messages[0]["content"] == VISION_SYSTEM
    parts = messages[1]["content"]
    assert parts[0]["type"] == "text"
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"] == "data:image/jpeg;base64,abc"


def test_describe_image_reads_completion(monkeypatch) -> None:
    from app.services import ingest

    monkeypatch.setattr(ingest.settings, "hetzner_api_key", "test-key")
    monkeypatch.setattr(ingest.settings, "hetzner_models", "Qwen/Qwen3.6-35B-A3B-FP8")

    async def fake_complete(provider, model_id, messages, tools=None):
        assert provider == "hetzner"
        assert model_id == "Qwen/Qwen3.6-35B-A3B-FP8"
        assert messages[1]["content"][1]["type"] == "image_url"
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Blaues Quadrat."))])

    monkeypatch.setattr(ingest.router, "complete", fake_complete)
    text = asyncio.run(describe_image(None, _png()))
    assert text == "Blaues Quadrat."


def test_extract_upload_text_keeps_plain_files() -> None:
    text = asyncio.run(extract_upload_text(None, "note.txt", b"Hallo Quelle"))
    assert text == "Hallo Quelle"
