import pytest

from app.services.studio.generate import STUDIO_USER, load_json_object, parse_json_object, sanitize_json_escapes, strip_fences


def test_strip_fences_json() -> None:
    raw = "```json\n{\"title\": \"A\"}\n```"
    assert strip_fences(raw) == '{"title": "A"}'


def test_strip_fences_plain() -> None:
    assert strip_fences('{"title": "A"}') == '{"title": "A"}'


def test_sanitize_drops_invalid_escape() -> None:
    assert sanitize_json_escapes(r'{"path": "C:\Program"}') == '{"path": "C:Program"}'


def test_sanitize_keeps_newline_escape() -> None:
    assert r"\n" in sanitize_json_escapes(r'{"m": "a\nb"}')


def test_parse_json_object_from_fences() -> None:
    raw = 'prefix\n```json\n{"title": "Mindmap", "mermaid": "mindmap"}\n```\n'
    data = parse_json_object(raw)
    assert data["title"] == "Mindmap"
    assert data["mermaid"] == "mindmap"


def test_parse_json_object_requires_object() -> None:
    with pytest.raises(ValueError):
        parse_json_object("kein objekt")


def test_load_json_object_accepts_trailing_comma() -> None:
    data = load_json_object('{"title": "A",}')
    assert data == {"title": "A"}


def test_load_json_object_rejects_broken_json() -> None:
    assert load_json_object('{\n  "title": "A"\n  "body": 1\n}') is None


def test_studio_user_includes_prompt() -> None:
    text = STUDIO_USER.replace("{prompt}", "Nur DSGVO-Pflichten").replace("{context}", "[1] Text")
    assert "Nur DSGVO-Pflichten" in text
    assert "[1] Text" in text
