import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.deps import owned_notebook
from app.models import AuditEvent, Citation, Notebook, Source
from app.schemas import AddTextIn, AddUrlIn, SelectSourceIn, SourceDetail, SourceOut
from app.services.autoname import maybe_autoname
from app.services.ingest import (
    extract_upload_text,
    finalize_source,
    ingest_text,
    ingest_url,
    is_image_filename,
    refresh_model_summary,
    store_file,
)
from app.services.pdf import markdown_to_pdf

api = APIRouter(prefix="/api/notebooks/{notebook_id}")


@api.get("/sources", response_model=list[SourceOut])
async def list_sources(
    notebook: Notebook = Depends(owned_notebook), session: AsyncSession = Depends(get_session)
) -> list[Source]:
    result = await session.execute(
        select(Source).where(Source.notebook_id == notebook.id).order_by(Source.created_at.desc())
    )
    return list(result.scalars())


@api.get("/sources/{source_id}", response_model=SourceDetail)
async def get_source(
    source_id: uuid.UUID,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> SourceDetail:
    source = await session.get(Source, source_id)
    if source is None or source.notebook_id != notebook.id:
        raise HTTPException(404, "Quelle nicht gefunden")
    cites = (
        await session.execute(select(Citation).where(Citation.source_id == source.id))
    ).scalars()
    return SourceDetail.model_validate(source).model_copy(update={"citations": list(cites)})


@api.post("/sources/url", response_model=SourceOut)
async def add_url(
    body: AddUrlIn,
    background_tasks: BackgroundTasks,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> Source:
    source = Source(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        type="url",
        title=body.title or body.url,
        status="pending",
        origin_uri=body.url,
    )
    session.add(source)
    await session.flush()
    await ingest_url(session, source, body.url, use_model_summary=False)
    maybe_autoname(notebook, source.title or body.url)
    session.add(AuditEvent(tenant_id=notebook.tenant_id, notebook_id=notebook.id, action="source.add_url", detail={"url": body.url}))
    await session.commit()
    background_tasks.add_task(refresh_model_summary, source.id)
    return source


@api.post("/sources/text", response_model=SourceOut)
async def add_text(
    body: AddTextIn,
    background_tasks: BackgroundTasks,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> Source:
    source = Source(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        type="text",
        title=body.title,
        status="pending",
    )
    session.add(source)
    await session.flush()
    await ingest_text(session, source, body.text, use_model_summary=False)
    if maybe_autoname(notebook, source.title or body.text):
        await session.commit()
    background_tasks.add_task(refresh_model_summary, source.id)
    return source


@api.post("/sources/file", response_model=SourceOut)
async def add_file(
    background_tasks: BackgroundTasks,
    notebook: Notebook = Depends(owned_notebook),
    upload: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> Source:
    data = await upload.read()
    filename = upload.filename or "upload.bin"
    if is_image_filename(filename) and not settings.hetzner_api_key:
        raise HTTPException(400, "Bilder brauchen Hetzner Inference. Setze HETZNER_API_KEY oder wähle Hetzner.")
    path = store_file(notebook.id, filename, data)
    text = await extract_upload_text(notebook, filename, data)
    source = Source(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        type="file",
        title=filename,
        status="pending",
        origin_uri=filename,
        file_path=path,
    )
    session.add(source)
    await session.flush()
    await finalize_source(session, source, text, use_model_summary=False)
    if maybe_autoname(notebook, source.title or filename):
        await session.commit()
    background_tasks.add_task(refresh_model_summary, source.id)
    return source


@api.patch("/sources/{source_id}", response_model=SourceOut)
async def select_source(
    source_id: uuid.UUID,
    body: SelectSourceIn,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> Source:
    source = await session.get(Source, source_id)
    if source is None or source.notebook_id != notebook.id:
        raise HTTPException(404, "Quelle nicht gefunden")
    source.selected = body.selected
    await session.commit()
    await session.refresh(source)
    return source


@api.delete("/sources/{source_id}")
async def delete_source(
    source_id: uuid.UUID,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    source = await session.get(Source, source_id)
    if source is None or source.notebook_id != notebook.id:
        raise HTTPException(404, "Quelle nicht gefunden")
    await session.delete(source)
    await session.commit()
    return {"status": "deleted"}


@api.get("/sources/{source_id}/pdf")
async def source_pdf(
    source_id: uuid.UUID,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> Response:
    source = await session.get(Source, source_id)
    if source is None or source.notebook_id != notebook.id:
        raise HTTPException(404, "Quelle nicht gefunden")
    pdf = markdown_to_pdf(source.title, source.summary_md or source.content_md)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{source.title[:40]}.pdf"',
            "X-AI-Generated": "true",
        },
    )
