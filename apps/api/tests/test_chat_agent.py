import inspect
import uuid

from app.schemas import plain_text
from app.services import skills
import asyncio
from types import SimpleNamespace

from app.services.chat_agent import (
    NO_ANSWER,
    SYSTEM,
    TOOL_SKIPPED,
    _stream_pass,
    citation_marks,
    expand_grouped_cite_marks,
    finalize_answer,
    context_from_chunks,
    extract_leaked_tools,
    is_smalltalk,
    json_object_complete,
    parse_tool_args,
    research_query,
    research_scratch,
    retrieve_step_detail,
    run_chat,
    run_chat_resume,
    split_incomplete_tool,
    step_event,
    strip_citation_dump,
    strip_self_intro,
    thinking_text,
    delta_stream_parts,
    join_system,
    tool_prelude_events,
    used_citations,
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
    assert "Sage das klar" not in SYSTEM
    assert "Stelle dich nicht vor" in SYSTEM


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


def test_context_from_chunks_numbers_sources() -> None:
    blocks, cites = context_from_chunks(
        [
            {"source_title": "A", "text": "alpha", "source_id": "1", "chunk_id": "c1"},
            {"source_title": "B", "text": "beta", "source_id": "2", "chunk_id": "c2"},
        ]
    )
    assert blocks[0] == "[1] A: alpha"
    assert cites[1]["n"] == 2
    assert cites[1]["source_id"] == "2"


def test_chat_refreshes_after_source_change() -> None:
    src = inspect.getsource(run_chat)
    assert src.count("retrieve_chunks") >= 2
    assert "context_from_chunks" in src


def test_resume_requires_report() -> None:
    src = inspect.getsource(run_chat_resume)
    assert "report_md" in src
    assert "noch nicht fertig" in src


def test_leaked_tool_extract() -> None:
    cleaned, calls = extract_leaked_tools('Hallo {"name": "sources.list", "arguments": {}} Ende')
    assert "Hallo" in cleaned
    assert "Ende" in cleaned
    assert calls[0]["name"] == "sources.list"
    assert calls[0]["runnable"] is True


def test_leaked_notes_create_is_stripped_not_run() -> None:
    raw = (
        '{"name": "notes_create", "arguments": {"title": "Mike Hukiewitz - Everlast Kandidat", '
        '"body": "Die Quellen enthalten dazu keine klare Antwort.", "message_id": "123456"}}'
    )
    cleaned, calls = extract_leaked_tools(raw)
    assert "notes_create" not in cleaned
    assert "keine klare Antwort" not in cleaned
    assert len(calls) == 1
    assert calls[0]["name"] == "notes.create"
    assert calls[0]["runnable"] is False


def test_leaked_tool_shapes() -> None:
    shapes = [
        '{"tool": "notes.create", "parameters": {"title": "x"}}',
        '{"function": {"name": "notes_create", "arguments": {}}}',
        "<tool_call>{\"name\": \"notes_create\", \"arguments\": {}}</tool_call>",
        "```json\n{\"name\": \"notes_create\", \"arguments\": {}}\n```",
    ]
    for raw in shapes:
        cleaned, calls = extract_leaked_tools(raw)
        assert "notes_create" not in cleaned
        assert "notes.create" not in cleaned
        assert calls[0]["name"] == "notes.create"
        assert calls[0]["runnable"] is False


def test_split_incomplete_tool_holds_prefixes() -> None:
    assert split_incomplete_tool("Hallo {") == ("Hallo ", "{")
    assert split_incomplete_tool("Hallo <tool_call>") == ("Hallo ", "<tool_call>")
    visible, held = split_incomplete_tool("Hallo ```json\n")
    assert visible == "Hallo "
    assert held.startswith("```json")
    visible, held = split_incomplete_tool('Text {"name": "notes_create"')
    assert visible == "Text "
    assert held.startswith("{")
    german = "Everlast berät den Mittelstand in Deutschland."
    assert split_incomplete_tool(german) == (german, "")
    visible, held = split_incomplete_tool("Antwort:\n```python\nprint(1)\n")
    assert visible.startswith("Antwort:")
    assert "print(1)" in visible
    assert held == ""


def test_join_system_keeps_one_block() -> None:
    packed = join_system(SYSTEM, "Quellenkontext:\n[1] Everlast: Beratung")
    assert packed.startswith("Du bist Everlast Notebook")
    assert "Quellenkontext:" in packed
    assert packed.count("Quellenkontext:") == 1


def test_delta_stream_parts_hetzner_reasoning_is_content() -> None:
    reasoning = SimpleNamespace(
        content=None,
        reasoning_content="Everlast berät Unternehmen.",
        reasoning=None,
        thinking=None,
        model_extra=None,
    )
    think, content = delta_stream_parts(reasoning, "hetzner")
    assert think == ""
    assert content == "Everlast berät Unternehmen."
    visible = SimpleNamespace(
        content="Sichtbarer Satz.",
        reasoning_content=None,
        reasoning=None,
        thinking=None,
        model_extra=None,
    )
    think, content = delta_stream_parts(visible, "hetzner")
    assert think == ""
    assert content == "Sichtbarer Satz."
    ollama = SimpleNamespace(
        content=None,
        reasoning_content="Nur Denken",
        reasoning=None,
        thinking=None,
        model_extra=None,
    )
    think, content = delta_stream_parts(ollama, "ollama")
    assert think == "Nur Denken"
    assert content == ""


def test_citation_dump_and_used_filter() -> None:
    raw = "[1] [2] [3] [4] [5] [6] [7] [8]\n\nEverlast berät Unternehmen [1]."
    cleaned = strip_citation_dump(raw)
    assert "[2]" not in cleaned
    assert "Everlast berät Unternehmen [1]." in cleaned
    assert citation_marks(cleaned) == {1}
    cites = [{"n": index, "quote": str(index)} for index in range(1, 9)]
    assert [item["n"] for item in used_citations(cleaned, cites)] == [1]
    assert used_citations("Keine Zitate.", cites) == []
    assert expand_grouped_cite_marks("Berlin [7, 5] und [2].") == "Berlin [7][5] und [2]."
    assert citation_marks("Berlin [7, 5] und [2].") == {7, 5, 2}
    grouped = used_citations("Berlin [7, 5].", cites)
    assert [item["n"] for item in grouped] == [5, 7]
    text, used = finalize_answer("Berlin [7, 5].", cites)
    assert text == "Berlin [7][5]."
    assert [item["n"] for item in used] == [5, 7]
    assert strip_self_intro("Ich bin Everlast Notebook, ein KI-System.\n\nBerlin [1].") == "Berlin [1]."
    intro, intro_used = finalize_answer("Ich bin Everlast Notebook, ein KI-System. Berlin [1].", cites)
    assert intro == "Berlin [1]."
    assert [item["n"] for item in intro_used] == [1]


def test_plain_text_strips_control_chars() -> None:
    assert "\x0b" not in plain_text("Hallo\x0bWelt\nOK")
    assert "Hallo Welt\nOK" == plain_text("Hallo\x0bWelt\nOK")


def test_retrieve_step_detail_counts_hits() -> None:
    detail = retrieve_step_detail(
        [
            {"source_id": "a", "text": "eins"},
            {"source_id": "a", "text": "zwei"},
            {"source_id": "b", "text": "drei"},
        ]
    )
    assert detail == "3 Treffer in 2 Quellen"
    assert retrieve_step_detail([]) == "Keine Treffer"
    event = step_event("retrieve", "Quellen durchsuchen", retrieve_step_detail(
        [{"source_id": "a", "text": "x"}] * 8 + [{"source_id": "b", "text": "y"}]
    ))
    assert event["event"] == "step"
    assert event["kind"] == "retrieve"
    assert event["detail"] == "9 Treffer in 2 Quellen"


def test_thinking_text_reads_reasoning_and_thinking() -> None:
    assert thinking_text(SimpleNamespace(reasoning_content="Schritt", thinking=None, model_extra=None)) == "Schritt"
    assert thinking_text(SimpleNamespace(reasoning=None, reasoning_content=None, thinking="Denk", model_extra=None)) == "Denk"
    assert thinking_text(SimpleNamespace(reasoning="Pfad", reasoning_content=None, thinking=None, model_extra=None)) == "Pfad"
    assert thinking_text(SimpleNamespace(reasoning_content=None, thinking=None, model_extra=None)) == ""


def _delta(content=None, reasoning_content=None, thinking=None):
    return SimpleNamespace(
        content=content,
        reasoning_content=reasoning_content,
        thinking=thinking,
        tool_calls=None,
        model_extra=None,
    )


def test_stream_pass_keeps_thinking_out_of_tokens(monkeypatch) -> None:
    async def fake_stream(*_args, **_kwargs):
        yield SimpleNamespace(choices=[SimpleNamespace(delta=_delta(reasoning_content="Ich prüfe die Frage"))])
        yield SimpleNamespace(choices=[SimpleNamespace(delta=_delta(content="Die Antwort."))])

    monkeypatch.setattr("app.services.chat_agent.router.stream_chat", fake_stream)
    executed: list = []

    async def collect():
        events = []
        notebook = SimpleNamespace(provider="ollama", model_id="qwen2.5:7b")
        async for event in _stream_pass(SimpleNamespace(), notebook, [], None, executed):
            events.append(event)
        return events

    events = asyncio.run(collect())
    kinds = [event["event"] for event in events]
    assert kinds.count("think") == 1
    assert events[0]["event"] == "think"
    assert events[0]["text"] == "Ich prüfe die Frage"
    assert "think" not in [event.get("text") for event in events if event["event"] == "token"]
    tokens = "".join(event["text"] for event in events if event["event"] == "token")
    assert tokens == "Die Antwort."
    assert "Ich prüfe" not in tokens
    assert any(event["event"] == "step" and event["kind"] == "write" for event in events)


def test_stream_pass_without_thinking_has_no_think_event(monkeypatch) -> None:
    async def fake_stream(*_args, **_kwargs):
        yield SimpleNamespace(choices=[SimpleNamespace(delta=_delta(content="Nur Text"))])

    monkeypatch.setattr("app.services.chat_agent.router.stream_chat", fake_stream)

    async def collect():
        events = []
        notebook = SimpleNamespace(provider="ollama", model_id="qwen2.5:7b")
        async for event in _stream_pass(SimpleNamespace(), notebook, [], None, []):
            events.append(event)
        return events

    events = asyncio.run(collect())
    assert all(event["event"] != "think" for event in events)
    assert any(event["event"] == "token" and event["text"] == "Nur Text" for event in events)


def test_stream_pass_keeps_spaces_between_chunks(monkeypatch) -> None:
    async def fake_stream(*_args, **_kwargs):
        yield SimpleNamespace(choices=[SimpleNamespace(delta=_delta(content="Hallo "))])
        yield SimpleNamespace(choices=[SimpleNamespace(delta=_delta(content="Welt."))])

    monkeypatch.setattr("app.services.chat_agent.router.stream_chat", fake_stream)

    async def collect():
        events = []
        notebook = SimpleNamespace(provider="ollama", model_id="qwen2.5:7b")
        async for event in _stream_pass(SimpleNamespace(), notebook, [], None, []):
            events.append(event)
        return events

    events = asyncio.run(collect())
    tokens = "".join(event["text"] for event in events if event["event"] == "token")
    assert tokens == "Hallo Welt."


def test_stream_pass_holds_brace_and_skips_notes_create(monkeypatch) -> None:
    async def fake_stream(*_args, **_kwargs):
        yield SimpleNamespace(choices=[SimpleNamespace(delta=_delta(content="{"))])
        yield SimpleNamespace(
            choices=[SimpleNamespace(delta=_delta(content='"name": "notes_create", "arguments": {}}'))]
        )
        yield SimpleNamespace(choices=[SimpleNamespace(delta=_delta(content="Die Antwort bleibt."))])

    async def boom(*_args, **_kwargs):
        raise AssertionError("notes.create must not run")

    monkeypatch.setattr("app.services.chat_agent.router.stream_chat", fake_stream)
    monkeypatch.setattr("app.services.chat_agent.run_skill", boom)
    messages: list = []
    executed: list = []

    async def collect():
        events = []
        notebook = SimpleNamespace(provider="ollama", model_id="qwen2.5:7b")
        async for event in _stream_pass(SimpleNamespace(), notebook, messages, None, executed):
            events.append(event)
        return events

    events = asyncio.run(collect())
    tokens = [event["text"] for event in events if event["event"] == "token"]
    assert all("{" not in text for text in tokens)
    assert "".join(tokens) == "Die Antwort bleibt."
    assert any(event["event"] == "tool_start" for event in events)
    assert any(event["event"] == "tool_name" and event.get("skill_id") == "notes.create" for event in events)
    assert any(event["event"] == "tool_result" and event.get("result") == TOOL_SKIPPED for event in events)
    assert executed[0]["skipped"] is True
    assert executed[0]["skill_id"] == "notes.create"
    assert all(item.get("role") != "tool" for item in messages)
    assert all(not item.get("tool_calls") for item in messages)


def test_stream_pass_skips_native_non_chat_tool(monkeypatch) -> None:
    def tool_delta(name=None, arguments=None, call_id="call_native"):
        return SimpleNamespace(
            content=None,
            reasoning_content=None,
            thinking=None,
            model_extra=None,
            tool_calls=[
                SimpleNamespace(
                    index=0,
                    id=call_id,
                    function=SimpleNamespace(name=name, arguments=arguments),
                )
            ],
        )

    async def fake_stream(*_args, **_kwargs):
        yield SimpleNamespace(choices=[SimpleNamespace(delta=tool_delta(name="notes_create"))])
        yield SimpleNamespace(choices=[SimpleNamespace(delta=tool_delta(arguments="{}"))])

    async def boom(*_args, **_kwargs):
        raise AssertionError("notes.create must not run")

    monkeypatch.setattr("app.services.chat_agent.router.stream_chat", fake_stream)
    monkeypatch.setattr("app.services.chat_agent.run_skill", boom)
    messages: list = []
    executed: list = []

    async def collect():
        events = []
        notebook = SimpleNamespace(provider="ollama", model_id="qwen2.5:7b")
        async for event in _stream_pass(SimpleNamespace(), notebook, messages, None, executed):
            events.append(event)
        return events

    events = asyncio.run(collect())
    assert any(event["event"] == "tool_result" and event.get("result") == TOOL_SKIPPED for event in events)
    assert executed[0]["skipped"] is True
    assert executed[0]["skill_id"] == "notes.create"
    assert all(not item.get("tool_calls") for item in messages)


class _ChatSession:
    def add(self, row) -> None:
        if getattr(row, "id", None) is None:
            row.id = uuid.uuid4()

    async def commit(self) -> None:
        return

    async def flush(self) -> None:
        return

    async def execute(self, *_args, **_kwargs):
        return SimpleNamespace(scalars=lambda: [])


def test_run_chat_emits_retrieve_step(monkeypatch) -> None:
    chunks = [
        {"source_id": "s1", "chunk_id": "c1", "source_title": "A", "text": "Everlast AI"},
        {"source_id": "s2", "chunk_id": "c2", "source_title": "B", "text": "Beratung"},
    ]

    async def fake_ids(*_args, **_kwargs):
        return []

    async def fake_search(*_args, **_kwargs):
        return chunks, "Everlast AI"

    async def fake_stream(*_args, **_kwargs):
        yield SimpleNamespace(choices=[SimpleNamespace(delta=_delta(content="Kurzantwort."))])

    async def fake_record(*_args, **_kwargs):
        return

    monkeypatch.setattr("app.services.chat_agent.selected_source_ids", fake_ids)
    monkeypatch.setattr("app.services.chat_agent.retrieve_chunks", fake_search)
    monkeypatch.setattr("app.services.chat_agent._host_open", lambda *_args, **_kwargs: True)
    monkeypatch.setattr("app.services.chat_agent.router.stream_chat", fake_stream)
    monkeypatch.setattr("app.services.chat_agent.record_generation", fake_record)
    monkeypatch.setattr("app.services.chat_agent.start_trace", lambda *_args, **_kwargs: "trace")
    notebook = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id="default",
        provider="ollama",
        model_id="qwen2.5:7b",
    )

    async def collect():
        events = []
        async for event in run_chat(_ChatSession(), notebook, "Was macht Everlast AI?"):
            events.append(event)
        return events

    events = asyncio.run(collect())
    retrieve = [event for event in events if event.get("event") == "step" and event.get("kind") == "retrieve"]
    assert retrieve
    assert retrieve[0]["detail"].startswith("2 Treffer in 2 Quellen")
    assert all(event["event"] != "think" for event in events)
    done = next(event for event in events if event["event"] == "done")
    assert [item["n"] for item in done["citations"]] == [1, 2]


