import pytest

from app.services.pdf import AI_MARK
from app.services.studio.export import FORMATS, export_artifact

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
}


def test_every_listed_format_returns_bytes() -> None:
    for artifact_type, formats in FORMATS.items():
        title, payload = FIXTURES[artifact_type]
        for fmt in formats:
            data, media, filename = export_artifact(artifact_type, title, payload, fmt)
            assert data
            assert media
            assert filename.endswith(f".{fmt}")
            if fmt != "pdf":
                assert AI_MARK in data.decode("utf-8")


def test_unknown_format_raises() -> None:
    with pytest.raises(ValueError):
        export_artifact("note", "X", {"body": "y"}, "docx")


def test_table_csv_has_header() -> None:
    data, media, _filename = export_artifact(
        "table", "Tabelle", FIXTURES["table"][1], "csv"
    )
    assert media.startswith("text/csv")
    assert data.decode("utf-8").startswith("Schicht,Inhalt")
