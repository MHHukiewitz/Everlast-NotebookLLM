import io
import zipfile
from pathlib import Path

import markdown
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


CITED_REPORT = {
    "body_md": "Ingest steht in [1] und lokal in [2].",
    "citations": [
        {"n": 1, "source_id": "s1", "source_title": "Alpha"},
        {"n": 2, "source_id": "s2", "source_title": "Datei"},
    ],
}
CITED_SOURCES = [
    {"id": "s1", "title": "Alpha", "status": "ready", "origin_uri": "https://cite.example/alpha"},
    {"id": "s2", "title": "Datei", "status": "ready", "origin_uri": None},
]


def test_report_markdown_links_sources() -> None:
    text = artifact_markdown("report", "Bericht", CITED_REPORT, CITED_SOURCES)
    assert "[[1]](https://cite.example/alpha)" in text
    assert "## Quellen" in text
    assert "[Alpha](https://cite.example/alpha)" in text
    assert "[2] Datei" in text


def test_report_pdf_embeds_source_url() -> None:
    body = artifact_markdown("report", "Bericht", CITED_REPORT, CITED_SOURCES)
    html_body = markdown.markdown(body, extensions=["tables", "fenced_code"])
    assert 'href="https://cite.example/alpha"' in html_body
    data, media, _filename = export_artifact(
        "report", "Bericht", CITED_REPORT, "pdf", CITED_SOURCES
    )
    assert media == "application/pdf"
    assert data.startswith(b"%PDF")


def test_slides_html_links_sources() -> None:
    payload = {
        "slides": [{"heading": "Ingest [1]", "bullets": ["Holt PDF [1]"], "notes": "Siehe [1]"}],
        "citations": [{"n": 1, "source_title": "Alpha", "url": "https://cite.example/alpha"}],
    }
    data, _media, _filename = export_artifact("slides", "Folien", payload, "html")
    text = data.decode("utf-8")
    assert 'href="https://cite.example/alpha"' in text
    assert "Quellen" in text


def test_table_csv_appends_source_urls() -> None:
    payload = {
        "columns": ["Schicht", "Inhalt"],
        "rows": [["Ingest [1]", "PDF"]],
        "citations": [{"n": 1, "source_title": "Alpha", "url": "https://cite.example/alpha"}],
    }
    data, _media, _filename = export_artifact("table", "Tabelle", payload, "csv")
    text = data.decode("utf-8")
    assert "Quellen" in text
    assert "https://cite.example/alpha" in text


def test_json_export_lists_references() -> None:
    data, _media, _filename = export_artifact(
        "report", "Bericht", CITED_REPORT, "json", CITED_SOURCES
    )
    body = data.decode("utf-8")
    assert "cite.example/alpha" in body
    assert '"references"' in body


def test_note_txt_uses_url_footnotes() -> None:
    payload = {
        "body": "Fact [1].",
        "citations": [{"n": 1, "source_title": "Alpha", "url": "https://cite.example/alpha"}],
    }
    data, _media, _filename = export_artifact("note", "Notiz", payload, "txt")
    text = data.decode("utf-8")
    assert "Fact [1]." in text
    assert "[1] Alpha — https://cite.example/alpha" in text


def test_infographic_svg_links_source_marks() -> None:
    payload = {
        "items": [{"label": "Zahl [1]", "value": "70", "detail": "Quelle [1]"}],
        "citations": [{"n": 1, "source_title": "Alpha", "url": "https://cite.example/alpha"}],
    }
    data, _media, _filename = export_artifact("infographic", "Grafik", payload, "svg")
    text = data.decode("utf-8")
    assert 'href="https://cite.example/alpha"' in text
    assert "cite.example/alpha" in text


def test_slides_pptx_embeds_source_url() -> None:
    payload = {
        "slides": [{"heading": "Ingest [1]", "bullets": ["Holt PDF [1]"], "notes": ""}],
        "citations": [{"n": 1, "source_title": "Alpha", "url": "https://cite.example/alpha"}],
    }
    data, _media, _filename = export_artifact("slides", "Folien", payload, "pptx")
    xml = b"".join(
        zipfile.ZipFile(io.BytesIO(data)).read(name)
        for name in zipfile.ZipFile(io.BytesIO(data)).namelist()
        if name.endswith(".xml") or name.endswith(".rels")
    )
    assert b"cite.example" in xml
    assert b"Quellen" in xml
