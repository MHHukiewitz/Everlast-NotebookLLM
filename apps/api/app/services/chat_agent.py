import json
import re
import socket
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Citation, Message, Notebook, ResearchJob, Source
from app.services.connectors import router
from app.services.research import searx_reachable
from app.services.retrieve import hybrid_search, overlap_score
from app.services.skills import CHAT_TOOLS, REGISTRY, resolve_tool_name, run_skill, tool_schema
from app.services.tracing import pack_prompt, record_generation, start_trace

NO_ANSWER = "Die Quellen enthalten dazu keine klare Antwort."
NO_SOURCES = "Ich bin ein KI-System. Füge Quellen hinzu oder stelle eine Frage."
RESEARCH_WAIT = "Ich suche im Web nach weiteren Fakten…"
SEARX_DOWN = "SearXNG ist nicht erreichbar. Starte den SearXNG-Container."
TOOL_SKIPPED = "Nicht ausgeführt"
MAX_TOOL_ROUNDS = 4

SYSTEM = f"""Du bist Everlast Notebook, ein KI-System. Sage das klar.
Antworte auf Deutsch in normaler Sprache.
Beantworte zuerst die Frage. Schreibe nur wenige Sätze.
Schreibe keine JSON-Werkzeugaufrufe in die Antwort.
Lege keine Notiz an, um die Frage zu beantworten.
Für Fakten nutze nur die ausgewählten Quellen im Kontext.
Wenn der Quellenkontext relevante Fakten zur Frage enthält, musst du antworten. Verbinde Fakten aus mehreren Quellen. Nutze dann nicht: {NO_ANSWER}
Wenn der Quellenkontext keine relevanten Fakten zur Frage enthält, antworte genau mit: {NO_ANSWER}
Übernimm Werkzeug- und Methodennamen aus dem Kontext wörtlich: Ollama, BM25, Hybrid-Search, Langfuse.
Erfinde keine Fakten, Zahlen, Namen oder Daten.
Hänge Zitate in der Form [n] an Sätze an, wenn du eine Faktantwort gibst. n ist die Nummer im Quellenkontext.
Schreibe keinen ganzen Architekturbericht, wenn die Frage kurz ist.
Markiere generierten Text als KI-generiert, wenn du einen Bericht schreibst.
Lege, wähle oder lösche Quellen nur über Werkzeuge.
Zum Löschen nutze sources_delete_matching mit einem kurzen Suchbegriff aus Titel oder URL.
"""

RESUME_SYSTEM = f"""Du bist Everlast Notebook, ein KI-System. Sage das klar.
Antworte auf Deutsch in normaler Sprache.
Beantworte zuerst die Frage. Schreibe nur wenige Sätze.
Nutze nur den Recherche-Scratch im Kontext.
Wenn der Scratch die gefragte Tatsache nennt, musst du antworten. Nutze dann nicht: {NO_ANSWER}
Wenn eine Tatsache fehlt, antworte genau mit: {NO_ANSWER}
Übernimm Werkzeug- und Methodennamen aus dem Kontext wörtlich: Ollama, BM25, Hybrid-Search, Langfuse.
Erfinde keine Zahlen und keine Fakten.
Hänge Zitate in der Form [n] an Sätze an, wenn du eine Faktantwort gibst. n ist die Nummer im Scratch.
Markiere generierten Text als KI-generiert, wenn du einen Bericht schreibst.
"""

_TOOL_OBJECT_START = re.compile(r'\{\s*"(?:name|tool|function|parameters)"\s*:')
_TOOL_NAME_HOLD = re.compile(
    r'\{\s*"(?:name|tool)"\s*:\s*"([^"]+)"'
    r'|"function"\s*:\s*\{\s*"name"\s*:\s*"([^"]+)"'
)
_TOOL_CALL_OPEN = re.compile(r"<tool_call>", re.I)
_FENCE_OPEN = re.compile(r"```(?:json)?[ \t]*\n", re.I)
_CITE_MARK = re.compile(r"\[(\d+)\]")
_DUMP_LINE = re.compile(r"^\s*(?:\[\d+\]\s*)+$")
_TOOL_KEY_PREFIX = re.compile(r'\{\s*"([A-Za-z_]*)"?\s*:?')
_DELETE_TARGET = re.compile(
    r"(?:entferne|lösche|löschen|remove|delete)\s+(?:die\s+|das\s+|den\s+|the\s+)?(.+)",
    re.I,
)
_RESEARCH_INTENT = re.compile(
    r"(?:recherchier\w*|suche\s+im\s+web|google\b|finde\s+fakten|research\b)",
    re.I,
)
_SMALLTALK = re.compile(
    r"^(hallo|hi|hey|guten\s+(tag|morgen|abend)|danke|ok|okay|einstellungen|settings)\b",
    re.I,
)


