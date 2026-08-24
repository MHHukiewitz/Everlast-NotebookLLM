import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import AuditEvent, Citation, Notebook, Source
from app.schemas import AddTextIn, AddUrlIn, SelectSourceIn, SourceDetail, SourceOut
from app.services.ingest import finalize_source, ingest_text, ingest_url, parse_upload, store_file
from app.services.pdf import markdown_to_pdf

api = APIRouter(prefix="/api/notebooks/{notebook_id}")


async def _notebook(session: AsyncSession, notebook_id: uuid.UUID) -> Notebook:
    notebook = await session.get(Notebook, notebook_id)
    if notebook is None or notebook.tenant_id != settings.default_tenant_id:
        raise HTTPException(404, "Notebook nicht gefunden")
    return notebook


@api.get("/sources", response_model=list[SourceOut])
async def list_sources(notebook_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> list[Source]:
    await _notebook(session, notebook_id)
    result = await session.execute(
        select(Source).where(Source.notebook_id == notebook_id).order_by(Source.created_at.desc())
    )
    return list(result.scalars())


@api.get("/sources/{source_id}", response_model=SourceDetail)
async def get_source(
    notebook_id: uuid.UUID, source_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> SourceDetail:
    source = await session.get(Source, source_id)
    if source is None or source.notebook_id != notebook_id:
        raise HTTPException(404, "Quelle nicht gefunden")
    cites = (
        await session.execute(select(Citation).where(Citation.source_id == source.id))
    ).scalars()
    return SourceDetail.model_validate(source).model_copy(update={"citations": list(cites)})


@api.post("/sources/url", response_model=SourceOut)
async def add_url(
    notebook_id: uuid.UUID, body: AddUrlIn, session: AsyncSession = Depends(get_session)
) -> Source:
    notebook = await _notebook(session, notebook_id)
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
    await ingest_url(session, source, body.url)
    session.add(AuditEvent(tenant_id=notebook.tenant_id, notebook_id=notebook.id, action="source.add_url", detail={"url": body.url}))
    await session.commit()
    return source


@api.post("/sources/text", response_model=SourceOut)
async def add_text(
    notebook_id: uuid.UUID, body: AddTextIn, session: AsyncSession = Depends(get_session)
) -> Source:
    notebook = await _notebook(session, notebook_id)
    source = Source(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        type="text",
        title=body.title,
        status="pending",
    )
    session.add(source)
    await session.flush()
    await ingest_text(session, source, body.text)
    return source


@api.post("/sources/file", response_model=SourceOut)
async def add_file(
    notebook_id: uuid.UUID,
    upload: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> Source:
    notebook = await _notebook(session, notebook_id)
    data = await upload.read()
    filename = upload.filename or "upload.bin"
    path = store_file(notebook.id, filename, data)
    text = parse_upload(filename, data)
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
    await finalize_source(session, source, text)
    return source


@api.patch("/sources/{source_id}", response_model=SourceOut)
async def select_source(
    notebook_id: uuid.UUID,
    source_id: uuid.UUID,
    body: SelectSourceIn,
    session: AsyncSession = Depends(get_session),
) -> Source:
    source = await session.get(Source, source_id)
    if source is None or source.notebook_id != notebook_id:
        raise HTTPException(404, "Quelle nicht gefunden")
    source.selected = body.selected
    await session.commit()
    await session.refresh(source)
    return source


@api.delete("/sources/{source_id}")
async def delete_source(
    notebook_id: uuid.UUID, source_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    source = await session.get(Source, source_id)
    if source is None or source.notebook_id != notebook_id:
        raise HTTPException(404, "Quelle nicht gefunden")
    await session.delete(source)
    await session.commit()
    return {"status": "deleted"}


@api.get("/sources/{source_id}/pdf")
async def source_pdf(
    notebook_id: uuid.UUID, source_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    source = await session.get(Source, source_id)
    if source is None or source.notebook_id != notebook_id:
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
