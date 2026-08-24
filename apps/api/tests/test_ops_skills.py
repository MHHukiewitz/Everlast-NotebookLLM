import asyncio
import uuid

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Artifact, Notebook, ResearchJob, Source
from app.services.skills import run_skill


async def _ops_notebook() -> None:
    async with SessionLocal() as session:
        notebook = Notebook(
            tenant_id=settings.default_tenant_id,
            title=f"Eval Ops Pytest {uuid.uuid4().hex[:8]}",
        )
        session.add(notebook)
        await session.flush()
        note = await run_skill(
            session,
            notebook,
            "notes.create",
            {"title": "Ops-Notiz", "body": "Ingest bleibt lokal."},
        )
        artifact = await session.get(Artifact, uuid.UUID(note["artifact_id"]))
        assert artifact is not None
        assert artifact.title == "Ops-Notiz"
        assert artifact.payload["body"] == "Ingest bleibt lokal."

        alpha = Source(
            tenant_id=notebook.tenant_id,
            notebook_id=notebook.id,
            type="text",
            title="Alpha Quelle",
            status="ready",
            origin_uri="eval://alpha",
            selected=True,
        )
        beta = Source(
            tenant_id=notebook.tenant_id,
            notebook_id=notebook.id,
            type="text",
            title="Beta Quelle",
            status="ready",
            origin_uri="eval://beta",
            selected=True,
        )
        session.add(alpha)
        session.add(beta)
        await session.commit()

        listed = await run_skill(session, notebook, "sources.list", {})
        titles = {row["title"] for row in listed["sources"]}
        assert titles == {"Alpha Quelle", "Beta Quelle"}

        toggled = await run_skill(
            session,
            notebook,
            "sources.set_selected",
            {"source_id": str(alpha.id), "selected": False},
        )
        assert toggled["selected"] is False
        await session.refresh(alpha)
        assert alpha.selected is False

        deleted = await run_skill(session, notebook, "sources.delete_matching", {"query": "Beta"})
        assert deleted["count"] == 1
        left = (
            await session.execute(select(Source).where(Source.notebook_id == notebook.id))
        ).scalars()
        assert [row.title for row in left] == ["Alpha Quelle"]

        job = await run_skill(
            session, notebook, "research.fast", {"query": "ops pytest enqueue only"}
        )
        assert job["status"] == "queued"
        assert job["mode"] == "fast"
        stored = await session.get(ResearchJob, uuid.UUID(job["job_id"]))
        assert stored is not None
        assert stored.query == "ops pytest enqueue only"
        assert stored.status == "queued"

        await session.delete(notebook)
        await session.commit()


def test_notes_and_source_skills() -> None:
    asyncio.run(_ops_notebook())