def _host_open(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    sock = socket.socket()
    sock.settimeout(1.0)
    code = sock.connect_ex((host, port))
    sock.close()
    return code == 0


def _tools_for_prompt() -> list[dict[str, Any]]:
    return [tool_schema(skill_id) for skill_id in CHAT_TOOLS]


def can_run_chat_tool(skill_id: str) -> bool:
    return skill_id in CHAT_TOOLS or skill_id.startswith("research.")


def new_call_id() -> str:
    return f"call_{uuid.uuid4().hex[:12]}"


def skill_title(skill_id: str) -> str:
    skill = REGISTRY.get(skill_id)
    if skill is None:
        return skill_id
    return skill.card.title


WRITE_STEP_ID = "write"


def new_step_id() -> str:
    return f"step_{uuid.uuid4().hex[:12]}"


def retrieve_step_detail(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "Keine Treffer"
    sources = {str(chunk.get("source_id") or "") for chunk in chunks}
    sources.discard("")
    return f"{len(chunks)} Treffer in {len(sources)} Quellen"


def tool_args_detail(args: dict[str, Any]) -> str:
    for key in ("query", "url", "title", "text"):
        value = args.get(key)
        if value:
            return str(value)[:80]
    return ""


def tool_result_detail(skill_id: str, args: dict[str, Any], result: Any) -> str:
    if isinstance(result, dict) and "count" in result:
        return f"{result['count']} Quelle(n)"
    if isinstance(result, dict) and result.get("query"):
        return str(result["query"])[:80]
    return tool_args_detail(args) or skill_title(skill_id)


def thinking_text(delta: Any) -> str:
    if delta is None:
        return ""
    for attr in ("reasoning_content", "thinking"):
        value = getattr(delta, attr, None)
        if value:
            return str(value)
    extra = getattr(delta, "model_extra", None) or {}
    if isinstance(extra, dict):
        for key in ("reasoning_content", "thinking"):
            value = extra.get(key)
            if value:
                return str(value)
    return ""


def step_event(
    kind: str,
    title: str,
    detail: str = "",
    status: str = "done",
    step_id: str | None = None,
    call_id: str = "",
) -> dict[str, Any]:
    event = {
        "event": "step",
        "id": step_id or new_step_id(),
        "kind": kind,
        "title": title,
        "detail": detail,
        "status": status,
    }
    if call_id:
        event["call_id"] = call_id
    return event


def record_step(reasoning: list[Any], event: dict[str, Any]) -> None:
    if event.get("event") != "step":
        return
    step = {
        "id": event["id"],
        "title": event["title"],
        "detail": event.get("detail") or "",
        "kind": event["kind"],
    }
    if event.get("call_id"):
        step["call_id"] = event["call_id"]
    for index, item in enumerate(reasoning):
        if isinstance(item, dict) and item.get("id") == step["id"]:
            reasoning[index] = step
            return
    reasoning.append(step)


def delete_target(text: str) -> str:
    match = _DELETE_TARGET.search(text.strip())
    if not match:
        return ""
    target = match.group(1)
    target = re.sub(r"\s+quellen?\s*$", "", target, flags=re.I)
    target = re.sub(r"\s+sources?\s*$", "", target, flags=re.I)
    return target.strip(" .")


def research_query(text: str) -> str:
    if not _RESEARCH_INTENT.search(text.strip()):
        return ""
    return text.strip()


def is_smalltalk(text: str) -> bool:
    return bool(_SMALLTALK.match(text.strip()))


def json_object_complete(text: str) -> bool:
    raw = text.strip()
    if not raw or raw[0] not in "{[":
        return False
    depth = 0
    in_str = False
    escape = False
    for char in raw:
        if in_str:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_str = False
            continue
        if char == '"':
            in_str = True
        elif char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def parse_tool_args(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if not json_object_complete(raw):
        return None
    return json.loads(raw)


def _balanced_object(text: str, start: int) -> str:
    if start >= len(text) or text[start] != "{":
        return ""
    depth = 0
    in_str = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_str:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_str = False
            continue
        if char == '"':
            in_str = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def _tool_call_entry(name: str, args: dict[str, Any]) -> dict[str, Any]:
    raw_name = str(name).strip()
    skill_id = resolve_tool_name(raw_name)
    display = skill_id or raw_name
    return {
        "name": display,
        "arguments": json.dumps(args, ensure_ascii=False),
        "runnable": bool(skill_id and can_run_chat_tool(skill_id)),
    }


def _call_from_parsed(parsed: dict[str, Any]) -> dict[str, Any] | None:
    name = parsed.get("name") or parsed.get("tool")
    fn = parsed.get("function")
    args: Any = parsed.get("arguments")
    if args is None:
        args = parsed.get("parameters")
    if args is None:
        args = parsed.get("args")
    if not name and isinstance(fn, dict):
        name = fn.get("name")
        if args is None:
            args = fn.get("arguments")
        if args is None:
            args = fn.get("parameters")
    if not name:
        return None
    if args is None:
        args = {}
    if isinstance(args, str):
        parsed_args = parse_tool_args(args)
        args = parsed_args if parsed_args is not None else {}
    if not isinstance(args, dict):
        args = {}
    return _tool_call_entry(str(name), args)


def _call_from_leak_text(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    fence = re.fullmatch(r"```(?:json)?\s*(.*)\s*```", text, re.S | re.I)
    if fence:
        text = fence.group(1).strip()
    parsed = parse_tool_args(text)
    if parsed is None:
        obj_at = text.find("{")
        if obj_at >= 0:
            blob = _balanced_object(text, obj_at)
            if blob:
                parsed = parse_tool_args(blob)
    if parsed is not None:
        return _call_from_parsed(parsed)
    name = text.strip().strip("`").strip()
    if not name or any(char in name for char in " \n\t{}[]"):
        return None
    return _tool_call_entry(name, {})


def extract_leaked_tools(text: str) -> tuple[str, list[dict[str, Any]]]:
    spans: list[tuple[int, int, dict[str, Any] | None]] = []
    for found in _TOOL_CALL_OPEN.finditer(text):
        close = re.search(r"</tool_call>", text[found.end() :], re.I)
        if close is None:
            continue
        inner = text[found.end() : found.end() + close.start()]
        spans.append((found.start(), found.end() + close.end(), _call_from_leak_text(inner)))
    for found in _FENCE_OPEN.finditer(text):
        close_at = text.find("```", found.end())
        if close_at < 0:
            continue
        inner = text[found.end() : close_at]
        call = _call_from_leak_text(inner)
        if call is None and _TOOL_OBJECT_START.search(inner) is None:
            continue
        spans.append((found.start(), close_at + 3, call))
    for found in _TOOL_OBJECT_START.finditer(text):
        blob = _balanced_object(text, found.start())
        if not blob:
            continue
        if any(start <= found.start() < end for start, end, _call in spans):
            continue
        spans.append((found.start(), found.start() + len(blob), _call_from_leak_text(blob)))
    spans.sort(key=lambda item: item[0])
    calls: list[dict[str, Any]] = []
    parts: list[str] = []
    index = 0
    for start, end, call in spans:
        if start < index:
            continue
        parts.append(text[index:start])
        if call:
            calls.append(call)
        index = end
    parts.append(text[index:])
    cleaned = re.sub(r"```(?:json)?\s*```", "", "".join(parts), flags=re.I)
    cleaned = re.sub(r"</?tool_call>", "", cleaned, flags=re.I)
    return re.sub(r"\n{3,}", "\n\n", cleaned), calls


def _is_toolish_prefix(rest: str) -> bool:
    if re.match(r"\{\s*$", rest):
        return True
    found = _TOOL_KEY_PREFIX.match(rest)
    if found is None:
        return False
    key = found.group(1).lower()
    return any(candidate.startswith(key) for candidate in ("name", "tool", "function", "parameters"))


def split_incomplete_tool(text: str) -> tuple[str, str]:
    hold_at: int | None = None

    def consider(pos: int) -> None:
        nonlocal hold_at
        if hold_at is None or pos < hold_at:
            hold_at = pos

    for found in _TOOL_CALL_OPEN.finditer(text):
        if re.search(r"</tool_call>", text[found.end() :], re.I) is None:
            consider(found.start())
    for found in _FENCE_OPEN.finditer(text):
        if "```" not in text[found.end() :]:
            consider(found.start())
    fence_tail = re.search(r"```(?:json)?\s*$", text, re.I)
    if fence_tail:
        consider(fence_tail.start())
    for found in _TOOL_OBJECT_START.finditer(text):
        if not _balanced_object(text, found.start()):
            consider(found.start())
    trimmed = text.rstrip()
    if trimmed.endswith("{"):
        consider(len(trimmed) - 1)
    else:
        for index, char in enumerate(text):
            if char != "{":
                continue
            if _balanced_object(text, index):
                continue
            if _is_toolish_prefix(text[index:]):
                consider(index)
                break
    if hold_at is None:
        return text, ""
    return text[:hold_at], text[hold_at:]


def citation_marks(text: str) -> set[int]:
    return {int(found.group(1)) for found in _CITE_MARK.finditer(text or "")}


def strip_citation_dump(text: str) -> str:
    kept = [line for line in (text or "").splitlines() if not _DUMP_LINE.match(line)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def used_citations(text: str, citation_map: list[dict[str, Any]]) -> list[dict[str, Any]]:
    used = citation_marks(text)
    return [item for item in citation_map if item.get("n") in used]


def finalize_answer(text: str, citation_map: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    cleaned = strip_citation_dump(text)
    return cleaned, used_citations(cleaned, citation_map)


def skipped_tool_record(call_id: str, skill_id: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "call_id": call_id,
        "skill_id": skill_id,
        "arguments": args,
        "result": TOOL_SKIPPED,
        "status": "done",
        "skipped": True,
    }


def skipped_tool_finish_events(call_id: str, skill_id: str) -> list[dict[str, Any]]:
    return [
        {"event": "tool_result", "call_id": call_id, "skill_id": skill_id, "result": TOOL_SKIPPED},
        step_event("tool", skill_title(skill_id), TOOL_SKIPPED, step_id=call_id, call_id=call_id),
    ]


async def _emit_leaked_call(
    session: AsyncSession,
    notebook: Notebook,
    messages: list[dict[str, Any]],
    leak: dict[str, Any],
    executed: list[dict[str, Any]],
    call_id: str,
    started: bool,
    args_sent: str,
    visible_pass: str,
) -> AsyncIterator[dict[str, Any]]:
    skill_id = str(leak["name"])
    args = parse_tool_args(str(leak.get("arguments") or "{}")) or {}
    if not started:
        for event in tool_prelude_events(call_id, skill_id, args):
            yield event
    elif args_sent != leak["arguments"]:
        rest = leak["arguments"][len(args_sent) :] if args_sent else leak["arguments"]
        if rest:
            yield {"event": "tool_args", "call_id": call_id, "delta": rest}
    if not leak.get("runnable"):
        executed.append(skipped_tool_record(call_id, skill_id, args))
        for event in skipped_tool_finish_events(call_id, skill_id):
            yield event
        return
    messages.append(
        {
            "role": "assistant",
            "content": visible_pass or None,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": skill_id, "arguments": leak["arguments"]},
                }
            ],
        }
    )
    record = await _run_recorded_skill(session, notebook, skill_id, args, call_id, call_id, messages)
    executed.append(record)
    yield {"event": "tool_result", "call_id": call_id, "skill_id": skill_id, "result": record["result"]}
    yield step_event(
        "tool",
        skill_title(skill_id),
        tool_result_detail(skill_id, args, record["result"]),
        step_id=call_id,
        call_id=call_id,
    )


def tool_prelude_events(call_id: str, skill_id: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
    args_text = json.dumps(arguments, ensure_ascii=False)
    return [
        {"event": "tool_start", "call_id": call_id},
        {"event": "tool_name", "call_id": call_id, "skill_id": skill_id, "name": skill_title(skill_id)},
        {"event": "tool_args", "call_id": call_id, "delta": args_text},
    ]


def research_scratch(report_md: str, candidates: list[Any]) -> tuple[str, list[dict[str, Any]]]:
    blocks = []
    if report_md.strip():
        blocks.append(report_md.strip())
    citation_map: list[dict[str, Any]] = []
    for index, item in enumerate(candidates, start=1):
        title = getattr(item, "title", None) or item.get("title") or ""
        url = getattr(item, "url", None) or item.get("url") or ""
        quote = getattr(item, "quote", None) or item.get("quote") or ""
        blocks.append(f"[{index}] {title} — {url} — {quote}")
        citation_map.append({"n": index, "url": url, "title": title, "quote": quote[:280]})
    return "Recherche-Scratch:\n" + "\n\n".join(blocks), citation_map


async def selected_source_ids(session: AsyncSession, notebook_id: uuid.UUID) -> list[uuid.UUID]:
    rows = (
        await session.execute(
            select(Source.id).where(
                Source.notebook_id == notebook_id,
                Source.selected.is_(True),
                Source.status == "ready",
            )
        )
    ).scalars()
    return list(rows)


async def _save_assistant(
    session: AsyncSession,
    notebook: Notebook,
    *,
    content: str,
    citations: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
    model_label: str,
    trace_id: str | None,
    raw_output: str,
    reasoning: list[Any],
    kind: str,
    prompt: str,
    extra: dict[str, Any],
    latency_ms: int = 0,
) -> Message:
    assistant = Message(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        role="assistant",
        content=content,
        citations=citations,
        tool_calls=tool_calls,
        model=model_label,
        trace_id=trace_id,
        raw_output=raw_output,
        reasoning=reasoning,
    )
    session.add(assistant)
    await session.flush()
    await record_generation(
        session,
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        kind=kind,
        model=model_label,
        prompt=prompt,
        raw_output=raw_output,
        visible_output=content,
        reasoning=reasoning,
        tool_calls=tool_calls,
        extra=extra,
        message_id=assistant.id,
        latency_ms=latency_ms,
        trace_id=trace_id,
    )
    await session.commit()
    return assistant


async def _run_recorded_skill(
    session: AsyncSession,
    notebook: Notebook,
    skill_id: str,
    args: dict[str, Any],
    call_id: str,
    tool_call_id: str,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    result = await run_skill(session, notebook, skill_id, args)
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps(result, default=str),
        }
    )
    return {
        "call_id": call_id,
        "skill_id": skill_id,
        "arguments": args,
        "result": result,
        "status": "done",
    }


def _provider_ready(notebook: Notebook) -> str:
    if notebook.provider == "ollama" and not _host_open(settings.ollama_api_base):
        return "Ollama ist nicht erreichbar. Starte Ollama oder wähle Hetzner in den Einstellungen."
    if notebook.provider == "hetzner" and not settings.hetzner_api_key:
        raise ValueError("HETZNER_API_KEY fehlt.")
    if notebook.provider == "openrouter" and not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY fehlt.")
    if notebook.provider == "eu" and not (settings.eu_llm_base_url and settings.eu_llm_api_key):
        raise ValueError("EU-Gateway ist nicht konfiguriert.")
    return ""


async def _emit_rule_skill(
    session: AsyncSession,
    notebook: Notebook,
    skill_id: str,
    args: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    call_id = new_call_id()
    yield step_event(
        "tool",
        skill_title(skill_id),
        tool_args_detail(args),
        status="running",
        step_id=call_id,
        call_id=call_id,
    )
    for event in tool_prelude_events(call_id, skill_id, args):
        yield event
    result = await run_skill(session, notebook, skill_id, args)
    record = {
        "call_id": call_id,
        "skill_id": skill_id,
        "arguments": args,
        "result": result,
        "status": "done",
    }
    yield {"event": "tool_result", "call_id": call_id, "skill_id": skill_id, "result": result}
    yield step_event(
        "tool",
        skill_title(skill_id),
        tool_result_detail(skill_id, args, result),
        step_id=call_id,
        call_id=call_id,
    )
    yield {"_record": record}


async def run_chat(
    session: AsyncSession,
    notebook: Notebook,
    user_text: str,
    tools_enabled: bool = True,
    use_history: bool = True,
) -> AsyncIterator[dict[str, Any]]:
    user_msg = Message(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        role="user",
        content=user_text,
    )
    session.add(user_msg)
    await session.commit()
    yield {"event": "user", "message_id": str(user_msg.id)}

    model_label = f"{notebook.provider}/{notebook.model_id}"
    started = time.perf_counter()
    reasoning: list[Any] = []
    analyze = step_event("analyze", "Frage prüfen", user_text[:80])
    record_step(reasoning, analyze)
    yield analyze

    target = delete_target(user_text)
    if tools_enabled and target:
        trace_id = start_trace("chat", notebook.tenant_id, {"notebook_id": str(notebook.id), "model": model_label})
        tool_calls: list[dict[str, Any]] = []
        async for item in _emit_rule_skill(session, notebook, "sources.delete_matching", {"query": target}):
            if "_record" in item:
                tool_calls.append(item["_record"])
                continue
            record_step(reasoning, item)
            yield item
        result = tool_calls[0]["result"]
        count = int(result["count"])
        if count:
            assistant_text = f"Ich habe {count} Quelle(n) entfernt, die zu „{target}“ passen."
        else:
            assistant_text = f"Keine Quelle passt zu „{target}“."
        write = step_event("write", "Antwort schreiben", step_id=WRITE_STEP_ID)
        record_step(reasoning, write)
        yield write
        yield {"event": "token", "text": assistant_text}
        assistant = await _save_assistant(
            session,
            notebook,
            content=assistant_text,
            citations=[],
            tool_calls=tool_calls,
            model_label=model_label,
            trace_id=trace_id,
            raw_output="",
            reasoning=reasoning,
            kind="chat_rule",
            prompt=user_text,
            extra={"rule": "delete_target"},
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        yield {
            "event": "done",
            "message_id": str(assistant.id),
            "citations": [],
            "model": assistant.model,
            "trace_id": trace_id,
        }
        return

    query = research_query(user_text)
    if tools_enabled and query:
        async for event in _research_turn(
            session,
            notebook,
            query,
            model_label,
            started,
            user_text,
            "research_intent",
            prior_reasoning=reasoning,
        ):
            yield event
        return

    source_ids = await selected_source_ids(session, notebook.id)
    chunks = await hybrid_search(session, notebook.id, notebook.tenant_id, user_text, source_ids)
    retrieve = step_event("retrieve", "Quellen durchsuchen", retrieve_step_detail(chunks))
    record_step(reasoning, retrieve)
    yield retrieve
    context_blocks = []
    citation_map = []
    for index, chunk in enumerate(chunks, start=1):
        context_blocks.append(f"[{index}] {chunk['source_title']}: {chunk['text']}")
        citation_map.append(
            {
                "n": index,
                "source_id": chunk["source_id"],
                "chunk_id": chunk["chunk_id"],
                "quote": chunk["text"][:280],
            }
        )
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM}]
    if context_blocks:
        messages.append({"role": "system", "content": "Quellenkontext:\n" + "\n\n".join(context_blocks)})
    if use_history:
        history_rows = (
            await session.execute(
                select(Message)
                .where(Message.notebook_id == notebook.id)
                .order_by(Message.created_at.desc())
                .limit(8)
            )
        ).scalars()
        history = list(reversed(list(history_rows)))
        for item in history[:-1]:
            content = item.content
            if item.role == "assistant":
                content, _leaks = extract_leaked_tools(content)
            messages.append({"role": item.role, "content": content})
    messages.append({"role": "user", "content": user_text})

    offline = _provider_ready(notebook)
    if offline:
        offline_text, offline_cites = finalize_answer(offline, citation_map)
        assistant = await _save_assistant(
            session,
            notebook,
            content=offline_text,
            citations=offline_cites,
            tool_calls=[],
            model_label=model_label,
            trace_id=None,
            raw_output=offline,
            reasoning=[],
            kind="chat_error",
            prompt=user_text,
            extra={"error": "ollama_offline"},
        )
        yield {"event": "token", "text": offline_text}
        yield {"event": "done", "message_id": str(assistant.id), "citations": offline_cites, "model": model_label}
        return

    trace_id = start_trace("chat", notebook.tenant_id, {"notebook_id": str(notebook.id), "model": model_label})
    yield {"event": "meta", "model": model_label, "trace_id": trace_id, "citations": citation_map}

    tools = _tools_for_prompt() if tools_enabled else None
    assistant_text = ""
    raw_output = ""
    tool_calls = []
    mutated_sources = False
    pending_job_id = ""
    pending_query = ""

    for _round in range(MAX_TOOL_ROUNDS + 1):
        executed: list[dict[str, Any]] = []
        async for event in _stream_pass(session, notebook, messages, tools, executed):
            if event.get("event") == "token":
                piece = str(event.get("text") or "")
                assistant_text += piece
                raw_output += piece
            record_step(reasoning, event)
            yield event
        ran_tool = False
        for record in executed:
            tool_calls.append(record)
            if record.get("skipped"):
                continue
            ran_tool = True
            if record["skill_id"].startswith("sources."):
                mutated_sources = True
            if record["skill_id"].startswith("research."):
                pending_job_id = str(record["result"]["job_id"])
                pending_query = str(record["result"].get("query") or record["arguments"].get("query") or user_text)
        if pending_job_id:
            break
        if not ran_tool:
            break
        tools = _tools_for_prompt() if tools_enabled else None

    assistant_text, _leaks = extract_leaked_tools(assistant_text)
    if chunks and tools_enabled and not pending_job_id:
        visible = assistant_text.strip()
        if not visible or visible == NO_ANSWER:
            retry_messages = [item for item in messages if item.get("role") == "system"]
            retry_messages.append({"role": "user", "content": user_text})
            retry_executed: list[dict[str, Any]] = []
            assistant_text = ""
            async for event in _stream_pass(session, notebook, retry_messages, None, retry_executed):
                if event.get("event") == "token":
                    piece = str(event.get("text") or "")
                    assistant_text += piece
                    raw_output += piece
                record_step(reasoning, event)
                yield event
            assistant_text, _leaks = extract_leaked_tools(assistant_text)

    if tools_enabled and not pending_job_id:
        visible = assistant_text.strip()
        thin = (not visible or visible == NO_ANSWER) and not is_smalltalk(user_text) and not chunks
        if thin:
            async for event in _research_turn(
                session,
                notebook,
                user_text,
                model_label,
                started,
                pack_prompt(messages),
                "thin_sources",
                prior_text=assistant_text,
                prior_tools=tool_calls,
                prior_reasoning=reasoning,
                trace_id=trace_id,
            ):
                yield event
            return

    if pending_job_id:
        wait_text = assistant_text.strip() or RESEARCH_WAIT
        if wait_text != RESEARCH_WAIT and RESEARCH_WAIT not in wait_text:
            wait_text = f"{wait_text}\n\n{RESEARCH_WAIT}" if wait_text else RESEARCH_WAIT
            yield {"event": "token", "text": "\n\n" + RESEARCH_WAIT}
        yield {
            "event": "research_pending",
            "job_id": pending_job_id,
            "query": pending_query or user_text,
            "mode": "fast",
        }
        assistant = await _save_assistant(
            session,
            notebook,
            content=wait_text if wait_text else RESEARCH_WAIT,
            citations=[],
            tool_calls=tool_calls,
            model_label=model_label,
            trace_id=trace_id,
            raw_output=raw_output,
            reasoning=reasoning,
            kind="chat",
            prompt=pack_prompt(messages),
            extra={"prompt_version": settings.prompt_version, "research_job_id": pending_job_id},
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        yield {
            "event": "done",
            "message_id": str(assistant.id),
            "citations": [],
            "model": model_label,
            "trace_id": trace_id,
            "research_pending": True,
            "job_id": pending_job_id,
        }
        return

    if not assistant_text:
        assistant_text = NO_SOURCES if not chunks else NO_ANSWER
        write = step_event("write", "Antwort schreiben", step_id=WRITE_STEP_ID)
        record_step(reasoning, write)
        yield write
        yield {"event": "token", "text": assistant_text}

    if mutated_sources:
        citation_map = []

    assistant_text, citation_map = finalize_answer(assistant_text, citation_map)
    faith = overlap_score(assistant_text, chunks) if chunks and not mutated_sources else 1.0
    if chunks and not mutated_sources and faith < 0.12:
        yield {"event": "warning", "text": "Antwort weicht stark von den zitierten Chunks ab."}

    assistant = await _save_assistant(
        session,
        notebook,
        content=assistant_text,
        citations=citation_map,
        tool_calls=tool_calls,
        model_label=model_label,
        trace_id=trace_id,
        raw_output=raw_output,
        reasoning=reasoning,
        kind="chat",
        prompt=pack_prompt(messages),
        extra={"prompt_version": settings.prompt_version, "retrieved": len(chunks)},
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    yield {
        "event": "done",
        "message_id": str(assistant.id),
        "citations": citation_map,
        "model": model_label,
        "trace_id": trace_id,
        "overlap": faith,
        "retrieved": chunks,
    }


async def _research_turn(
    session: AsyncSession,
    notebook: Notebook,
    query: str,
    model_label: str,
    started: float,
    prompt: str,
    rule: str,
    prior_text: str = "",
    prior_tools: list[dict[str, Any]] | None = None,
    prior_reasoning: list[Any] | None = None,
    trace_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    if not searx_reachable():
        text = SEARX_DOWN
        yield {"event": "token", "text": text}
        assistant = await _save_assistant(
            session,
            notebook,
            content=text,
            citations=[],
            tool_calls=prior_tools or [],
            model_label=model_label,
            trace_id=trace_id,
            raw_output=text,
            reasoning=prior_reasoning or [],
            kind="chat_error",
            prompt=prompt,
            extra={"error": "searx_offline", "rule": rule},
        )
        yield {"event": "done", "message_id": str(assistant.id), "citations": [], "model": model_label}
        return

    tool_calls = list(prior_tools or [])
    reasoning = list(prior_reasoning or [])
    research = step_event("research", "Websuche starten", query[:80])
    record_step(reasoning, research)
    yield research
    async for item in _emit_rule_skill(session, notebook, "research.fast", {"query": query}):
        if "_record" in item:
            tool_calls.append(item["_record"])
            continue
        record_step(reasoning, item)
        yield item
    job_id = str(tool_calls[-1]["result"]["job_id"])
    wait_text = prior_text.strip()
    write = step_event("write", "Antwort schreiben", step_id=WRITE_STEP_ID)
    record_step(reasoning, write)
    yield write
    if wait_text and wait_text not in {NO_ANSWER, NO_SOURCES}:
        assistant_text = f"{wait_text}\n\n{RESEARCH_WAIT}"
        yield {"event": "token", "text": "\n\n" + RESEARCH_WAIT}
    else:
        assistant_text = RESEARCH_WAIT
        yield {"event": "token", "text": RESEARCH_WAIT}
    yield {"event": "research_pending", "job_id": job_id, "query": query, "mode": "fast"}
    if trace_id is None:
        trace_id = start_trace("chat", notebook.tenant_id, {"notebook_id": str(notebook.id), "model": model_label})
    assistant = await _save_assistant(
        session,
        notebook,
        content=assistant_text,
        citations=[],
        tool_calls=tool_calls,
        model_label=model_label,
        trace_id=trace_id,
        raw_output=assistant_text,
        reasoning=reasoning,
        kind="chat",
        prompt=prompt,
        extra={"prompt_version": settings.prompt_version, "rule": rule, "research_job_id": job_id},
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    yield {
        "event": "done",
        "message_id": str(assistant.id),
        "citations": [],
        "model": model_label,
        "trace_id": trace_id,
        "research_pending": True,
        "job_id": job_id,
    }


async def _stream_pass(
    session: AsyncSession,
    notebook: Notebook,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    executed: list[dict[str, Any]],
) -> AsyncIterator[dict[str, Any]]:
    pending: dict[int, dict[str, Any]] = {}
    hold = ""
    leak_call_id = ""
    leak_args_sent = ""
    visible_pass = ""
    wrote = False

    async for chunk in router.stream_chat(notebook.provider, notebook.model_id, messages, tools):
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        think = thinking_text(delta)
        if think:
            yield {"event": "think", "text": think}
        content = getattr(delta, "content", None)
        if content:
            hold += content
            cleaned, leaked = extract_leaked_tools(hold)
            visible, hold = split_incomplete_tool(cleaned)
            if visible:
                if not wrote:
                    wrote = True
                    yield step_event("write", "Antwort schreiben", status="running", step_id=WRITE_STEP_ID)
                visible_pass += visible
                yield {"event": "token", "text": visible}
            name_hold = _TOOL_NAME_HOLD.search(hold)
            if name_hold and not leak_call_id:
                raw_name = name_hold.group(1) or name_hold.group(2)
                skill_id = resolve_tool_name(raw_name) or raw_name
                leak_call_id = new_call_id()
                yield {"event": "tool_start", "call_id": leak_call_id}
                yield {
                    "event": "tool_name",
                    "call_id": leak_call_id,
                    "skill_id": skill_id,
                    "name": skill_title(skill_id),
                }
                yield step_event(
                    "tool",
                    skill_title(skill_id),
                    status="running",
                    step_id=leak_call_id,
                    call_id=leak_call_id,
                )
            if leak_call_id and hold:
                args_match = re.search(r'"(?:arguments|parameters)"\s*:\s*(\{.*)', hold, re.DOTALL)
                if args_match:
                    args_so_far = args_match.group(1)
                    delta_args = args_so_far[len(leak_args_sent) :]
                    if delta_args:
                        leak_args_sent = args_so_far
                        yield {"event": "tool_args", "call_id": leak_call_id, "delta": delta_args}
            ran_leak = False
            for leak in leaked:
                call_id = leak_call_id or new_call_id()
                async for event in _emit_leaked_call(
                    session,
                    notebook,
                    messages,
                    leak,
                    executed,
                    call_id,
                    bool(leak_call_id),
                    leak_args_sent,
                    visible_pass,
                ):
                    yield event
                if leak.get("runnable"):
                    ran_leak = True
                leak_call_id = ""
                leak_args_sent = ""
            if ran_leak:
                if wrote:
                    yield step_event("write", "Antwort schreiben", step_id=WRITE_STEP_ID)
                return
        raw_tools = getattr(delta, "tool_calls", None) or []
        for call in raw_tools:
            index = call.index or 0
            slot = pending.setdefault(
                index,
                {
                    "id": "",
                    "call_id": "",
                    "name": "",
                    "arguments": "",
                    "started": False,
                    "named": False,
                },
            )
            if not slot["started"]:
                slot["call_id"] = call.id or new_call_id()
                slot["started"] = True
                yield {"event": "tool_start", "call_id": slot["call_id"]}
            if call.id and not slot["id"]:
                slot["id"] = call.id
            if call.function and call.function.name:
                slot["name"] = call.function.name
                if not slot["named"]:
                    skill_id = resolve_tool_name(slot["name"]) or slot["name"]
                    slot["named"] = True
                    yield {
                        "event": "tool_name",
                        "call_id": slot["call_id"],
                        "skill_id": skill_id,
                        "name": skill_title(skill_id) if skill_id in REGISTRY else skill_id,
                    }
                    yield step_event(
                        "tool",
                        skill_title(skill_id) if skill_id in REGISTRY else skill_id,
                        status="running",
                        step_id=slot["call_id"],
                        call_id=slot["call_id"],
                    )
            if call.function and call.function.arguments:
                slot["arguments"] += call.function.arguments
                yield {"event": "tool_args", "call_id": slot["call_id"], "delta": call.function.arguments}

    if hold.strip():
        cleaned, leaked = extract_leaked_tools(hold)
        visible, _incomplete = split_incomplete_tool(cleaned)
        if visible:
            if not wrote:
                wrote = True
                yield step_event("write", "Antwort schreiben", status="running", step_id=WRITE_STEP_ID)
            visible_pass += visible
            yield {"event": "token", "text": visible}
        for leak in leaked:
            call_id = leak_call_id or new_call_id()
            async for event in _emit_leaked_call(
                session,
                notebook,
                messages,
                leak,
                executed,
                call_id,
                bool(leak_call_id),
                leak_args_sent,
                visible_pass,
            ):
                yield event
            leak_call_id = ""
            leak_args_sent = ""

    to_run = [slot for slot in pending.values() if slot["started"] and slot["name"]]
    runnable_slots: list[tuple[dict[str, Any], str]] = []
    for slot in to_run:
        if any(record["call_id"] == slot["call_id"] for record in executed):
            continue
        skill_id = resolve_tool_name(slot["name"])
        args = parse_tool_args(slot["arguments"]) or {}
        if skill_id and can_run_chat_tool(skill_id):
            runnable_slots.append((slot, skill_id))
            continue
        display = skill_id or slot["name"]
        executed.append(skipped_tool_record(slot["call_id"], display, args))
        for event in skipped_tool_finish_events(slot["call_id"], display):
            yield event
    if not runnable_slots:
        if wrote:
            yield step_event("write", "Antwort schreiben", step_id=WRITE_STEP_ID)
        return
    messages.append(
        {
            "role": "assistant",
            "content": visible_pass or None,
            "tool_calls": [
                {
                    "id": slot["id"] or slot["call_id"],
                    "type": "function",
                    "function": {"name": slot["name"], "arguments": slot["arguments"] or "{}"},
                }
                for slot, _skill in runnable_slots
            ],
        }
    )
    for slot, skill_id in runnable_slots:
        args = parse_tool_args(slot["arguments"]) or {}
        record = await _run_recorded_skill(
            session,
            notebook,
            skill_id,
            args,
            slot["call_id"],
            slot["id"] or slot["call_id"],
            messages,
        )
        executed.append(record)
        yield {"event": "tool_result", "call_id": slot["call_id"], "skill_id": skill_id, "result": record["result"]}
        yield step_event(
            "tool",
            skill_title(skill_id),
            tool_result_detail(skill_id, args, record["result"]),
            step_id=slot["call_id"],
            call_id=slot["call_id"],
        )
    if wrote:
        yield step_event("write", "Antwort schreiben", step_id=WRITE_STEP_ID)


async def run_chat_resume(
    session: AsyncSession,
    notebook: Notebook,
    job_id: uuid.UUID,
) -> AsyncIterator[dict[str, Any]]:
    job = await session.get(ResearchJob, job_id)
    if job is None or job.notebook_id != notebook.id:
        raise ValueError("Recherche nicht gefunden")
    if job.status != "ready":
        raise ValueError("Recherche ist noch nicht fertig.")
    cites = list(
        (await session.execute(select(Citation).where(Citation.research_job_id == job.id).order_by(Citation.id))).scalars()
    )
    scratch, citation_map = research_scratch(job.report_md, cites)
    model_label = f"{notebook.provider}/{notebook.model_id}"
    offline = _provider_ready(notebook)
    if offline:
        offline_text, offline_cites = finalize_answer(offline, citation_map)
        yield {"event": "token", "text": offline_text}
        assistant = await _save_assistant(
            session,
            notebook,
            content=offline_text,
            citations=offline_cites,
            tool_calls=[],
            model_label=model_label,
            trace_id=None,
            raw_output=offline,
            reasoning=[],
            kind="chat_error",
            prompt=job.query,
            extra={"error": "ollama_offline", "job_id": str(job.id)},
        )
        yield {"event": "done", "message_id": str(assistant.id), "citations": offline_cites, "model": model_label}
        return

    messages = [
        {"role": "system", "content": RESUME_SYSTEM},
        {"role": "system", "content": scratch},
        {"role": "user", "content": job.query},
    ]
    trace_id = start_trace("chat_research", notebook.tenant_id, {"notebook_id": str(notebook.id), "job_id": str(job.id)})
    yield {"event": "meta", "model": model_label, "trace_id": trace_id, "citations": citation_map}
    reasoning: list[Any] = []
    research = step_event("research", "Recherche nutzen", job.query[:80])
    record_step(reasoning, research)
    yield research
    write = step_event("write", "Antwort schreiben", status="running", step_id=WRITE_STEP_ID)
    record_step(reasoning, write)
    yield write
    assistant_text = ""
    raw_output = ""
    started = time.perf_counter()
    async for chunk in router.stream_chat(notebook.provider, notebook.model_id, messages, None):
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        think = thinking_text(delta)
        if think:
            yield {"event": "think", "text": think}
        content = getattr(delta, "content", None)
        if content:
            assistant_text += content
            raw_output += content
            yield {"event": "token", "text": content}
    if not assistant_text:
        assistant_text = "Die Recherche enthält dazu keine klare Antwort."
        yield {"event": "token", "text": assistant_text}
    write = step_event("write", "Antwort schreiben", step_id=WRITE_STEP_ID)
    record_step(reasoning, write)
    yield write
    assistant_text, citation_map = finalize_answer(assistant_text, citation_map)
    assistant = await _save_assistant(
        session,
        notebook,
        content=assistant_text,
        citations=citation_map,
        tool_calls=[],
        model_label=model_label,
        trace_id=trace_id,
        raw_output=raw_output,
        reasoning=reasoning,
        kind="chat_research",
        prompt=pack_prompt(messages),
        extra={"job_id": str(job.id), "query": job.query, "prompt_version": settings.prompt_version},
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    yield {
        "event": "done",
        "message_id": str(assistant.id),
        "citations": citation_map,
        "model": model_label,
        "trace_id": trace_id,
        "job_id": str(job.id),
    }
