from types import SimpleNamespace

from app.services.autoname import (
    UNTITLED_TITLE,
    hint_from_skill,
    is_untitled,
    maybe_autoname,
    should_autoname_skill,
    title_from_hint,
)


def test_untitled_default() -> None:
    assert is_untitled(UNTITLED_TITLE)
    assert is_untitled("  ")
    assert not is_untitled("Everlast Consulting")


def test_title_from_hint_cleans_and_truncates() -> None:
    assert title_from_hint("  AI Agency Kickstart  ") == "AI Agency Kickstart"
    assert title_from_hint("https://www.everlast.de/jobs") == "everlast.de"
    assert title_from_hint("Informationen zu einem neuen Thema") == ""
    long = "Wort " * 40
    assert len(title_from_hint(long)) <= 80


def test_autoname_only_once() -> None:
    notebook = SimpleNamespace(title=UNTITLED_TITLE)
    assert maybe_autoname(notebook, "AI Agency Kickstart")
    assert notebook.title == "AI Agency Kickstart"
    assert not maybe_autoname(notebook, "Anderer Titel")
    assert notebook.title == "AI Agency Kickstart"


def test_autoname_skips_custom_title() -> None:
    notebook = SimpleNamespace(title="Mein Notebook")
    assert not maybe_autoname(notebook, "AI Agency")
    assert notebook.title == "Mein Notebook"


def test_skill_hint_prefers_topic() -> None:
    assert hint_from_skill("studio.report", {"topic": "Haftung GmbH"}, {}) == "Haftung GmbH"
    assert hint_from_skill("sources.add_url", {"url": "https://everlast.de"}, {}) == "https://everlast.de"
    assert should_autoname_skill("studio.audio")
    assert should_autoname_skill("notes.create")
    assert not should_autoname_skill("sources.list")