def test_run_chat_keeps_used_citations_only(monkeypatch) -> None:
    chunks = [
        {"source_id": f"s{index}", "chunk_id": f"c{index}", "source_title": "A", "text": f"text {index}"}
        for index in range(1, 9)
    ]

    async def fake_ids(*_args, **_kwargs):
        return []

    async def fake_search(*_args, **_kwargs):
        return chunks, "Everlast AI"

    async def fake_stream(*_args, **_kwargs):
        yield SimpleNamespace(
            choices=[SimpleNamespace(delta=_delta(content="[1] [2] [3] [4] [5] [6] [7] [8]\n\nEverlast [1]."))]
        )

    async def fake_record(*_args, **_kwargs):
        return

    monkeypatch.setattr("app.services.chat_agent.selected_source_ids", fake_ids)
    monkeypatch.setattr("app.services.chat_agent.retrieve_chunks", fake_search)
    monkeypatch.setattr("app.services.chat_agent._host_open", lambda *_args, **_kwargs: True)
    monkeypatch.setattr("app.services.chat_agent.router.stream_chat", fake_stream)
    monkeypatch.setattr("app.services.chat_agent.record_generation", fake_record)
    monkeypatch.setattr("app.services.chat_agent.start_trace", lambda *_args, **_kwargs: "trace")
    notebook = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id="default",
        provider="ollama",
        model_id="qwen2.5:7b",
    )

    async def collect():
        events = []
        async for event in run_chat(_ChatSession(), notebook, "Was macht Everlast AI?"):
            events.append(event)
        return events

    events = asyncio.run(collect())
    done = next(event for event in events if event["event"] == "done")
    assert [item["n"] for item in done["citations"]] == list(range(1, 9))


def test_research_skills_enqueue_only() -> None:
    fast = inspect.getsource(skills._research_fast)
    deep = inspect.getsource(skills._research_deep)
    assert "run_research_job" not in fast
    assert "run_research_job" not in deep
    assert "enqueue_research" in fast
    assert "enqueue_research" in deep
