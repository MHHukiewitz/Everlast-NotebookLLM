import hashlib
import json
import uuid
from typing import Any, Callable, Awaitable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Artifact, Message, Notebook, SkillRun, Source
from app.schemas import SkillCard
from app.models import ResearchJob
from app.services.ingest import ingest_text, ingest_url
from app.services.research import run_research_job
from app.services.studio import create_flashcards, create_mindmap, create_quiz, create_report, create_table

Handler = Callable[[AsyncSession, Notebook, dict[str, Any]], Awaitable[dict[str, Any]]]


class Skill:
    def __init__(
        self,
        card: SkillCard,
        description_full: str,
        schema: dict[str, Any],
        handler: Handler | None,
    ) -> None:
        self.card = card
        self.description_full = description_full
        self.schema = schema
        self.handler = handler


async def _add_url(session: AsyncSession, notebook: Notebook, args: dict[str, Any]) -> dict[str, Any]:
    url = args["url"]
    source = Source(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        type="url",
        title=args.get("title") or url,
        status="pending",
        origin_uri=url,
    )
    session.add(source)
    await session.flush()
    await ingest_url(session, source, url)
    return {"source_id": str(source.id), "title": source.title}


async def _add_text(session: AsyncSession, notebook: Notebook, args: dict[str, Any]) -> dict[str, Any]:
    source = Source(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        type="text",
        title=args.get("title") or "Textquelle",
        status="pending",
    )
    session.add(source)
    await session.flush()
    await ingest_text(session, source, args["text"])
    return {"source_id": str(source.id), "title": source.title}


async def _list_sources(session: AsyncSession, notebook: Notebook, args: dict[str, Any]) -> dict[str, Any]:
    rows = (
        await session.execute(select(Source).where(Source.notebook_id == notebook.id))
    ).scalars()
    return {
        "sources": [
            {
                "id": str(row.id),
                "title": row.title,
                "selected": row.selected,
                "status": row.status,
                "origin_uri": row.origin_uri,
            }
            for row in rows
        ]
    }


async def _set_selected(session: AsyncSession, notebook: Notebook, args: dict[str, Any]) -> dict[str, Any]:
    source = await session.get(Source, uuid.UUID(args["source_id"]))
    if source is None or source.notebook_id != notebook.id:
        raise ValueError("Quelle nicht gefunden")
    source.selected = bool(args["selected"])
    await session.commit()
    return {"source_id": str(source.id), "selected": source.selected}


def _source_matches(source: Source, query: str) -> bool:
    needle = query.casefold().strip()
    if not needle:
        return False
    hay = " ".join(part for part in (source.title, source.origin_uri, source.type) if part)
    return needle in hay.casefold()


async def _delete_source(session: AsyncSession, notebook: Notebook, args: dict[str, Any]) -> dict[str, Any]:
    source = await session.get(Source, uuid.UUID(args["source_id"]))
    if source is None or source.notebook_id != notebook.id:
        raise ValueError("Quelle nicht gefunden")
    title = source.title
    await session.delete(source)
    await session.commit()
    return {"deleted": [{"id": args["source_id"], "title": title}], "count": 1}


