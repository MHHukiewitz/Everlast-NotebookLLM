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
from app.models import Message, Notebook, Source
from app.services.connectors import router
from app.services.retrieve import hybrid_search, overlap_score
from app.services.skills import CHAT_TOOLS, resolve_tool_name, run_skill, tool_schema
from app.services.tracing import pack_prompt, record_generation, start_trace

def _host_open(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    sock = socket.socket()
    sock.settimeout(1.0)
    code = sock.connect_ex((host, port))
    sock.close()
    return code == 0


SYSTEM = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Antworte auf Deutsch in normaler Sprache.
Schreibe keine JSON-Werkzeugaufrufe in die Antwort.
Für Fakten nutze nur die ausgewählten Quellen im Kontext.
Wenn die Antwort nicht in den Quellen steht, sage das.
Erfinde keine Fakten.
Hänge Zitate in der Form [n] an Sätze an. n ist die Nummer im Quellenkontext.
Markiere generierten Text als KI-generiert, wenn du einen Bericht schreibst.
Lege, wähle oder lösche Quellen nur über Werkzeuge.
Zum Löschen nutze sources_delete_matching mit einem kurzen Suchbegriff aus Titel oder URL.
"""

_LEAKED_TOOL = re.compile(
    r"\{[^{}]*\"name\"\s*:\s*\"([^\"]+)\"[^{}]*\"arguments\"\s*:\s*(\{(?:[^{}]*)\})[^{}]*\}",
    re.DOTALL,
)
_DELETE_TARGET = re.compile(
    r"(?:entferne|lösche|löschen|remove|delete)\s+(?:die\s+|das\s+|den\s+|the\s+)?(.+)",
    re.I,
)


def _tools_for_prompt() -> list[dict[str, Any]]:
    return [tool_schema(skill_id) for skill_id in CHAT_TOOLS]


def delete_target(text: str) -> str:
    match = _DELETE_TARGET.search(text.strip())
    if not match:
        return ""
    target = match.group(1)
    target = re.sub(r"\s+quellen?\s*$", "", target, flags=re.I)
    target = re.sub(r"\s+sources?\s*$", "", target, flags=re.I)
    return target.strip(" .")


def extract_leaked_tools(text: str) -> tuple[str, list[dict[str, str]]]:
    calls: list[dict[str, str]] = []

    def take(match: re.Match[str]) -> str:
        skill_id = resolve_tool_name(match.group(1))
        if skill_id is None:
            return ""
        calls.append({"name": skill_id, "arguments": match.group(2)})
        return ""

    cleaned = _LEAKED_TOOL.sub(take, text)
    cleaned = re.sub(r"```(?:json)?\s*```", "", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip(), calls


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

    target = delete_target(user_text)
    if tools_enabled and target:
        model_label = f"{notebook.provider}/{notebook.model_id}"
        trace_id = start_trace("chat", notebook.tenant_id, {"notebook_id": str(notebook.id), "model": model_label})
        thought = "Fähigkeit: sources.delete_matching"
        yield {"event": "thought", "text": thought}
        result = await run_skill(session, notebook, "sources.delete_matching", {"query": target})
        count = int(result["count"])
        if count:
            assistant_text = f"Ich habe {count} Quelle(n) entfernt, die zu „{target}“ passen."
        else:
            assistant_text = f"Keine Quelle passt zu „{target}“."
        tool_calls = [{"skill_id": "sources.delete_matching", "args": {"query": target}, "result": result}]
        assistant = Message(
            tenant_id=notebook.tenant_id,
            notebook_id=notebook.id,
            role="assistant",
            content=assistant_text,
            citations=[],
            tool_calls=tool_calls,
            model=model_label,
            trace_id=trace_id,
            raw_output="",
            reasoning=[thought],
        )
        session.add(assistant)
        await session.flush()
        await record_generation(
            session,
            tenant_id=notebook.tenant_id,
            notebook_id=notebook.id,
            kind="chat_rule",
            model=model_label,
            prompt=user_text,
            raw_output="",
            visible_output=assistant_text,
            reasoning=[thought],
            tool_calls=tool_calls,
            extra={"rule": "delete_target"},
            message_id=assistant.id,
            trace_id=trace_id,
        )
        await session.commit()
        yield {"event": "token", "text": assistant_text}
        yield {
            "event": "done",
            "message_id": str(assistant.id),
            "citations": [],
            "model": assistant.model,
            "trace_id": trace_id,
        }
        return

    source_ids = await selected_source_ids(session, notebook.id)
    chunks = await hybrid_search(session, notebook.id, notebook.tenant_id, user_text, source_ids)
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
            messages.append({"role": item.role, "content": item.content})
    messages.append({"role": "user", "content": user_text})

    model_label = f"{notebook.provider}/{notebook.model_id}"
    if notebook.provider == "ollama" and not _host_open(settings.ollama_api_base):
        assistant_text = "Ollama ist nicht erreichbar. Starte Ollama oder wähle OpenRouter in den Einstellungen."
        assistant = Message(
            tenant_id=notebook.tenant_id,
            notebook_id=notebook.id,
            role="assistant",
            content=assistant_text,
            citations=citation_map,
            model=model_label,
            raw_output=assistant_text,
            reasoning=[],
        )
        session.add(assistant)
        await session.flush()
        await record_generation(
            session,
            tenant_id=notebook.tenant_id,
            notebook_id=notebook.id,
            kind="chat_error",
            model=model_label,
            prompt=user_text,
            raw_output=assistant_text,
            visible_output=assistant_text,
            extra={"error": "ollama_offline"},
            message_id=assistant.id,
        )
        await session.commit()
        yield {"event": "token", "text": assistant_text}
        yield {"event": "done", "message_id": str(assistant.id), "citations": citation_map, "model": model_label}
        return
    if notebook.provider == "openrouter" and not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY fehlt.")
    if notebook.provider == "eu" and not (settings.eu_llm_base_url and settings.eu_llm_api_key):
        raise ValueError("EU-Gateway ist nicht konfiguriert.")

    trace_id = start_trace("chat", notebook.tenant_id, {"notebook_id": str(notebook.id), "model": model_label})
    yield {"event": "meta", "model": model_label, "trace_id": trace_id, "citations": citation_map}

    tools = _tools_for_prompt() if tools_enabled else None
    assistant_text = ""
    raw_output = ""
    reasoning: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    pending: dict[int, dict[str, Any]] = {}
    started = time.perf_counter()

    async for chunk in router.stream_chat(notebook.provider, notebook.model_id, messages, tools):
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        if getattr(delta, "content", None):
            assistant_text += delta.content
            raw_output += delta.content
            yield {"event": "token", "text": delta.content}
        raw_tools = getattr(delta, "tool_calls", None) or []
        for call in raw_tools:
            index = call.index or 0
            slot = pending.setdefault(index, {"id": "", "name": "", "arguments": ""})
            if call.id:
                slot["id"] = call.id
            if call.function and call.function.name:
                slot["name"] = call.function.name
            if call.function and call.function.arguments:
                slot["arguments"] += call.function.arguments
    if pending:
        raw_output += "\n" + json.dumps(
            [{"name": slot["name"], "arguments": slot["arguments"]} for slot in pending.values()],
            ensure_ascii=False,
        )

    if not pending:
        cleaned, leaked = extract_leaked_tools(assistant_text)
        if leaked or cleaned != assistant_text.strip():
            assistant_text = cleaned
        for index, leak in enumerate(leaked):
            pending[index] = {"id": f"leak_{index}", "name": leak["name"], "arguments": leak["arguments"]}

    mutated_sources = False
    if pending:
        messages.append(
            {
                "role": "assistant",
                "content": assistant_text or None,
                "tool_calls": [
                    {
                        "id": slot["id"] or f"call_{index}",
                        "type": "function",
                        "function": {"name": slot["name"], "arguments": slot["arguments"] or "{}"},
                    }
                    for index, slot in pending.items()
                ],
            }
        )
        for slot in pending.values():
            skill_id = resolve_tool_name(slot["name"])
            if skill_id is None:
                continue
            args = json.loads(slot["arguments"] or "{}")
            thought = f"Fähigkeit: {skill_id}"
            reasoning.append(thought)
            yield {"event": "thought", "text": thought}
            result = await run_skill(session, notebook, skill_id, args)
            tool_calls.append({"skill_id": skill_id, "args": args, "result": result})
            if skill_id.startswith("sources."):
                mutated_sources = True
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": slot["id"] or slot["name"],
                    "content": json.dumps(result, default=str),
                }
            )
            yield {"event": "skill", "skill_id": skill_id, "result": result}
        async for chunk in router.stream_chat(notebook.provider, notebook.model_id, messages, None):
            delta = chunk.choices[0].delta
            if delta and getattr(delta, "content", None):
                assistant_text += delta.content
                raw_output += delta.content
                yield {"event": "token", "text": delta.content}

    target = delete_target(user_text)
    if target and not any(item["skill_id"].startswith("sources.delete") for item in tool_calls):
        thought = "Fähigkeit: sources.delete_matching"
        reasoning.append(thought)
        yield {"event": "thought", "text": thought}
        result = await run_skill(session, notebook, "sources.delete_matching", {"query": target})
        tool_calls.append({"skill_id": "sources.delete_matching", "args": {"query": target}, "result": result})
        mutated_sources = True
        count = int(result["count"])
        if count:
            assistant_text = f"Ich habe {count} Quelle(n) entfernt, die zu „{target}“ passen."
        else:
            assistant_text = f"Keine Quelle passt zu „{target}“."
        yield {"event": "token", "text": assistant_text}

    if not assistant_text:
        if not chunks:
            assistant_text = "Ich bin ein KI-System. Füge Quellen hinzu oder stelle eine Frage."
        else:
            assistant_text = "Die Quellen enthalten dazu keine klare Antwort."
        yield {"event": "token", "text": assistant_text}

    if mutated_sources:
        citation_map = []

    faith = overlap_score(assistant_text, chunks) if chunks and not mutated_sources else 1.0
    if chunks and not mutated_sources and faith < 0.12:
        yield {"event": "warning", "text": "Antwort weicht stark von den zitierten Chunks ab."}

    assistant = Message(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        role="assistant",
        content=assistant_text,
        citations=citation_map,
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
        kind="chat",
        model=model_label,
        prompt=pack_prompt(messages),
        raw_output=raw_output,
        visible_output=assistant_text,
        reasoning=reasoning,
        tool_calls=tool_calls,
        extra={"prompt_version": settings.prompt_version, "retrieved": len(chunks)},
        message_id=assistant.id,
        latency_ms=int((time.perf_counter() - started) * 1000),
        trace_id=trace_id,
    )
    await session.commit()
    yield {
        "event": "done",
        "message_id": str(assistant.id),
        "citations": citation_map,
        "model": model_label,
        "trace_id": trace_id,
        "overlap": faith,
        "retrieved": chunks,
    }
