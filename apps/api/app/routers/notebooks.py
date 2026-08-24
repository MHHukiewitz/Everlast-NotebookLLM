import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import AuditEvent, Notebook
from app.schemas import NotebookOut, NotebookUpdate, ProviderStatus
from app.services.connectors import router as model_router

api = APIRouter(prefix="/api")


@api.get("/providers", response_model=list[ProviderStatus])
async def providers() -> list[ProviderStatus]:
    return model_router.list_providers()


@api.post("/notebooks", response_model=NotebookOut)
async def create_notebook(session: AsyncSession = Depends(get_session)) -> Notebook:
    notebook = Notebook(
        tenant_id=settings.default_tenant_id,
        title="Unbenanntes Notebook",
        provider=settings.default_provider,
        model_id=settings.default_model,
    )
    session.add(notebook)
    await session.commit()
    await session.refresh(notebook)
    return notebook


@api.get("/notebooks", response_model=list[NotebookOut])
async def list_notebooks(session: AsyncSession = Depends(get_session)) -> list[Notebook]:
    result = await session.execute(
        select(Notebook).where(Notebook.tenant_id == settings.default_tenant_id)
    )
    return list(result.scalars())


@api.get("/notebooks/{notebook_id}", response_model=NotebookOut)
async def get_notebook(notebook_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Notebook:
    notebook = await session.get(Notebook, notebook_id)
    if notebook is None or notebook.tenant_id != settings.default_tenant_id:
        raise HTTPException(404, "Notebook nicht gefunden")
    return notebook


@api.patch("/notebooks/{notebook_id}", response_model=NotebookOut)
async def update_notebook(
    notebook_id: uuid.UUID, body: NotebookUpdate, session: AsyncSession = Depends(get_session)
) -> Notebook:
    notebook = await session.get(Notebook, notebook_id)
    if notebook is None or notebook.tenant_id != settings.default_tenant_id:
        raise HTTPException(404, "Notebook nicht gefunden")
    if body.provider == "eu" and not body.eu_notice_accepted and not notebook.eu_notice_accepted:
        raise HTTPException(400, "EU-Hinweis muss bestätigt werden.")
    if body.provider == "openrouter" and not body.openrouter_notice_accepted and not notebook.openrouter_notice_accepted:
        raise HTTPException(400, "OpenRouter-Hinweis muss bestätigt werden.")
    if body.title is not None:
        notebook.title = body.title
    if body.provider is not None:
        notebook.provider = body.provider
    if body.model_id is not None:
        notebook.model_id = body.model_id
    if body.eu_notice_accepted is not None:
        notebook.eu_notice_accepted = body.eu_notice_accepted
    if body.openrouter_notice_accepted is not None:
        notebook.openrouter_notice_accepted = body.openrouter_notice_accepted
    session.add(
        AuditEvent(
            tenant_id=notebook.tenant_id,
            notebook_id=notebook.id,
            action="notebook.update",
            detail={"provider": notebook.provider, "model": notebook.model_id},
        )
    )
    await session.commit()
    await session.refresh(notebook)
    return notebook
