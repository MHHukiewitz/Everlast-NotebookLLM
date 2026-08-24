import json
import socket
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
from app.services.skills import REGISTRY, name_to_id, run_skill, tool_schema
from app.services.tracing import log_generation, start_trace

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
Antworte auf Deutsch.
Für Fakten nutze nur die ausgewählten Quellen im Kontext.
Wenn die Antwort nicht in den Quellen steht, sage das.
Erfinde keine Fakten.
Hänge Zitate in der Form [n] an Sätze an. n ist die Nummer im Quellenkontext.
Markiere generierten Text als KI-generiert, wenn du einen Bericht schreibst.
Lege Quellen oder Notizen nur über Werkzeuge an.
"""


def _tools_for_prompt() -> list[dict[str, Any]]:
    return [tool_schema(skill_id) for skill_id in REGISTRY]


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
        )
        session.add(assistant)
        await session.commit()
        yield {"event": "token", "text": assistant_text}
        yield {"event": "done", "message_id": str(assistant.id), "citations": citation_map, "model": model_label}
        return
    if notebook.provider == "openrouter" and not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY fehlt.")
    if notebook.provider == "eu" and not (settings.eu_llm_base_url and settings.eu_llm_api_key):
        raise ValueError("EU-Gateway ist nicht konfiguriert.")

    trace_id = start_trace("chat", settings.default_user_id, {"notebook_id": str(notebook.id), "model": model_label})
    yield {"event": "meta", "model": model_label, "trace_id": trace_id, "citations": citation_map}

    tools = _tools_for_prompt() if tools_enabled else None
    assistant_text = ""
    tool_calls: list[dict[str, Any]] = []
    pending: dict[int, dict[str, Any]] = {}

    async for chunk in router.stream_chat(notebook.provider, notebook.model_id, messages, tools):
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        if getattr(delta, "content", None):
            assistant_text += delta.content
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
            skill_id = name_to_id(slot["name"])
            args = json.loads(slot["arguments"] or "{}")
            yield {"event": "thought", "text": f"Fähigkeit: {skill_id}"}
            result = await run_skill(session, notebook, skill_id, args)
            tool_calls.append({"skill_id": skill_id, "args": args, "result": result})
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
                yield {"event": "token", "text": delta.content}

    if not assistant_text:
        if not chunks:
            assistant_text = "Ich bin ein KI-System. Füge Quellen hinzu oder stelle eine Frage."
        else:
            assistant_text = "Die Quellen enthalten dazu keine klare Antwort."
        yield {"event": "token", "text": assistant_text}

    faith = overlap_score(assistant_text, chunks) if chunks else 1.0
    if chunks and faith < 0.12:
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
    )
    session.add(assistant)
    await session.commit()
    log_generation(trace_id, model_label, user_text, assistant_text, {"prompt_version": settings.prompt_version})
    yield {
        "event": "done",
        "message_id": str(assistant.id),
        "citations": citation_map,
        "model": model_label,
        "trace_id": trace_id,
        "overlap": faith,
        "retrieved": chunks,
    }
