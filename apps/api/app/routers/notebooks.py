from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_tenant, current_user, owned_notebook
from app.models import AuditEvent, Notebook, User
from app.schemas import ModalitiesOut, NotebookOut, NotebookUpdate, ProviderStatus
from app.services.autoname import UNTITLED_TITLE
from app.services.connectors import router as model_router
from app.services.modalities import list_modalities
from app.services.tenancy import notebook_defaults

api = APIRouter(prefix="/api")


@api.get("/providers", response_model=list[ProviderStatus])
async def providers(_: User = Depends(current_user)) -> list[ProviderStatus]:
    return model_router.list_providers()


@api.get("/modalities", response_model=ModalitiesOut)
async def modalities(_: User = Depends(current_user)) -> ModalitiesOut:
    return list_modalities()


@api.post("/notebooks", response_model=NotebookOut)
async def create_notebook(
    session: AsyncSession = Depends(get_session), tenant: str = Depends(current_tenant)
) -> Notebook:
    notebook = Notebook(
        tenant_id=tenant,
        title=UNTITLED_TITLE,
        **notebook_defaults(),
    )
    session.add(notebook)
    await session.commit()
    await session.refresh(notebook)
    return notebook


@api.get("/notebooks", response_model=list[NotebookOut])
async def list_notebooks(
    session: AsyncSession = Depends(get_session), tenant: str = Depends(current_tenant)
) -> list[Notebook]:
    result = await session.execute(
        select(Notebook).where(Notebook.tenant_id == tenant).order_by(Notebook.created_at.asc())
    )
    return list(result.scalars())


@api.get("/notebooks/{notebook_id}", response_model=NotebookOut)
async def get_notebook(notebook: Notebook = Depends(owned_notebook)) -> Notebook:
    return notebook


@api.patch("/notebooks/{notebook_id}", response_model=NotebookOut)
async def update_notebook(
    body: NotebookUpdate,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> Notebook:
    cloud = {body.provider, body.tts_provider, body.image_provider}
    if "eu" in cloud and not body.eu_notice_accepted and not notebook.eu_notice_accepted:
        raise HTTPException(400, "EU-Hinweis muss bestätigt werden.")
    if "openrouter" in cloud and not body.openrouter_notice_accepted and not notebook.openrouter_notice_accepted:
        raise HTTPException(400, "OpenRouter-Hinweis muss bestätigt werden.")
    if body.title is not None:
        notebook.title = body.title
    if body.provider is not None:
        notebook.provider = body.provider
    if body.model_id is not None:
        notebook.model_id = body.model_id
    if body.tts_provider is not None:
        notebook.tts_provider = body.tts_provider
    if body.tts_model is not None:
        notebook.tts_model = body.tts_model
    if body.image_provider is not None:
        notebook.image_provider = body.image_provider
    if body.image_model is not None:
        notebook.image_model = body.image_model
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
