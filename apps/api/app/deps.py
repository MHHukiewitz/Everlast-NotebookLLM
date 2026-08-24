from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session


async def tenant_id() -> str:
    return settings.default_tenant_id


async def db_session(session: AsyncSession = Depends(get_session)) -> AsyncSession:
    return session
