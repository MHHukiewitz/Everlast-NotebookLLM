import json
import re
import socket
import uuid
from contextvars import ContextVar
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Artifact, Notebook, Source
from app.services.connectors import router
from app.services.retrieve import hybrid_search
from app.services.tracing import pack_prompt, record_generation, start_trace

DEFAULT_QUERY = "Kernaussagen der Quellen"
RENDER_RETRIES = 3
GIVE_UP = "Die Ausgabe konnte nach drei Versuchen nicht erzeugt werden."
CheckFn = Callable[[dict[str, Any]], tuple[bool, str]]
STUDIO_USER = """Anweisung: {prompt}

Quellenkontext:
{context}
"""
EVAL_MODE: ContextVar[bool] = ContextVar("eval_mode", default=False)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")

INVALID_STUDIO = {
    "title": "Keine gültige Studio-Ausgabe",
    "mermaid": "mindmap\n  root((Keine Ausgabe))",
    "mermaid_lines": ["mindmap", "  root((Keine Ausgabe))"],
    "body_md": "Keine gültige Studio-Ausgabe.",
    "questions": [
        {
            "question": "Keine gültige Studio-Ausgabe",
            "choices": ["–", "–", "–", "–"],
            "answer_index": 0,
            "explanation": "",
        }
    ],
    "cards": [{"front": "Keine Ausgabe", "back": "Keine Ausgabe", "cite": ""}],
    "columns": ["Feld", "Wert"],
    "rows": [["Status", "Keine gültige Studio-Ausgabe"]],
    "turns": [{"text": "Keine gültige Studio-Ausgabe"}],
    "scenes": [
        {
            "heading": "Keine Ausgabe",
            "bullets": ["Keine gültige Studio-Ausgabe"],
            "narration": "Keine gültige Studio-Ausgabe",
        }
    ],
}


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
        raise ValueError("Ollama ist nicht erreichbar. Starte Ollama oder wähle Hetzner in den Einstellungen.")
    if notebook.provider == "hetzner" and not settings.hetzner_api_key:
        raise ValueError("HETZNER_API_KEY fehlt.")
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


def load_json_object(raw: str) -> dict[str, Any] | None:
    text = strip_fences(raw)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    cleaned = _TRAILING_COMMA.sub(r"\1", sanitize_json_escapes(text[start : end + 1]))
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def parse_json_object(raw: str) -> dict[str, Any]:
    data = load_json_object(raw)
    if data is None:
        raise ValueError("Das Modell lieferte kein JSON.")
    return data


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


def topic_from_args(args: dict[str, Any], default: str = "") -> str:
    return str(args.get("prompt") or args.get("focus") or args.get("topic") or default).strip()


def source_ids_from_args(args: dict[str, Any]) -> list[uuid.UUID] | None:
    raw = args.get("source_ids")
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ValueError("source_ids muss eine Liste sein.")
    return [uuid.UUID(str(item)) for item in raw]


async def ready_source_ids(
    session: AsyncSession, notebook_id: uuid.UUID, wanted: list[uuid.UUID]
) -> list[uuid.UUID]:
    rows = (
        await session.execute(
            select(Source.id).where(
                Source.notebook_id == notebook_id,
                Source.status == "ready",
                Source.id.in_(wanted),
            )
        )
    ).scalars()
    found = set(rows)
    return [source_id for source_id in wanted if source_id in found]


async def retrieve_context(
    session: AsyncSession,
    notebook: Notebook,
    topic: str,
    source_ids: list[uuid.UUID] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    if source_ids is None:
        chosen = await selected_ready_ids(session, notebook.id)
    else:
        chosen = await ready_source_ids(session, notebook.id, source_ids)
    if not chosen:
        raise ValueError("Wähle mindestens eine Quelle.")
    query = topic.strip() or DEFAULT_QUERY
    chunks = await hybrid_search(session, notebook.id, notebook.tenant_id, query, chosen)
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
                "source_title": chunk["source_title"],
            }
        )
    return "\n\n".join(blocks), citations


async def generate_json(
    session: AsyncSession,
    notebook: Notebook,
    topic: str,
    system: str,
    user_template: str,
    source_ids: list[uuid.UUID] | None = None,
    check: CheckFn | None = None,
) -> dict[str, Any]:
    require_provider(notebook)
    context, citations = await retrieve_context(session, notebook, topic, source_ids)
    instruction = topic or DEFAULT_QUERY
    rounds = 1 if check is None else RENDER_RETRIES + 1
    reason = ""
    last: dict[str, Any] | None = None
    for _ in range(rounds):
        prompt = instruction
        if reason:
            prompt = f"{instruction}\n\nVorige Ausgabe war ungültig ({reason}). Erzeuge die Ausgabe neu."
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": user_template.replace("{topic}", prompt)
                .replace("{prompt}", prompt)
                .replace("{context}", context),
            },
        ]
        completion = await router.complete(notebook.provider, notebook.model_id, messages)
        raw = completion.choices[0].message.content or ""
        await record_generation(
            session,
            tenant_id=notebook.tenant_id,
            notebook_id=notebook.id,
            kind="studio",
            model=f"{notebook.provider}/{notebook.model_id}",
            prompt=pack_prompt(messages),
            raw_output=raw,
            visible_output=raw,
            extra={"topic": topic, "check_reason": reason},
            trace_id=start_trace("studio", notebook.tenant_id, {"notebook_id": str(notebook.id)}),
        )
        payload = load_json_object(raw) if raw.strip() else None
        if payload is None:
            if check is None:
                if EVAL_MODE.get():
                    fallback = dict(INVALID_STUDIO)
                    fallback["citations"] = citations
                    return fallback
                raise ValueError("Das Modell lieferte keine Ausgabe." if not raw.strip() else "Das Modell lieferte kein JSON.")
            reason = "keine gültige JSON-Ausgabe"
            last = dict(INVALID_STUDIO)
            last["citations"] = citations
            continue
        payload["citations"] = citations
        if check is None:
            return payload
        ok, reason = check(payload)
        if ok:
            return payload
        last = payload
    if EVAL_MODE.get() and last is not None:
        return last
    raise ValueError(GIVE_UP)


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
