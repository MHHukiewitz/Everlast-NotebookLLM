import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Artifact, AuditEvent, Message, Notebook, ResearchJob, SkillRun, Source
from app.services.pdf import AI_MARK
from app.services.tracing import delete_user_traces

api = APIRouter(prefix="/api")


@api.get("/compliance")
async def compliance_info() -> dict:
    return {
        "ai_disclosure": "Sie sprechen mit einem KI-System (Everlast Notebook).",
        "generated_mark": AI_MARK,
        "no_training": True,
        "default_provider": "ollama",
        "embeddings_leave_machine": False,
        "retention_days": settings.retention_days,
        "research_scratch_days": settings.research_scratch_days,
    }


@api.get("/notebooks/{notebook_id}/export")
async def export_notebook(notebook_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict:
    notebook = await session.get(Notebook, notebook_id)
    if notebook is None:
        raise HTTPException(404, "Notebook nicht gefunden")
    sources = list((await session.execute(select(Source).where(Source.notebook_id == notebook_id))).scalars())
    messages = list((await session.execute(select(Message).where(Message.notebook_id == notebook_id))).scalars())
    notes = list((await session.execute(select(Artifact).where(Artifact.notebook_id == notebook_id))).scalars())
    return {
        "ai_generated": True,
        "notice": AI_MARK,
        "notebook": {"id": str(notebook.id), "title": notebook.title, "model": f"{notebook.provider}/{notebook.model_id}"},
        "sources": [{"id": str(s.id), "title": s.title, "content_md": s.content_md} for s in sources],
        "messages": [{"role": m.role, "content": m.content, "model": m.model} for m in messages],
        "notes": [{"title": n.title, "payload": n.payload} for n in notes],
    }


@api.delete("/notebooks/{notebook_id}")
async def erase_notebook(notebook_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    notebook = await session.get(Notebook, notebook_id)
    if notebook is None:
        raise HTTPException(404, "Notebook nicht gefunden")
    sources = list((await session.execute(select(Source).where(Source.notebook_id == notebook_id))).scalars())
    for source in sources:
        if source.file_path:
            path = Path(source.file_path)
            if path.exists():
                path.unlink()
        await session.delete(source)
    for model in (Message, Artifact, ResearchJob, SkillRun, AuditEvent):
        rows = (await session.execute(select(model).where(model.notebook_id == notebook_id))).scalars()
        for row in rows:
            await session.delete(row)
    await session.delete(notebook)
    session.add(
        Notebook(
            tenant_id=settings.default_tenant_id,
            title="Unbenanntes Notebook",
            provider=settings.default_provider,
            model_id=settings.default_model,
        )
    )
    await session.commit()
    delete_user_traces(settings.default_user_id)
    return {"status": "erased"}


@api.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