async def _delete_matching(session: AsyncSession, notebook: Notebook, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    if not query:
        raise ValueError("Gib einen Suchbegriff für das Löschen an.")
    rows = list((await session.execute(select(Source).where(Source.notebook_id == notebook.id))).scalars())
    deleted: list[dict[str, str]] = []
    for source in rows:
        if not _source_matches(source, query):
            continue
        deleted.append({"id": str(source.id), "title": source.title})
        await session.delete(source)
    await session.commit()
    return {"deleted": deleted, "count": len(deleted), "query": query}


async def _notes_create(session: AsyncSession, notebook: Notebook, args: dict[str, Any]) -> dict[str, Any]:
    message_id = args.get("message_id")
    body = args.get("body") or ""
    if message_id and not body:
        message = await session.get(Message, uuid.UUID(message_id))
        if message:
            body = message.content
    artifact = Artifact(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        skill_id="notes.create",
        type="note",
        title=args.get("title") or "Neue Notiz",
        payload={"body": body},
        source_message_id=uuid.UUID(message_id) if message_id else None,
    )
    session.add(artifact)
    await session.commit()
    await session.refresh(artifact)
    return {"artifact_id": str(artifact.id), "title": artifact.title}


async def _research_fast(session: AsyncSession, notebook: Notebook, args: dict[str, Any]) -> dict[str, Any]:
    job = ResearchJob(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        query=args["query"],
        mode="fast",
        status="queued",
    )
    session.add(job)
    await session.commit()
    await run_research_job(session, job.id)
    return {"job_id": str(job.id), "mode": "fast"}


async def _research_deep(session: AsyncSession, notebook: Notebook, args: dict[str, Any]) -> dict[str, Any]:
    job = ResearchJob(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        query=args["query"],
        mode="deep",
        status="queued",
    )
    session.add(job)
    await session.commit()
    await run_research_job(session, job.id)
    return {"job_id": str(job.id), "mode": "deep"}


REGISTRY: dict[str, Skill] = {
    "sources.add_url": Skill(
        SkillCard(id="sources.add_url", title="URL hinzufügen", description="Webseite als Quelle laden", status="available", icon="link"),
        "Fügt eine Web-URL als Quelle hinzu.",
        {"type": "object", "properties": {"url": {"type": "string"}, "title": {"type": "string"}}, "required": ["url"]},
        _add_url,
    ),
    "sources.add_text": Skill(
        SkillCard(id="sources.add_text", title="Text hinzufügen", description="Text als Quelle speichern", status="available", icon="text"),
        "Speichert eingefügten Text als Quelle.",
        {"type": "object", "properties": {"title": {"type": "string"}, "text": {"type": "string"}}, "required": ["text"]},
        _add_text,
    ),
    "sources.list": Skill(
        SkillCard(id="sources.list", title="Quellen listen", description="Quellen des Notebooks", status="available", icon="list"),
        "Listet Quellen.",
        {"type": "object", "properties": {}},
        _list_sources,
    ),
    "sources.set_selected": Skill(
        SkillCard(id="sources.set_selected", title="Quelle wählen", description="Quelle ein- oder ausblenden", status="available", icon="check"),
        "Setzt selected.",
        {"type": "object", "properties": {"source_id": {"type": "string"}, "selected": {"type": "boolean"}}, "required": ["source_id", "selected"]},
        _set_selected,
    ),
    "sources.delete": Skill(
        SkillCard(id="sources.delete", title="Quelle löschen", description="Eine Quelle per ID entfernen", status="available", icon="delete"),
        "Löscht eine Quelle anhand der source_id.",
        {"type": "object", "properties": {"source_id": {"type": "string"}}, "required": ["source_id"]},
        _delete_source,
    ),
    "sources.delete_matching": Skill(
        SkillCard(id="sources.delete_matching", title="Quellen löschen", description="Quellen nach Titel oder URL entfernen", status="available", icon="delete"),
        "Löscht alle Quellen, deren Titel oder URL den Suchbegriff enthalten.",
        {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        _delete_matching,
    ),
    "research.fast": Skill(
        SkillCard(id="research.fast", title="Schnelle Recherche", description="Websuche nach Quellen", status="available", icon="search"),
        "Startet Fast Research.",
        {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        _research_fast,
    ),
    "research.deep": Skill(
        SkillCard(id="research.deep", title="Deep Research", description="Agent browsed und schreibt Bericht", status="available", icon="search"),
        "Startet Deep Research.",
        {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        _research_deep,
    ),
    "notes.create": Skill(
        SkillCard(id="notes.create", title="Notiz", description="Notiz im Studio anlegen", status="available", icon="note"),
        "Legt eine Notiz an.",
        {"type": "object", "properties": {"title": {"type": "string"}, "body": {"type": "string"}, "message_id": {"type": "string"}}},
        _notes_create,
    ),
    "studio.mindmap": Skill(
        SkillCard(id="studio.mindmap", title="Mindmap", description="Mindmap aus den gewählten Quellen", status="available", icon="mindmap"),
        "Erzeugt eine Mindmap aus den gewählten Quellen.",
        {"type": "object", "properties": {"topic": {"type": "string"}}},
        create_mindmap,
    ),
    "studio.report": Skill(
        SkillCard(id="studio.report", title="Berichte", description="Bericht aus den gewählten Quellen", status="available", icon="report"),
        "Schreibt einen zitierten Bericht aus den gewählten Quellen.",
        {"type": "object", "properties": {"topic": {"type": "string"}}},
        create_report,
    ),
    "studio.quiz": Skill(
        SkillCard(id="studio.quiz", title="Quiz", description="Quiz aus den gewählten Quellen", status="available", icon="quiz"),
        "Erzeugt ein Quiz aus den gewählten Quellen.",
        {"type": "object", "properties": {"topic": {"type": "string"}}},
        create_quiz,
    ),
    "studio.flashcards": Skill(
        SkillCard(id="studio.flashcards", title="Karteikarten", description="Karteikarten aus den gewählten Quellen", status="available", icon="cards"),
        "Erzeugt Karteikarten aus den gewählten Quellen.",
        {"type": "object", "properties": {"topic": {"type": "string"}}},
        create_flashcards,
    ),
    "studio.table": Skill(
        SkillCard(id="studio.table", title="Datentabelle", description="Tabelle aus den gewählten Quellen", status="available", icon="table"),
        "Erzeugt eine Datentabelle aus den gewählten Quellen.",
        {"type": "object", "properties": {"topic": {"type": "string"}}},
        create_table,
    ),
}

STUDIO_CATALOG = [
    SkillCard(id="notes.create", title="Notiz", description="Notiz schreiben oder aus dem Chat speichern", status="available", icon="note"),
    SkillCard(id="studio.audio", title="Audio-Zusammenfassung", description="Kommt nach dem MVP", status="locked", icon="audio"),
    SkillCard(id="studio.slides", title="Präsentation", description="Kommt nach dem MVP", status="locked", icon="slides"),
    SkillCard(id="studio.video", title="Videoübersicht", description="Kommt nach dem MVP", status="locked", icon="video"),
    SkillCard(id="studio.mindmap", title="Mindmap", description="Mindmap aus den gewählten Quellen", status="available", icon="mindmap"),
    SkillCard(id="studio.report", title="Berichte", description="Bericht aus den gewählten Quellen", status="available", icon="report"),
    SkillCard(id="studio.flashcards", title="Karteikarten", description="Karteikarten aus den gewählten Quellen", status="available", icon="cards"),
    SkillCard(id="studio.quiz", title="Quiz", description="Quiz aus den gewählten Quellen", status="available", icon="quiz"),
    SkillCard(id="studio.infographic", title="Infografik", description="Kommt nach dem MVP", status="locked", icon="info"),
    SkillCard(id="studio.table", title="Datentabelle", description="Tabelle aus den gewählten Quellen", status="available", icon="table"),
]


CHAT_TOOLS = [
    "sources.add_url",
    "sources.add_text",
    "sources.list",
    "sources.set_selected",
    "sources.delete",
    "sources.delete_matching",
    "notes.create",
]


def router_cards() -> list[dict[str, str]]:
    return [{"id": skill.card.id, "description": skill.card.description} for skill in REGISTRY.values()]


def tool_schema(skill_id: str) -> dict[str, Any]:
    skill = REGISTRY[skill_id]
    return {
        "type": "function",
        "function": {
            "name": skill.card.id.replace(".", "_"),
            "description": skill.description_full,
            "parameters": skill.schema,
        },
    }


async def run_skill(
    session: AsyncSession, notebook: Notebook, skill_id: str, args: dict[str, Any]
) -> dict[str, Any]:
    if skill_id not in REGISTRY:
        raise ValueError(f"Unbekannte Fähigkeit: {skill_id}")
    skill = REGISTRY[skill_id]
    if skill.handler is None:
        raise ValueError("Diese Studio-Funktion ist gesperrt.")
    result = await skill.handler(session, notebook, args)
    digest = hashlib.sha256(json.dumps(args, sort_keys=True, default=str).encode()).hexdigest()
    session.add(
        SkillRun(
            tenant_id=notebook.tenant_id,
            notebook_id=notebook.id,
            skill_id=skill_id,
            args_hash=digest,
            status="ok",
            artifact_id=uuid.UUID(result["artifact_id"]) if "artifact_id" in result else None,
        )
    )
    await session.commit()
    return result


def name_to_id(tool_name: str) -> str:
    return tool_name.replace("_", ".", 1) if tool_name.count("_") else tool_name


def resolve_tool_name(tool_name: str) -> str | None:
    raw = tool_name.strip()
    if raw in REGISTRY:
        return raw
    dotted = name_to_id(raw.replace(".", "_"))
    if dotted in REGISTRY:
        return dotted
    return None
