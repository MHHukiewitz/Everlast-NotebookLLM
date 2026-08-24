import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import owned_notebook
from app.models import Citation, Notebook, ResearchJob
from app.schemas import ResearchImportIn, ResearchJobOut, ResearchStartIn, SourceOut
from app.services.research import import_research, run_research_job_isolated, searx_reachable

api = APIRouter(prefix="/api/notebooks/{notebook_id}")


@api.post("/research", response_model=ResearchJobOut)
async def start_research(
    body: ResearchStartIn,
    background_tasks: BackgroundTasks,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> ResearchJobOut:
    query = body.query.strip()
    if not query:
        raise HTTPException(400, "Gib einen Suchbegriff ein.")
    if not searx_reachable():
        raise HTTPException(400, "SearXNG ist nicht erreichbar. Starte den SearXNG-Container.")
    job = ResearchJob(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        query=query,
        mode=body.mode,
        status="queued",
        progress="Suche läuft",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    background_tasks.add_task(run_research_job_isolated, job.id)
    return ResearchJobOut.model_validate(job).model_copy(update={"candidates": []})


@api.get("/research/{job_id}", response_model=ResearchJobOut)
async def get_research(
    job_id: uuid.UUID,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> ResearchJobOut:
    job = await session.get(ResearchJob, job_id)
    if job is None or job.notebook_id != notebook.id:
        raise HTTPException(404, "Recherche nicht gefunden")
    cites = (
        await session.execute(select(Citation).where(Citation.research_job_id == job.id))
    ).scalars()
    return ResearchJobOut.model_validate(job).model_copy(update={"candidates": list(cites)})


@api.post("/research/{job_id}/import", response_model=list[SourceOut])
async def import_job(
    job_id: uuid.UUID,
    body: ResearchImportIn,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> list:
    job = await session.get(ResearchJob, job_id)
    if job is None or job.notebook_id != notebook.id:
        raise HTTPException(404, "Recherche nicht gefunden")
    return await import_research(session, job, body.citation_ids, body.import_report)
