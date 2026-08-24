from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Artifact, AuditEvent, GenerationLog, Message, Notebook, ResearchJob, SkillRun, Source, User
from app.services.auth import is_demo_email, normalize_email
from app.services.passwords import hash_password, verify_password
from app.services.tracing import delete_user_traces


async def erase_notebook(session: AsyncSession, notebook: Notebook) -> None:
    sources = list((await session.execute(select(Source).where(Source.notebook_id == notebook.id))).scalars())
    for source in sources:
        if source.file_path:
            path = Path(source.file_path)
            if path.exists():
                path.unlink()
        await session.delete(source)
    for model in (GenerationLog, Message, Artifact, ResearchJob, SkillRun, AuditEvent):
        rows = (await session.execute(select(model).where(model.notebook_id == notebook.id))).scalars()
        for row in rows:
            await session.delete(row)
    await session.delete(notebook)


async def create_empty_notebook(session: AsyncSession, tenant_id: str) -> Notebook:
    notebook = Notebook(
        tenant_id=tenant_id,
        title="Unbenanntes Notebook",
        provider=settings.default_provider,
        model_id=settings.default_model,
    )
    session.add(notebook)
    await session.flush()
    return notebook


async def ensure_notebook(session: AsyncSession, tenant_id: str) -> Notebook:
    existing = await session.scalar(select(Notebook).where(Notebook.tenant_id == tenant_id).limit(1))
    if existing is not None:
        return existing
    return await create_empty_notebook(session, tenant_id)


async def erase_tenant(session: AsyncSession, tenant_id: str) -> None:
    notebooks = list((await session.execute(select(Notebook).where(Notebook.tenant_id == tenant_id))).scalars())
    for notebook in notebooks:
        await erase_notebook(session, notebook)
    delete_user_traces(tenant_id)


async def seed_demo_user(session: AsyncSession) -> None:
    if not settings.demo_email.strip() or not settings.demo_password:
        return
    email = normalize_email(settings.demo_email)
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, password_hash=hash_password(settings.demo_password))
        session.add(user)
        await session.flush()
        await create_empty_notebook(session, str(user.id))
        await session.commit()
        return
    if not verify_password(settings.demo_password, user.password_hash):
        user.password_hash = hash_password(settings.demo_password)
    await ensure_notebook(session, str(user.id))
    await session.commit()


def user_is_demo(user: User) -> bool:
    return is_demo_email(user.email)
