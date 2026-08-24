import io
import zipfile
from pathlib import Path

import pytest

from app.services.pdf import AI_MARK
from app.services.studio.export import FORMATS, artifact_markdown, export_artifact

BINARY_FORMATS = {"pdf", "pptx", "mp3", "mp4", "png"}

FIXTURES: dict[str, tuple[str, dict]] = {
    "note": ("Notiz", {"body": "Kurzer Text über Ingest."}),
    "report": ("Bericht", {"body_md": "# Bericht\n\nIngest und Embeddings.\n\nDieser Bericht ist KI-generiert."}),
    "mindmap": ("Mindmap", {"mermaid": "mindmap\n  root((Ingest))"}),
    "quiz": (
        "Quiz",
        {
            "questions": [
                {
                    "question": "Was ist Ingest?",
                    "choices": ["A", "B", "C", "D"],
                    "answer_index": 0,
                    "explanation": "Schicht 1",
                }
            ]
        },
    ),
    "flashcards": (
        "Karten",
        {"cards": [{"front": "Ingest", "back": "Holt Dokumente", "cite": "[1]"}]},
    ),
    "table": (
        "Tabelle",
        {"columns": ["Schicht", "Inhalt"], "rows": [["Ingest", "PDF und HTML"], ["Embeddings", "Vektoren"]]},
    ),
    "slides": (
        "Folien",
        {"slides": [{"heading": "Ingest", "bullets": ["Holt PDF"], "notes": "Schicht 1"}]},
    ),
    "infographic": (
        "Grafik",
        {"items": [{"label": "Schicht 1", "value": "Ingest", "detail": "Holt Dokumente"}]},
    ),
    "audio": (
        "Ton",
        {"turns": [{"speaker": "A", "text": "Ingest holt Dateien."}, {"speaker": "B", "text": "Embeddings bleiben lokal."}]},
    ),
    "video": (
        "Film",
        {
            "scenes": [
                {"heading": "Ingest", "bullets": ["Holt PDF"], "narration": "Ingest holt Dateien."}
            ]
        },
    ),
}


def test_every_listed_format_returns_bytes(tmp_path: Path) -> None:
    audio_file = tmp_path / "a.mp3"
    video_file = tmp_path / "v.mp4"
    audio_file.write_bytes(b"ID3fake")
    video_file.write_bytes(b"ftypfake")
    for artifact_type, formats in FORMATS.items():
        title, payload = FIXTURES[artifact_type]
        if artifact_type == "audio":
            payload = {**payload, "audio_path": str(audio_file)}
        if artifact_type == "video":
            payload = {**payload, "video_path": str(video_file)}
        for fmt in formats:
            data, media, filename = export_artifact(artifact_type, title, payload, fmt)
            assert data
            assert media
            assert filename.endswith(f".{fmt}")
            if fmt not in BINARY_FORMATS:
                assert AI_MARK in data.decode("utf-8")


def test_unknown_format_raises() -> None:
    with pytest.raises(ValueError):
        export_artifact("note", "X", {"body": "y"}, "docx")


def test_artifact_markdown_covers_all_types() -> None:
    for artifact_type, (title, payload) in FIXTURES.items():
        text = artifact_markdown(artifact_type, title, payload)
        assert title in text
        assert AI_MARK in text


def test_unknown_artifact_markdown_raises() -> None:
    with pytest.raises(ValueError, match="keinen Text"):
        artifact_markdown("unknown", "X", {})


def test_slides_pptx_is_office_zip() -> None:
    title, payload = FIXTURES["slides"]
    data, media, filename = export_artifact("slides", title, payload, "pptx")
    assert filename.endswith(".pptx")
    assert "presentationml" in media
    assert data[:2] == b"PK"
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert any(name.startswith("ppt/slides/slide") for name in names)
    xml = b"".join(
        zipfile.ZipFile(io.BytesIO(data)).read(name) for name in names if name.endswith(".xml")
    )
    assert title.encode("utf-8") in xml
    assert AI_MARK.encode("utf-8") in xml


def test_slides_html_has_heading() -> None:
    title, payload = FIXTURES["slides"]
    data, media, _filename = export_artifact("slides", title, payload, "html")
    text = data.decode("utf-8")
    assert media.startswith("text/html")
    assert title in text
    assert "Ingest" in text
    assert AI_MARK in text


def test_table_csv_has_header() -> None:
    data, media, _filename = export_artifact(
        "table", "Tabelle", FIXTURES["table"][1], "csv"
    )
    assert media.startswith("text/csv")
    assert data.decode("utf-8").startswith("Schicht,Inhalt")
