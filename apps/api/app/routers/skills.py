import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_tenant, current_user, owned_notebook
from app.models import Artifact, Notebook, User
from app.schemas import ArtifactOut, NoteIn, SkillCard, SkillRunIn
from app.services.skills import STUDIO_CATALOG, run_skill
from app.services.studio.export import export_artifact

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


@api.post("/skills/{skill_id}/run")
async def run(
    skill_id: str,
    notebook_id: uuid.UUID,
    body: SkillRunIn,
    session: AsyncSession = Depends(get_session),
    tenant: str = Depends(current_tenant),
) -> dict:
    notebook = await session.get(Notebook, notebook_id)
    if notebook is None or notebook.tenant_id != tenant:
        raise HTTPException(404, "Notebook nicht gefunden")
    locked = {card.id for card in STUDIO_CATALOG if card.status == "locked"}
    if skill_id in locked:
        raise HTTPException(400, "Diese Studio-Funktion ist gesperrt.")
    return await run_skill(session, notebook, skill_id, body.args)
