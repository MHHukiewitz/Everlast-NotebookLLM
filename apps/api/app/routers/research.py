import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Citation, Notebook, ResearchJob
from app.schemas import CitationOut, ResearchImportIn, ResearchJobOut, ResearchStartIn, SourceOut
from app.services.research import import_research, run_research_job

api = APIRouter(prefix="/api/notebooks/{notebook_id}")


@api.post("/research", response_model=ResearchJobOut)
async def start_research(
    notebook_id: uuid.UUID, body: ResearchStartIn, session: AsyncSession = Depends(get_session)
) -> ResearchJobOut:
    notebook = await session.get(Notebook, notebook_id)
    if notebook is None or notebook.tenant_id != settings.default_tenant_id:
        raise HTTPException(404, "Notebook nicht gefunden")
    job = ResearchJob(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        query=body.query,
        mode=body.mode,
        status="queued",
    )
    session.add(job)
    await session.commit()
    await run_research_job(session, job.id)
    await session.refresh(job)
    cites = (
        await session.execute(select(Citation).where(Citation.research_job_id == job.id))
    ).scalars()
    return ResearchJobOut.model_validate(job).model_copy(update={"candidates": list(cites)})


@api.get("/research/{job_id}", response_model=ResearchJobOut)
async def get_research(
    notebook_id: uuid.UUID, job_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ResearchJobOut:
    job = await session.get(ResearchJob, job_id)
    if job is None or job.notebook_id != notebook_id:
        raise HTTPException(404, "Recherche nicht gefunden")
    cites = (
        await session.execute(select(Citation).where(Citation.research_job_id == job.id))
    ).scalars()
    return ResearchJobOut.model_validate(job).model_copy(update={"candidates": list(cites)})


@api.post("/research/{job_id}/import", response_model=list[SourceOut])
async def import_job(
    notebook_id: uuid.UUID,
    job_id: uuid.UUID,
    body: ResearchImportIn,
    session: AsyncSession = Depends(get_session),
) -> list:
    job = await session.get(ResearchJob, job_id)
    if job is None or job.notebook_id != notebook_id:
        raise HTTPException(404, "Recherche nicht gefunden")
    return await import_research(session, job, body.citation_ids, body.import_report)
