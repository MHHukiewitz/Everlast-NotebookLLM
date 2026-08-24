import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Notebook, User


async def current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    raw = request.session.get("user_id")
    if not isinstance(raw, str) or not raw:
        raise HTTPException(status_code=401, detail="Nicht angemeldet")
    user = await session.get(User, uuid.UUID(raw))
    if user is None:
        raise HTTPException(status_code=401, detail="Nicht angemeldet")
    return user


async def current_tenant(user: User = Depends(current_user)) -> str:
    return str(user.id)


async def owned_notebook(
    notebook_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    tenant: str = Depends(current_tenant),
) -> Notebook:
    notebook = await session.get(Notebook, notebook_id)
    if notebook is None or notebook.tenant_id != tenant:
        raise HTTPException(status_code=404, detail="Notebook nicht gefunden")
    return notebook
