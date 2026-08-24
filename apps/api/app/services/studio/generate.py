import json
import socket
import uuid
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Artifact, Notebook, Source
from app.services.connectors import router
from app.services.retrieve import hybrid_search

DEFAULT_QUERY = "Kernaussagen der Quellen"


def _host_open(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    sock = socket.socket()
    sock.settimeout(1.0)
    code = sock.connect_ex((host, port))
    sock.close()
    return code == 0


def require_provider(notebook: Notebook) -> None:
    if notebook.provider == "ollama" and not _host_open(settings.ollama_api_base):
        raise ValueError("Ollama ist nicht erreichbar. Starte Ollama oder wähle OpenRouter in den Einstellungen.")
    if notebook.provider == "openrouter" and not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY fehlt.")
    if notebook.provider == "eu" and not (settings.eu_llm_base_url and settings.eu_llm_api_key):
        raise ValueError("EU-Gateway ist nicht konfiguriert.")


def strip_fences(raw: str) -> str:
    text = raw.strip()
    if not text.startswith("```"):
        return text
    body = text[3:]
    if body.startswith("json"):
        body = body[4:]
    elif body.startswith("mermaid"):
        body = body[7:]
    if body.endswith("```"):
        body = body[:-3]
    return body.strip()


_VALID_ESCAPES = set('"\\/bfnrt')


def sanitize_json_escapes(text: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char != "\\" or index + 1 >= len(text):
            out.append(char)
            index += 1
            continue
        nxt = text[index + 1]
        if nxt in _VALID_ESCAPES:
            out.append(char)
            out.append(nxt)
            index += 2
            continue
        hex_ok = all(item in "0123456789abcdefABCDEF" for item in text[index + 2 : index + 6])
        if nxt == "u" and index + 5 < len(text) and hex_ok:
            out.append(text[index : index + 6])
            index += 6
            continue
        out.append(nxt)
        index += 2
    return "".join(out)


def parse_json_object(raw: str) -> dict[str, Any]:
    text = strip_fences(raw)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Das Modell lieferte kein JSON.")
    return json.loads(sanitize_json_escapes(text[start : end + 1]))


async def selected_ready_ids(session: AsyncSession, notebook_id: uuid.UUID) -> list[uuid.UUID]:
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


async def retrieve_context(
    session: AsyncSession, notebook: Notebook, topic: str
) -> tuple[str, list[dict[str, Any]]]:
    source_ids = await selected_ready_ids(session, notebook.id)
    if not source_ids:
        raise ValueError("Wähle mindestens eine Quelle.")
    query = topic.strip() or DEFAULT_QUERY
    chunks = await hybrid_search(session, notebook.id, notebook.tenant_id, query, source_ids)
    if not chunks:
        raise ValueError("Die gewählten Quellen haben keine durchsuchbaren Abschnitte.")
    blocks: list[str] = []
    citations: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        blocks.append(f"[{index}] {chunk['source_title']}: {chunk['text']}")
        citations.append(
            {
                "n": index,
                "source_id": chunk["source_id"],
                "chunk_id": chunk["chunk_id"],
                "quote": chunk["text"][:280],
            }
        )
    return "\n\n".join(blocks), citations


async def generate_json(
    session: AsyncSession,
    notebook: Notebook,
    topic: str,
    system: str,
    user_template: str,
) -> dict[str, Any]:
    require_provider(notebook)
    context, citations = await retrieve_context(session, notebook, topic)
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": user_template.replace("{topic}", topic or DEFAULT_QUERY).replace("{context}", context),
        },
    ]
    completion = await router.complete(notebook.provider, notebook.model_id, messages)
    raw = completion.choices[0].message.content or ""
    if not raw.strip():
        raise ValueError("Das Modell lieferte keine Ausgabe.")
    payload = parse_json_object(raw)
    payload["citations"] = citations
    return payload


async def save_artifact(
    session: AsyncSession,
    notebook: Notebook,
    skill_id: str,
    artifact_type: str,
    title: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    artifact = Artifact(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        skill_id=skill_id,
        type=artifact_type,
        title=title,
        payload=payload,
    )
    session.add(artifact)
    await session.commit()
    await session.refresh(artifact)
    return {"artifact_id": str(artifact.id), "title": artifact.title}
