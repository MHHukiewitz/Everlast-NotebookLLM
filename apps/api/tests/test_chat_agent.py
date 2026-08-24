import inspect

from app.schemas import plain_text
from app.services import skills
from app.services.chat_agent import (
    NO_ANSWER,
    SYSTEM,
    extract_leaked_tools,
    is_smalltalk,
    json_object_complete,
    parse_tool_args,
    research_query,
    research_scratch,
    tool_prelude_events,
)


def test_system_uses_exact_no_answer() -> None:
    assert NO_ANSWER in SYSTEM
    assert "Beantworte zuerst die Frage" in SYSTEM
    assert "Verbinde Fakten aus mehreren Quellen" in SYSTEM
    assert "notes.create" not in skills.CHAT_TOOLS
    assert "Ollama" in SYSTEM
    assert "BM25" in SYSTEM
    assert "Hybrid-Search" in SYSTEM
    assert "Langfuse" in SYSTEM
    assert "Schreibe dann keinen weiteren Text" not in SYSTEM


def test_research_query_detects_german_and_english() -> None:
    assert research_query("recherchiere die historische entwicklung von Everlast anhand Zahlen und Fakten")
    assert research_query("Bitte research the company history")
    assert research_query("suche im web nach Everlast")
    assert not research_query("Was steht in den Quellen zu Everlast?")


def test_smalltalk_skips_research() -> None:
    assert is_smalltalk("Hallo")
    assert is_smalltalk("guten Morgen")
    assert not is_smalltalk("recherchiere Everlast")


def test_tool_prelude_event_order() -> None:
    events = tool_prelude_events("call_1", "research.fast", {"query": "Everlast"})
    assert [event["event"] for event in events] == ["tool_start", "tool_name", "tool_args"]
    assert events[0]["call_id"] == "call_1"
    assert events[1]["call_id"] == "call_1"
    assert events[1]["skill_id"] == "research.fast"
    assert events[1]["name"]
    assert events[2]["call_id"] == "call_1"
    assert "Everlast" in events[2]["delta"]


def test_json_object_complete_and_parse() -> None:
    assert json_object_complete('{"query": "Everlast"}')
    assert not json_object_complete('{"query":')
    assert parse_tool_args('{"query": "Everlast"}') == {"query": "Everlast"}
    assert parse_tool_args('{"query":') is None


def test_research_scratch_lists_candidates() -> None:
    text, cites = research_scratch("# Bericht", [{"title": "T", "url": "https://x.example", "quote": "Zahl 12"}])
    assert "Recherche-Scratch" in text
    assert "https://x.example" in text
    assert cites[0]["url"] == "https://x.example"
    assert cites[0]["n"] == 1


def test_leaked_tool_extract() -> None:
    cleaned, calls = extract_leaked_tools('Hallo {"name": "sources.list", "arguments": {}} Ende')
    assert "Hallo" in cleaned
    assert "Ende" in cleaned
    assert calls[0]["name"] == "sources.list"


def test_leaked_notes_create_is_stripped_not_run() -> None:
    raw = (
        '{"name": "notes_create", "arguments": {"title": "Mike Hukiewitz - Everlast Kandidat", '
        '"body": "Die Quellen enthalten dazu keine klare Antwort.", "message_id": "123456"}}'
    )
    cleaned, calls = extract_leaked_tools(raw)
    assert "notes_create" not in cleaned
    assert "keine klare Antwort" not in cleaned
    assert calls == []


def test_plain_text_strips_control_chars() -> None:
    assert "\x0b" not in plain_text("Hallo\x0bWelt\nOK")
    assert "Hallo Welt\nOK" == plain_text("Hallo\x0bWelt\nOK")


def test_research_skills_enqueue_only() -> None:
    fast = inspect.getsource(skills._research_fast)
    deep = inspect.getsource(skills._research_deep)
    assert "run_research_job" not in fast
    assert "run_research_job" not in deep
    assert "enqueue_research" in fast
    assert "enqueue_research" in deep
