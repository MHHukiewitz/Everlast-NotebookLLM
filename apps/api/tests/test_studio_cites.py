from app.services.studio.cites import (
    citations_for_export,
    finish_markdown,
    finish_plain,
    html_cite_text,
    markdown_cite_text,
    resolve_citations,
)


def test_markdown_turns_url_cites_into_links() -> None:
    cites = [{"n": 1, "title": "Alpha", "url": "https://a.example/x"}]
    assert markdown_cite_text("Fact [1] and [2, 3].", cites) == "Fact [[1]](https://a.example/x) and [2][3]."


def test_finish_markdown_adds_quellen() -> None:
    cites = [
        {"n": 1, "title": "Alpha", "url": "https://a.example/x"},
        {"n": 2, "title": "Datei", "url": ""},
    ]
    text = finish_markdown("Fact [1] and [2].\n\nMARK\n", cites, "MARK")
    assert "[[1]](https://a.example/x)" in text
    assert "## Quellen" in text
    assert "[Alpha](https://a.example/x)" in text
    assert "[2] Datei" in text
    assert text.strip().endswith("MARK")


def test_finish_plain_uses_url_footnotes() -> None:
    cites = [{"n": 1, "title": "Alpha", "url": "https://a.example/x"}]
    text = finish_plain("Fact [1].\n\nMARK\n", cites, "MARK")
    assert "Fact [1]." in text
    assert "Quellen" in text
    assert "[1] Alpha — https://a.example/x" in text


def test_html_cite_text_makes_anchors() -> None:
    cites = [{"n": 1, "title": "Alpha", "url": "https://a.example/x"}]
    html = html_cite_text("Fact [1] <raw>", cites)
    assert '<a href="https://a.example/x">[1]</a>' in html
    assert "&lt;raw&gt;" in html


def test_resolve_citations_uses_source_origin() -> None:
    payload = {
        "citations": [{"n": 1, "source_id": "s1", "source_title": "Alpha"}],
        "body_md": "Fact [1].",
    }
    sources = [{"id": "s1", "title": "Alpha", "status": "ready", "origin_uri": "https://a.example/x"}]
    resolved = resolve_citations(payload, sources)
    assert resolved[0]["url"] == "https://a.example/x"
    used = citations_for_export(payload, sources)
    assert used[0]["n"] == 1
