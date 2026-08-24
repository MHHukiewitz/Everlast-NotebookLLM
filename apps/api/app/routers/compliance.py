from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.deps import owned_notebook
from app.models import Artifact, GenerationLog, Message, Notebook, Source
from app.services.pdf import AI_MARK
from app.services.tenancy import create_empty_notebook, erase_notebook
from app.services.tracing import delete_user_traces

api = APIRouter(prefix="/api")


@api.get("/compliance")
async def compliance_info() -> dict:
    return {
        "ai_disclosure": "Sie sprechen mit einem KI-System (Everlast Notebook).",
        "generated_mark": AI_MARK,
        "no_training": True,
        "default_provider": settings.default_provider,
        "embeddings_leave_machine": False,
        "retention_days": settings.retention_days,
        "research_scratch_days": settings.research_scratch_days,
    }


@api.get("/notebooks/{notebook_id}/export")
async def export_notebook(
    notebook: Notebook = Depends(owned_notebook), session: AsyncSession = Depends(get_session)
) -> dict:
    sources = list((await session.execute(select(Source).where(Source.notebook_id == notebook.id))).scalars())
    messages = list((await session.execute(select(Message).where(Message.notebook_id == notebook.id))).scalars())
    notes = list((await session.execute(select(Artifact).where(Artifact.notebook_id == notebook.id))).scalars())
    generations = list(
        (await session.execute(select(GenerationLog).where(GenerationLog.notebook_id == notebook.id))).scalars()
    )
    return {
        "ai_generated": True,
        "notice": AI_MARK,
        "notebook": {"id": str(notebook.id), "title": notebook.title, "model": f"{notebook.provider}/{notebook.model_id}"},
        "sources": [{"id": str(s.id), "title": s.title, "content_md": s.content_md} for s in sources],
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "model": m.model,
                "raw_output": m.raw_output,
                "reasoning": m.reasoning,
                "tool_calls": m.tool_calls,
            }
            for m in messages
        ],
        "notes": [{"title": n.title, "payload": n.payload} for n in notes],
        "generations": [
            {
                "id": str(row.id),
                "kind": row.kind,
                "model": row.model,
                "prompt": row.prompt,
                "raw_output": row.raw_output,
                "visible_output": row.visible_output,
                "reasoning": row.reasoning,
                "tool_calls": row.tool_calls,
                "extra": row.extra,
                "latency_ms": row.latency_ms,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in generations
        ],
    }


@api.delete("/notebooks/{notebook_id}")
async def erase_notebook_route(
    notebook: Notebook = Depends(owned_notebook), session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    tenant_id = notebook.tenant_id
    await erase_notebook(session, notebook)
    await create_empty_notebook(session, tenant_id)
    await session.commit()
    delete_user_traces(tenant_id)
    return {"status": "erased"}


@api.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
