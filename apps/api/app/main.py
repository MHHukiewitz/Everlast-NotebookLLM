from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import Notebook
from app.routers import chat, compliance, eval as eval_router, notebooks, research, skills, sources
from app.services.ingest import rebuild_embeddings


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("ALTER TABLE eval_items ADD COLUMN IF NOT EXISTS task VARCHAR(32) DEFAULT 'chat'")
        )
    async with SessionLocal() as session:
        existing = await session.scalar(
            select(Notebook.id)
            .where(Notebook.tenant_id == settings.default_tenant_id)
            .limit(1)
        )
        if existing is None:
            session.add(
                Notebook(
                    tenant_id=settings.default_tenant_id,
                    title="Unbenanntes Notebook",
                    provider=settings.default_provider,
                    model_id=settings.default_model,
                )
            )
            await session.commit()
        if settings.embedding_backend == "ollama":
            await rebuild_embeddings(session)
    yield
    await engine.dispose()


app = FastAPI(title="Everlast Notebook", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(notebooks.api)
app.include_router(sources.api)
app.include_router(chat.api)
app.include_router(skills.api)
app.include_router(research.api)
app.include_router(compliance.api)
app.include_router(eval_router.api)


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(Exception)
async def any_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=500)
