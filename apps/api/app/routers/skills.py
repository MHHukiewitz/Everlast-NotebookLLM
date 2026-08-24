import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_tenant, current_user, owned_notebook
from app.models import Artifact, Notebook, Source, User
from app.schemas import ArtifactOut, NoteIn, SkillCard, SkillRunIn, SourceOut
from app.services.autoname import maybe_autoname
from app.services.ingest import ingest_text, refresh_model_summary
from app.services.skills import STUDIO_CATALOG, run_skill
from app.services.studio.export import artifact_markdown, export_artifact
from app.services.studio.media import media_file, synthesize_media_isolated

api = APIRouter(prefix="/api")


@api.get("/skills", response_model=list[SkillCard])
async def list_skills(_: User = Depends(current_user)) -> list[SkillCard]:
    return STUDIO_CATALOG


@api.get("/notebooks/{notebook_id}/artifacts", response_model=list[ArtifactOut])
async def list_artifacts(
    notebook: Notebook = Depends(owned_notebook), session: AsyncSession = Depends(get_session)
) -> list[Artifact]:
    result = await session.execute(
        select(Artifact).where(Artifact.notebook_id == notebook.id).order_by(Artifact.created_at.desc())
    )
    return list(result.scalars())


@api.post("/notebooks/{notebook_id}/notes", response_model=ArtifactOut)
async def create_note(
    body: NoteIn,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> Artifact:
    result = await run_skill(
        session,
        notebook,
        "notes.create",
        {"title": body.title, "body": body.body, "message_id": str(body.message_id) if body.message_id else None},
    )
    artifact = await session.get(Artifact, uuid.UUID(result["artifact_id"]))
    if artifact is None:
        raise HTTPException(500, "Notiz nicht gespeichert")
    return artifact


@api.get("/notebooks/{notebook_id}/artifacts/{artifact_id}/export")
async def export_artifact_file(
    artifact_id: uuid.UUID,
    notebook: Notebook = Depends(owned_notebook),
    fmt: str = Query("pdf", alias="format"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    artifact = await session.get(Artifact, artifact_id)
    if artifact is None or artifact.notebook_id != notebook.id:
        raise HTTPException(404, "Artefakt nicht gefunden")
    data, media_type, filename = export_artifact(
        artifact.type, artifact.title, artifact.payload or {}, fmt
    )
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api.get("/notebooks/{notebook_id}/artifacts/{artifact_id}/media")
async def artifact_media(
    artifact_id: uuid.UUID,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    artifact = await session.get(Artifact, artifact_id)
    if artifact is None or artifact.notebook_id != notebook.id:
        raise HTTPException(404, "Artefakt nicht gefunden")
    ext = "mp3" if artifact.type == "audio" else "mp4"
    if artifact.type not in {"audio", "video"}:
        raise HTTPException(404, "Keine Mediendatei")
    path = media_file(notebook.id, artifact.id, ext)
    if not path.exists():
        raise HTTPException(404, "Die Mediendatei ist noch nicht fertig.")
    media_type = "audio/mpeg" if ext == "mp3" else "video/mp4"
    return FileResponse(path, media_type=media_type, filename=path.name)


@api.post("/notebooks/{notebook_id}/artifacts/{artifact_id}/source", response_model=SourceOut)
async def artifact_as_source(
    artifact_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> Source:
    artifact = await session.get(Artifact, artifact_id)
    if artifact is None or artifact.notebook_id != notebook.id:
        raise HTTPException(404, "Artefakt nicht gefunden")
    text = artifact_markdown(artifact.type, artifact.title, artifact.payload or {})
    if not text.strip():
        raise ValueError("Das Artefakt ist leer.")
    source = Source(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        type="text",
        title=f"Studio: {artifact.title}",
        status="pending",
        origin_uri=f"artifact://{artifact.id}",
    )
    session.add(source)
    await session.flush()
    await ingest_text(session, source, text, use_model_summary=False)
    if maybe_autoname(notebook, source.title):
        await session.commit()
    background_tasks.add_task(refresh_model_summary, source.id)
    return source


@api.post("/skills/{skill_id}/run")
async def run(
    skill_id: str,
    notebook_id: uuid.UUID,
    body: SkillRunIn,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    tenant: str = Depends(current_tenant),
) -> dict:
    notebook = await session.get(Notebook, notebook_id)
    if notebook is None or notebook.tenant_id != tenant:
        raise HTTPException(404, "Notebook nicht gefunden")
    locked = {card.id for card in STUDIO_CATALOG if card.status == "locked"}
    if skill_id in locked:
        raise HTTPException(400, "Diese Studio-Funktion ist gesperrt.")
    result = await run_skill(session, notebook, skill_id, body.args)
    if skill_id in {"studio.audio", "studio.video"} and result.get("artifact_id"):
        artifact = await session.get(Artifact, uuid.UUID(result["artifact_id"]))
        if artifact and (artifact.payload or {}).get("status") == "pending":
            background_tasks.add_task(synthesize_media_isolated, artifact.id)
    return result
