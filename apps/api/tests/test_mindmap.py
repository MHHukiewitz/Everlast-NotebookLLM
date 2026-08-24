from app.services.skills import REGISTRY
from app.services.studio.export import export_artifact
from app.services.studio.generate import RENDER_RETRIES
from app.services.studio.mindmap import (
    SKILL_GUIDE,
    check_mindmap,
    normalize_mermaid,
    parse_mindmap,
)


def test_normalize_mermaid_oneline() -> None:
    source = "root((Thema)) Zweig(KI-Beratung) Knoten(Datenschutz)"
    text = normalize_mermaid(source)
    lines = text.split("\n")
    assert lines[0] == "mindmap"
    assert "root((Thema))" in lines[1]
    assert lines[2].startswith("    ")
    assert "KI-Beratung" in text
    assert "n1(" in text or "n1[" in text


def test_normalize_mermaid_literal_newlines() -> None:
    text = normalize_mermaid(r"mindmap\nroot((Ingest))\nPDF")
    assert text.split("\n")[0] == "mindmap"
    assert "root((Ingest))" in text
    assert "PDF" in text


def test_normalize_keeps_indented_map() -> None:
    text = normalize_mermaid("mindmap\n  root((Ingest))\n    PDF\n      Text")
    assert "root((Ingest))" in text
    assert "PDF" in text
    assert "Text" in text


def test_skill_guide_includes_sample() -> None:
    assert "mindmap" in SKILL_GUIDE
    assert "Wurzel" in SKILL_GUIDE
    assert "root((Kern))" not in SKILL_GUIDE
    assert "Aspekt" not in SKILL_GUIDE
    assert "Thema" not in SKILL_GUIDE
    assert "Zweig" not in SKILL_GUIDE
    assert "Punkt" not in SKILL_GUIDE
    assert "Ingest" not in SKILL_GUIDE
    assert REGISTRY["studio.mindmap"].description_full == SKILL_GUIDE


def test_normalize_makes_duplicate_ids_unique() -> None:
    text = normalize_mermaid("  root((Thema))\n    Knoten(A)\n    Knoten(B)")
    assert text.startswith("mindmap")
    assert "n1(A)" in text
    assert "n2(B)" in text


def test_normalize_strips_list_markers() -> None:
    text = normalize_mermaid(
        "mindmap\n  root((Angebot))\n    n1[- Zertifizierung und Prüfung]\n      n2[+ Offizielles Zertifikat]"
    )
    assert "[-" not in text
    assert "[+" not in text
    assert "Zertifizierung und Prüfung" in text
    assert check_mindmap(text) == (True, "")


def test_check_mindmap_rejects_list_markers() -> None:
    ok, reason = check_mindmap("mindmap\n  root((Ingest))\n    n1[- Zertifizierung]")
    assert ok is False
    assert "Listenzeichen" in reason


def test_check_mindmap_rejects_placeholder_nodes() -> None:
    ok, reason = check_mindmap("mindmap\n  root((Kern))\n    Zweig\n      Punkt")
    assert ok is False
    assert "Platzhalter" in reason


def test_check_mindmap_rejects_short_tree() -> None:
    ok, reason = check_mindmap("mindmap\n  root((Thema))")
    assert ok is False
    assert "wenige" in reason


def test_render_retries_is_three() -> None:
    assert RENDER_RETRIES == 3


def test_parse_mindmap_tree() -> None:
    root = parse_mindmap("mindmap\n  root((Ingest))\n    PDF\n    HTML")
    assert root.label == "Ingest"
    assert [child.label for child in root.children] == ["PDF", "HTML"]


def test_mindmap_png_is_png() -> None:
    data, media, filename = export_artifact(
        "mindmap", "Mindmap", {"mermaid": "root((Thema)) Zweig(Ingest) Knoten(RAG)"}, "png"
    )
    assert media == "image/png"
    assert filename.endswith(".png")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_infographic_png_is_png() -> None:
    data, media, filename = export_artifact(
        "infographic",
        "Grafik",
        {
            "items": [
                {
                    "label": "Zahlen",
                    "number": "70",
                    "suffix": "%",
                    "caption": "Zeitersparnis",
                    "value": "Zeitersparnis",
                }
            ]
        },
        "png",
    )
    assert media == "image/png"
    assert filename.endswith(".png")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
