import uuid

from arq.connections import RedisSettings

from app.config import settings
from app.db import SessionLocal
from app.services.research import run_research_job


async def research_task(_ctx: dict, job_id: str) -> None:
    async with SessionLocal() as session:
        await run_research_job(session, uuid.UUID(job_id))


class WorkerSettings:
    functions = [research_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url or "redis://localhost:6379")
