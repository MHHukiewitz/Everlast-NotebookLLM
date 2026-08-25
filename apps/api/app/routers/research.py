import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import owned_notebook
from app.models import Citation, Notebook, ResearchJob
from app.schemas import ResearchImportIn, ResearchJobOut, ResearchStartIn
from app.services.research import enqueue_research, import_research_isolated, run_research_job_isolated, searx_reachable
from app.services.search_query import prepare_web_query

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
    query = await prepare_web_query(query)
    job = await enqueue_research(session, notebook, query, body.mode)
    background_tasks.add_task(run_research_job_isolated, job.id)
    return ResearchJobOut.model_validate(job).model_copy(update={"candidates": []})


@api.get("/research/{job_id}", response_model=ResearchJobOut)
async def get_research(
    job_id: uuid.UUID,
    response: Response,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> ResearchJobOut:
    response.headers["Cache-Control"] = "no-store"
    job = await session.get(ResearchJob, job_id)
    if job is None or job.notebook_id != notebook.id:
        raise HTTPException(404, "Recherche nicht gefunden")
    cites = (
        await session.execute(select(Citation).where(Citation.research_job_id == job.id).order_by(Citation.id))
    ).scalars()
    return ResearchJobOut.model_validate(job).model_copy(update={"candidates": list(cites)})


@api.post("/research/{job_id}/import", response_model=ResearchJobOut)
async def import_job(
    job_id: uuid.UUID,
    body: ResearchImportIn,
    background_tasks: BackgroundTasks,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> ResearchJobOut:
    job = await session.get(ResearchJob, job_id)
    if job is None or job.notebook_id != notebook.id:
        raise HTTPException(404, "Recherche nicht gefunden")
    if job.status not in {"ready", "importing"}:
        raise HTTPException(400, "Recherche ist nicht bereit zum Import.")
    job.status = "importing"
    job.progress = "Import läuft"
    await session.commit()
    await session.refresh(job)
    background_tasks.add_task(import_research_isolated, job.id, list(body.citation_ids), body.import_report)
    cites = (
        await session.execute(select(Citation).where(Citation.research_job_id == job.id).order_by(Citation.id))
    ).scalars()
    return ResearchJobOut.model_validate(job).model_copy(update={"candidates": list(cites)})
